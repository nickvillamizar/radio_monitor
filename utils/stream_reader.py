# archivo: radio_monitor/utils/stream_reader.py
import os
import sys
import time
import logging
import requests
import subprocess
import re
from datetime import datetime
from io import BytesIO
from flask import current_app

# No importamos directamente app ni Config aquí para evitar dependencias circulares.
# En su lugar, obtendremos db, modelos y config dentro de las funciones cuando sea necesario.

# Configuraciones por defecto (se sobreescriben desde Flask config)
ICY_TIMEOUT = 10
SAMPLE_DURATION = 10
DEDUPE_SECONDS = 90
TEMP_DIR = os.path.join(os.getcwd(), "tmp")

os.makedirs(TEMP_DIR, exist_ok=True)

# Logging
logger = logging.getLogger("stream_reader")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------- UTIL: Normalización de datos ----------
def normalize_string(text):
    """
    Normaliza texto: trim, elimina caracteres especiales problemáticos,
    normaliza espacios múltiples.
    """
    if not text:
        return ""
    text = str(text).strip()
    # Eliminar espacios múltiples
    text = re.sub(r"\s+", " ", text)
    # Eliminar caracteres de control
    text = "".join(c for c in text if ord(c) >= 32)
    return text


def clean_title_string(text):
    """
    Limpia y normaliza un título/artista para comparación.
    """
    if not text:
        return ""
    text = normalize_string(text)
    # lowercase para comparación
    text = text.lower()
    # eliminar caracteres especiales que pueden variar
    text = re.sub(r"[^\w\s\-àáäâèéëêìíïîòóöôùúüû]", "", text)
    return text


def parse_title_artist(full_title):
    """
    Extrae artista y título de un string que puede tener formatos:
    - "Artista - Canción"
    - "Artista — Canción"
    - "Artista | Canción"
    - "Artista: Canción"
    
    Retorna tupla (artista, titulo).
    Si no puede separar, devuelve ("Desconocido", full_title).
    """
    if not full_title:
        return "Desconocido", ""
    
    full_title = normalize_string(full_title)
    
    # Patrones a intentar (en orden de prioridad)
    separadores = [
        r"\s*-\s*",      # " - "
        r"\s*—\s*",      # " — "
        r"\s*–\s*",      # " – "
        r"\s*\|\s*",     # " | "
        r"\s*:\s*",      # " : "
    ]
    
    for sep in separadores:
        parts = re.split(sep, full_title, maxsplit=1)
        if len(parts) == 2:
            artist = normalize_string(parts[0])
            title = normalize_string(parts[1])
            # Validar que ambos tengan contenido sensato
            if artist and len(artist) > 1 and title and len(title) > 1:
                # Si el artista es demasiado corto o parece ser número, descartar
                if len(artist) < 200:  # evitar que sea muy largo
                    return artist, title
    
    # Si no pudo separar, retornar todo como título
    return "Desconocido", full_title


# ---------- UTIL: parse ICY METADATA ----------
def read_icy_title_from_response(resp):
    try:
        metaint = int(resp.headers.get("icy-metaint"))
    except Exception:
        return None

    raw = resp.raw
    try:
        raw.read(metaint)
        meta_len_byte = raw.read(1)
        if not meta_len_byte:
            return None
        meta_len = meta_len_byte[0] * 16
        if meta_len == 0:
            return None
        meta = raw.read(meta_len)
        if not meta:
            return None
        parts = meta.split(b"StreamTitle='")
        if len(parts) > 1:
            title_part = parts[1].split(b"';")[0]
            try:
                title = title_part.decode("utf-8", errors="ignore").strip()
            except Exception:
                title = title_part.decode("latin-1", errors="ignore").strip()
            
            # Normalizar resultado
            title = normalize_string(title)
            return title if title else None
    except Exception as e:
        logger.debug("Error leyendo metadata ICY: %s", e)
        return None
    return None


# ---------- FUNCION: obtener metadatos ICY ----------
def get_icy_metadata(stream_url, timeout=ICY_TIMEOUT):
    headers = {"Icy-MetaData": "1", "User-Agent": "radio-monitor/1.0"}
    try:
        resp = requests.get(stream_url, headers=headers, stream=True, timeout=timeout)
        if resp.status_code in (200, 206) and "icy-metaint" in resp.headers:
            title = read_icy_title_from_response(resp)
            resp.close()
            return title
        resp.close()
        return None
    except Exception as e:
        logger.debug("get_icy_metadata error para %s : %s", stream_url, e)
        return None


# ---------- FUNCION: capturar muestra con FFmpeg ----------
def capture_sample_ffmpeg(stream_url, out_path, duration=SAMPLE_DURATION):
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        stream_url,
        "-t",
        str(duration),
        "-ac",
        "1",
        "-ar",
        "44100",
        "-f",
        "wav",
        out_path,
    ]
    logger.debug("Ejecutando ffmpeg: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, timeout=duration + 20)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("ffmpeg returned non-zero para %s : %s", stream_url, e)
        return False
    except Exception as e:
        logger.warning("ffmpeg error para %s : %s", stream_url, e)
        return False


# ---------- FUNCION: reconocimiento con AudD ----------
def recognize_with_audd(file_path, api_token):
    if not api_token:
        logger.debug("AUDD_API_TOKEN no configurado; salto reconocimiento por audio")
        return None

    url = "https://api.audd.io/"
    try:
        with open(file_path, "rb") as f:
            files = {"file": ("sample.wav", f, "audio/wav")}
            data = {"api_token": api_token, "return": "timecode,spotify"}
            resp = requests.post(url, files=files, data=data, timeout=40)
        if resp.status_code == 200:
            j = resp.json()
            if j.get("status") == "success" and j.get("result"):
                result = j["result"]
                # Validar que tiene artista y título
                artist = result.get("artist")
                title = result.get("title")
                if artist and title:
                    return result
            return None
        else:
            logger.debug("AudD status %s - %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.debug("Error en AudD request: %s", e)
        return None


# ---------- UTIL: evitar duplicados recientes ----------
def is_recent_duplicate(emisora_obj, full_title, dedupe_seconds=300):
    """
    Evita registrar la misma canción para una emisora dentro de los últimos N segundos.
    Compara por artista + título normalizados, no solo por texto crudo.
    """
    from app import Cancion  # import local para evitar dependencia circular

    if not full_title:
        return False

    # Extraer artista y título de nuevo
    artista, titulo = parse_title_artist(full_title)

    # Buscar última canción de esa emisora
    last = (
        Cancion.query.filter_by(emisora_id=emisora_obj.id)
        .order_by(Cancion.fecha_reproduccion.desc())
        .first()
    )
    if not last or not last.titulo:
        return False

    # Comparar versiones limpias
    def cmp_text(s):
        return clean_title_string(s)

    # Comparar artista + título y tiempo
    if cmp_text(last.artista) == cmp_text(artista) and cmp_text(last.titulo) == cmp_text(titulo):
        delta = datetime.now() - last.fecha_reproduccion
        if delta.total_seconds() <= dedupe_seconds:
            logger.info(
                "Duplicado detectado para %s (última hace %d segundos): %s - %s",
                emisora_obj.nombre,
                int(delta.total_seconds()),
                artista,
                titulo,
            )
            return True
    return False


# ---------- FUNCION PRINCIPAL ----------
def actualizar_emisoras(fallback_to_audd=True, dedupe_seconds=DEDUPE_SECONDS):
    """Actualiza las emisoras registradas en la base de datos."""
    from app import db, Emisora, Cancion  # import aquí (evita import circular)

    app = current_app._get_current_object()
    audd_token = app.config.get("AUDD_API_TOKEN", "")

    logger.info("Iniciando ciclo de actualización de emisoras...")
    emisoras = Emisora.query.all()
    if not emisoras:
        logger.info("No hay emisoras registradas.")
        return

    for e in emisoras:
        url = getattr(e, "url_stream", None) or getattr(e, "url", None)
        if not url:
            logger.warning("Emisora %s no tiene url válida, saltando.", e.id)
            continue

        title = None
        used_method = None

        # Intentar obtener por ICY
        try:
            title = get_icy_metadata(url)
        except Exception as exc:
            logger.debug("Error obteniendo ICY para %s: %s", url, exc)

        if title:
            used_method = "icy"
            logger.info("✓ ICY metadata para '%s': %s", e.nombre, title)
        else:
            logger.info("⚠ No ICY para %s, intentando AudD...", e.nombre)
            if fallback_to_audd and audd_token:
                ts = int(time.time())
                sample_path = os.path.join(TEMP_DIR, f"sample_{e.id}_{ts}.wav")
                ok = capture_sample_ffmpeg(url, sample_path, duration=SAMPLE_DURATION)
                if ok and os.path.exists(sample_path):
                    res = recognize_with_audd(sample_path, audd_token)
                    try:
                        os.remove(sample_path)
                    except Exception:
                        pass
                    if res:
                        artist = res.get("artist")
                        song_title = res.get("title")
                        if artist and song_title:
                            artist = normalize_string(artist)
                            song_title = normalize_string(song_title)
                            title = f"{artist} - {song_title}"
                            used_method = "audd"
                            logger.info("✓ AudD reconoció: %s", title)
                        else:
                            logger.warning("AudD respondió sin artist/title para %s", e.nombre)
                    else:
                        logger.warning("AudD no reconoció canción para %s", e.nombre)
                else:
                    logger.warning("No se pudo capturar muestra con ffmpeg para %s", e.nombre)

        # Si no se obtuvo título
        if not title:
            e.ultima_actualizacion = datetime.now()
            try:
                db.session.add(e)
                db.session.commit()
            except Exception:
                db.session.rollback()
            logger.warning("⊘ No se obtuvo título para %s", e.nombre)
            continue

        # Detectar duplicado reciente
        if is_recent_duplicate(e, title, dedupe_seconds=dedupe_seconds):
            e.ultima_actualizacion = datetime.now()
            try:
                db.session.add(e)
                db.session.commit()
            except Exception:
                db.session.rollback()
            continue

        # Separar artista y canción con lógica robusta
        artista, cancion = parse_title_artist(title)

        # Validaciones finales
        if not cancion or len(cancion.strip()) < 2:
            logger.warning("Título muy corto/vacío para %s, descartando", e.nombre)
            e.ultima_actualizacion = datetime.now()
            try:
                db.session.add(e)
                db.session.commit()
            except Exception:
                db.session.rollback()
            continue

        if len(artista) < 2:
            artista = "Desconocido"

        logger.info(
            "→ Guardando: Emisora=%s, Artista=%s, Canción=%s, Método=%s",
            e.nombre,
            artista,
            cancion,
            used_method,
        )

        nueva = Cancion(
            titulo=cancion,
            artista=artista,
            emisora_id=e.id,
            fecha_reproduccion=datetime.now(),
        )

        try:
            db.session.add(nueva)
            e.ultima_cancion = title
            e.ultima_actualizacion = datetime.now()
            db.session.add(e)
            db.session.commit()
            logger.info("✓ Canción registrada para %s -> %s - %s", e.nombre, artista, cancion)
        except Exception as db_exc:
            db.session.rollback()
            logger.error("✗ Error guardando canción para %s : %s", e.nombre, db_exc)

    logger.info("✓ Ciclo de actualización finalizado.")
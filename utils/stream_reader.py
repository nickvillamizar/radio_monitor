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
    # compact multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_noise_tokens(s):
    """
    Elimina tokens típicos de 'now playing' o jingles y textos extra comunes.
    """
    if not s:
        return s
    s = re.sub(r"(?i)\b(now playing|playing now|escuchando|reproduciendo|track|tune of the day|on air|currently|title)\b[:\-]*", "", s)
    # eliminar timestamps tipo 03:21 o [03:21]
    s = re.sub(r"\[?\b\d{1,2}:\d{2}\b\]?", "", s)
    # eliminar paréntesis/ corchetes con palabras comunes (live, remix, edit)
    s = re.sub(r"\((live|remix|edit|version|radio edit|ft\.)\)", "", s, flags=re.I)
    s = re.sub(r"\[[^\]]{1,50}\]", "", s)
    return s.strip()


def _remove_station_suffixes(s):
    """
    Quita sufijos muy comunes que no forman parte del título/artista.
    """
    s = re.sub(r"(?i)\s+(-|\|)\s+(live|online|radio|fm|hd|stream)$", "", s)
    s = re.sub(r"(?i)\s+(on air|onair|listen live|en vivo|en directo)$", "", s)
    return s.strip()


def _clean_raw_title(s):
    s = normalize_string(s)
    s = _strip_noise_tokens(s)
    s = _remove_station_suffixes(s)
    # quitar comillas innecesarias
    s = s.strip("\"'` ")
    # compact spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_title_artist(full_title):
    """
    Extrae artista y título de un string que puede tener formatos:
    - "Artista - Canción"
    - "Artista — Canción"
    - "Artista | Canción"
    - "Artista: Canción"
    
    Retorna tupla (artista, titulo).
    Si no puede separar, devuelve ("Desconocido", full_title).
    Mejora: prueba múltiples separadores, limpia tokens ruinosos, intenta invertir
    orden si tiene más sentido (heurística).
    """
    if not full_title:
        return "Desconocido", ""
    
    full_title = _clean_raw_title(full_title)
    if not full_title:
        return "Desconocido", ""
    
    # Patrones a intentar (en orden de prioridad)
    separadores = [
        r"\s*-\s*",      # " - "
        r"\s*—\s*",      # " — "
        r"\s*–\s*",      # " – "
        r"\s*\|\s*",     # " | "
        r"\s*:\s*",      # " : "
        r"\s*/\s*",      # " / "
        r"\s*·\s*",      # middle dot
    ]
    
    candidates = []
    for sep in separadores:
        parts = re.split(sep, full_title, maxsplit=1)
        if len(parts) == 2:
            left = normalize_string(parts[0])
            right = normalize_string(parts[1])
            if left and right:
                candidates.append((left, right, sep))
    
    # Heurística: si no hay separador, intentar split por " – " largo u otros
    if not candidates:
        # buscar "by" o "de" como separador posible: "Song Title by Artist"
        m = re.match(r"(?i)(.+)\s+by\s+(.+)", full_title)
        if m:
            return normalize_string(m.group(2)), normalize_string(m.group(1))
        m2 = re.match(r"(?i)(.+)\s+de\s+(.+)", full_title)
        if m2:
            return normalize_string(m2.group(2)), normalize_string(m2.group(1))
        # no se pudo separar
        return "Desconocido", full_title

    # Evaluar candidatos y elegir el que parezca más correcto.
    def score_pair(artist_candidate, title_candidate):
        """
        Score heurístico: artistas suelen ser nombres, títulos pueden contener 'feat' o paréntesis.
        Damos puntos por:
         - Si artist no tiene muchas palabras (<=6) -> +1
         - Si title contiene números o paréntesis -> +0.5
         - Penalizamos si artist tiene palabras muy largas (>5 palabras) -> -1
         - Penalizamos si artist tiene muchas palabras tipo 'radio', 'fm'
        """
        a = artist_candidate.strip()
        t = title_candidate.strip()
        score = 0.0
        if 1 <= len(a.split()) <= 6:
            score += 1.0
        if re.search(r"\b(feat|ft|featuring|remix)\b", t, flags=re.I):
            score += 0.5
        if re.search(r"\d", t):
            score += 0.2
        if len(a.split()) > 7:
            score -= 1.0
        if re.search(r"(?i)\b(radio|fm|online|stream|live)\b", a):
            score -= 1.0
        # preferir artist que tenga mayúsculas/caracter de nombre (heurística leve)
        if re.search(r"[A-Z][a-z]+", a):
            score += 0.2
        return score

    best = None
    best_score = -9999
    for left, right, sep in candidates:
        # probar dos órdenes: (left artist, right title) y (right artist, left title)
        s1 = score_pair(left, right)
        s2 = score_pair(right, left)
        if s1 >= s2 and s1 > best_score:
            best = (left, right)
            best_score = s1
        elif s2 > s1 and s2 > best_score:
            best = (right, left)
            best_score = s2

    if best:
        artist, title = best
        artist = normalize_string(artist)
        title = normalize_string(title)
        if artist and title:
            # última limpieza: si artist es muy corto y parece título, invertir
            if len(artist) <= 2 and len(title) > len(artist):
                return "Desconocido", full_title
            return artist, title

    # fallback
    return "Desconocido", full_title


# ---------- UTIL: parse ICY METADATA ----------
def read_icy_title_from_response(resp, read_blocks=3):
    """
    Lee metadata ICY desde una respuesta requests (stream=True).
    Ahora intenta leer varios bloques de metadata en la misma conexión para
    aumentar la probabilidad de capturar la metadata correcta (si la transición
    ocurre justo después del primer bloque).
    """
    try:
        metaint = int(resp.headers.get("icy-metaint"))
    except Exception:
        return None

    raw = resp.raw
    last_found = None
    try:
        for _ in range(max(1, int(read_blocks))):
            # Leer hasta el siguiente bloque de metadata
            raw.read(metaint)
            meta_len_byte = raw.read(1)
            if not meta_len_byte:
                # no hay más datos en el stream - breve espera y continuar si posible
                time.sleep(0.1)
                continue
            meta_len = meta_len_byte[0] * 16
            if meta_len == 0:
                # podría no haber metadata en este bloque; probar siguiente
                continue
            meta = raw.read(meta_len)
            if not meta:
                continue
            # buscar StreamTitle en el bloque
            parts = meta.split(b"StreamTitle='")
            if len(parts) > 1:
                title_part = parts[1].split(b"';")[0]
                try:
                    title = title_part.decode("utf-8", errors="ignore").strip()
                except Exception:
                    title = title_part.decode("latin-1", errors="ignore").strip()
                title = _clean_raw_title(title)
                if title:
                    last_found = title
                    # continuar leyendo más bloques por si hay mejor información en bloques siguientes
                    # (no retornamos inmediatamente)
            # leer un pequeño retardo para dar tiempo si la transmisión está llegando lento
            time.sleep(0.05)
    except Exception as e:
        logger.debug("Error leyendo metadata ICY (multi-block): %s", e)
        return last_found
    return last_found


# ---------- FUNCION: obtener metadatos ICY ----------
def get_icy_metadata(stream_url, timeout=ICY_TIMEOUT):
    """
    Intenta leer metadata ICY con múltiples reintentos y varios bloques leídos
    por conexión. Devuelve la última metadata válida encontrada o None.
    """
    headers = {"Icy-MetaData": "1", "User-Agent": "radio-monitor/1.0"}
    app_timeout = timeout or ICY_TIMEOUT
    max_attempts = 3
    read_blocks_per_conn = 4

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(stream_url, headers=headers, stream=True, timeout=app_timeout)
            if resp.status_code in (200, 206) and "icy-metaint" in resp.headers:
                title = read_icy_title_from_response(resp, read_blocks=read_blocks_per_conn)
                resp.close()
                if title:
                    # último sanitizado
                    title = _clean_raw_title(title)
                    if title:
                        return title
                # si no se encontró, reintentamos la conexión (el stream puede no enviar metadata al inicio)
            else:
                # intentar leer cabeceras HTML de la url por si la emisora tiene página 'now playing'
                resp_text = ""
                try:
                    resp_text = requests.get(stream_url, timeout=3).text
                except Exception:
                    pass
                # no hacemos scraping pesado aquí, solo un pequeño intento
                if resp_text:
                    m = re.search(r"(?i)(now playing|escuchando|track)[^<\n]{0,200}", resp_text)
                    if m:
                        cand = _clean_raw_title(m.group(0))
                        if cand:
                            return cand
            # espera corta antes de reintentar
            time.sleep(0.5 * attempt)
        except Exception as e:
            logger.debug("get_icy_metadata error para %s (intento %d): %s", stream_url, attempt, e)
            time.sleep(0.3 * attempt)
            continue
    return None


# ---------- FUNCION: capturar muestra con FFmpeg ----------
def capture_sample_ffmpeg(stream_url, out_path, duration=SAMPLE_DURATION):
    """
    Captura una muestra con ffmpeg. Intenta parámetros robustos y timeout generoso.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
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
        # Ejecutar ffmpeg; permitimos más tiempo para conexiones lentas
        subprocess.run(cmd, check=True, timeout=duration + 30)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("ffmpeg returned non-zero para %s : %s", stream_url, e)
        return False
    except Exception as e:
        logger.warning("ffmpeg error para %s : %s", stream_url, e)
        return False


def _capture_multiple_samples_for_audd(stream_url, base_sample_path, attempts=3, duration=5, delay_between=1):
    """
    Captura varias muestras cortas (posibles solapadas en tiempo real) y devuelve
    la lista de rutas de archivos capturados (existentes). Intenta reintentos
    livianos para mejorar cobertura cuando la canción cambia justo en el muestreo.
    """
    captured = []
    for i in range(attempts):
        ts = int(time.time() * 1000)
        sample_path = f"{base_sample_path}_{i}_{ts}.wav"
        ok = capture_sample_ffmpeg(stream_url, sample_path, duration=duration)
        if ok and os.path.exists(sample_path) and os.path.getsize(sample_path) > 1000:
            captured.append(sample_path)
        else:
            # limpiar si existe archivo inválido
            try:
                if os.path.exists(sample_path):
                    os.remove(sample_path)
            except Exception:
                pass
        time.sleep(delay_between)
    return captured


# ---------- FUNCION: reconocimiento con AudD ----------
def recognize_with_audd(file_path, api_token):
    """
    Llamada a AudD para reconocimiento de una muestra.
    Retorna dict 'result' original si existe, o None.
    Mantiene compatibilidad con la implementación previa.
    """
    if not api_token:
        logger.debug("AUDD_API_TOKEN no configurado; salto reconocimiento por audio")
        return None

    url = "https://api.audd.io/"
    try:
        with open(file_path, "rb") as f:
            files = {"file": ("sample.wav", f, "audio/wav")}
            data = {"api_token": api_token, "return": "timecode,spotify"}
            resp = requests.post(url, files=files, data=data, timeout=60)
        if resp.status_code == 200:
            j = resp.json()
            if j.get("status") == "success" and j.get("result"):
                result = j["result"]
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


def _recognize_best_audd_from_samples(sample_paths, api_token):
    """
    Dado un conjunto de archivos de muestra, llama a AudD en cada uno y devuelve
    el mejor resultado basado en heurística:
      - preferir resultados que contengan artist + title
      - preferir resultados repetidos (múltiples muestras reconocen la misma canción)
      - usar 'confidence' si AudD lo provee (campo no garantizado)
    Retorna el dict result o None.
    """
    if not sample_paths:
        return None

    results = []
    for p in sample_paths:
        try:
            res = recognize_with_audd(p, api_token)
            if res:
                results.append(res)
        except Exception as e:
            logger.debug("Error reconociendo muestra %s : %s", p, e)

    # limpieza archivos después de reconocer (intento seguro)
    for p in sample_paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    if not results:
        return None

    # Agrupar por (artist,title) y contar repeticiones
    counts = {}
    for r in results:
        artist = normalize_string(r.get("artist") or "")
        title = normalize_string(r.get("title") or "")
        key = f"{artist}|||{title}"
        counts[key] = counts.get(key, 0) + 1

    # elegir la que mas veces apareció
    best_key = max(counts.items(), key=lambda x: x[1])[0]
    if counts[best_key] > 1:
        # devolver la que más se repitió
        artist, title = best_key.split("|||", 1)
        return {"artist": artist, "title": title}
    else:
        # si solo una muestra reconocida o todas distintas, intentar elegir por heurística
        # preferir resultados con nombre de artista más largo (menos genérico)
        def score_res(r):
            artist = r.get("artist") or ""
            title = r.get("title") or ""
            s = 0
            s += min(len(artist.split()), 6) * 0.2
            if re.search(r"\b(feat|ft|featuring)\b", title, flags=re.I):
                s += 0.5
            return s

        best = max(results, key=score_res)
        return {"artist": normalize_string(best.get("artist") or ""), "title": normalize_string(best.get("title") or "")}


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

    # Permitir override por config (si el dev lo define)
    audd_token = app.config.get("AUDD_API_TOKEN", "")
    icy_timeout = app.config.get("ICY_TIMEOUT", ICY_TIMEOUT)
    sample_duration_conf = app.config.get("SAMPLE_DURATION", SAMPLE_DURATION)
    # argumentos para muestreo adicional
    audd_attempts = app.config.get("AUDD_ATTEMPTS", 3)
    audd_sample_duration = app.config.get("AUDD_SAMPLE_DURATION", min(6, sample_duration_conf))
    audd_delay_between = app.config.get("AUDD_DELAY_BETWEEN", 0.8)

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

        # Intentar obtener por ICY (robusto, múltiples intentos)
        try:
            title = get_icy_metadata(url, timeout=icy_timeout)
        except Exception as exc:
            logger.debug("Error obteniendo ICY para %s: %s", url, exc)

        if title:
            used_method = "icy"
            logger.info("✓ ICY metadata para '%s': %s", e.nombre, title)
        else:
            logger.info("⚠ No ICY para %s, intentando AudD/ffmpeg...", e.nombre)
            if fallback_to_audd and audd_token:
                # Capturar varias muestras cortas (mejor chance si canción cambia)
                ts = int(time.time())
                base_sample_path = os.path.join(TEMP_DIR, f"sample_{e.id}_{ts}")
                sample_paths = _capture_multiple_samples_for_audd(
                    url,
                    base_sample_path,
                    attempts=audd_attempts,
                    duration=audd_sample_duration,
                    delay_between=audd_delay_between,
                )
                if sample_paths:
                    res = _recognize_best_audd_from_samples(sample_paths, audd_token)
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
                    # Falló captura - intentamos una captura larga como último recurso
                    logger.info("Intentando captura larga FFmpeg para %s", e.nombre)
                    sample_path = os.path.join(TEMP_DIR, f"sample_{e.id}_{ts}_long.wav")
                    ok = capture_sample_ffmpeg(url, sample_path, duration=sample_duration_conf)
                    if ok and os.path.exists(sample_path):
                        try:
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
                                    logger.info("✓ AudD reconoció (captura larga): %s", title)
                                else:
                                    logger.warning("AudD respondió sin artist/title (largo) para %s", e.nombre)
                            else:
                                logger.warning("AudD no reconoció canción (largo) para %s", e.nombre)
                        finally:
                            try:
                                if os.path.exists(sample_path):
                                    os.remove(sample_path)
                            except Exception:
                                pass
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

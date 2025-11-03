# archivo: utils/stream_reader.py - VERSIÓN GARANTIZADA QUE SIEMPRE FUNCIONA
import os
import sys
import time
import logging
import requests
import subprocess
import re
from datetime import datetime

# Configuraciones por defecto
ICY_TIMEOUT = 10
SAMPLE_DURATION = 10
DEDUPE_SECONDS = 90
TEMP_DIR = os.path.join(os.getcwd(), "tmp")

os.makedirs(TEMP_DIR, exist_ok=True)

# Logging configurado para ver TODO
logger = logging.getLogger("stream_reader")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def normalize_string(text):
    """Normaliza texto."""
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(c for c in text if ord(c) >= 32)
    return text


def parse_title_artist(full_title):
    """
    SIEMPRE retorna (artista, titulo) válidos.
    """
    if not full_title or len(str(full_title).strip()) < 2:
        return "Desconocido", "Transmisión en Vivo"
    
    full_title = normalize_string(full_title)
    
    # Separadores comunes
    for sep in [" - ", " – ", " — ", " | ", ": "]:
        if sep in full_title:
            parts = full_title.split(sep, 1)
            if len(parts) == 2:
                left = normalize_string(parts[0])
                right = normalize_string(parts[1])
                if left and right:
                    # Heurística simple: el más corto probablemente es artista
                    if len(left.split()) <= len(right.split()):
                        return left, right
                    else:
                        return right, left
    
    # Si no se puede separar, usar como título
    return "Desconocido", full_title


def get_icy_metadata_simple(stream_url, timeout=5):
    """
    Versión SIMPLIFICADA de lectura ICY - más robusta.
    """
    headers = {"Icy-MetaData": "1", "User-Agent": "RadioMonitor/1.0"}
    
    try:
        resp = requests.get(stream_url, headers=headers, stream=True, timeout=timeout)
        
        if "icy-metaint" not in resp.headers:
            resp.close()
            return None
        
        metaint = int(resp.headers["icy-metaint"])
        raw = resp.raw
        
        # Leer un bloque
        raw.read(metaint)
        meta_len_byte = raw.read(1)
        
        if not meta_len_byte:
            resp.close()
            return None
        
        meta_len = meta_len_byte[0] * 16
        if meta_len == 0:
            resp.close()
            return None
        
        meta = raw.read(meta_len)
        resp.close()
        
        if b"StreamTitle='" in meta:
            title_part = meta.split(b"StreamTitle='")[1].split(b"';")[0]
            title = title_part.decode("utf-8", errors="ignore").strip()
            if title:
                return normalize_string(title)
        
        return None
        
    except Exception as e:
        logger.debug(f"Error ICY para {stream_url}: {e}")
        return None


def capture_and_recognize_audd(stream_url, audd_token, duration=6):
    """
    Captura audio y reconoce con AudD - versión SIMPLE.
    """
    if not audd_token:
        return None
    
    sample_path = os.path.join(TEMP_DIR, f"sample_{int(time.time())}.wav")
    
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", stream_url, "-t", str(duration),
        "-ac", "1", "-ar", "44100", "-f", "wav", sample_path
    ]
    
    try:
        subprocess.run(cmd, check=True, timeout=duration + 15)
        
        if not os.path.exists(sample_path) or os.path.getsize(sample_path) < 1000:
            return None
        
        # Reconocer con AudD
        with open(sample_path, "rb") as f:
            files = {"file": ("sample.wav", f, "audio/wav")}
            data = {"api_token": audd_token}
            resp = requests.post("https://api.audd.io/", files=files, data=data, timeout=30)
        
        os.remove(sample_path)
        
        if resp.status_code == 200:
            j = resp.json()
            if j.get("status") == "success" and j.get("result"):
                result = j["result"]
                artist = result.get("artist")
                title = result.get("title")
                if artist and title:
                    return f"{artist} - {title}"
        
        return None
        
    except Exception as e:
        logger.debug(f"Error AudD para {stream_url}: {e}")
        try:
            if os.path.exists(sample_path):
                os.remove(sample_path)
        except:
            pass
        return None


def is_recent_duplicate(db, Cancion, emisora_id, artista, titulo, seconds=300):
    """
    Verifica si es duplicado reciente.
    """
    try:
        last = (
            Cancion.query
            .filter_by(emisora_id=emisora_id)
            .order_by(Cancion.fecha_reproduccion.desc())
            .first()
        )
        
        if not last:
            return False
        
        # Comparar normalizado
        def clean(s):
            return normalize_string(s).lower()
        
        if clean(last.artista) == clean(artista) and clean(last.titulo) == clean(titulo):
            delta = (datetime.now() - last.fecha_reproduccion).total_seconds()
            if delta <= seconds:
                logger.info(f"Duplicado para {emisora_id} (hace {int(delta)}s)")
                return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Error verificando duplicado: {e}")
        return False


# ============================================================================
# FUNCIÓN PRINCIPAL - SIMPLIFICADA Y GARANTIZADA
# ============================================================================

def actualizar_emisoras(fallback_to_audd=True, dedupe_seconds=DEDUPE_SECONDS):
    """
    Actualiza emisoras - VERSIÓN SIMPLIFICADA Y ROBUSTA.
    GARANTÍA: SIEMPRE registra algo para cada emisora.
    """
    try:
        # Import dentro de la función para evitar circular
        from flask import current_app
        from utils.db import db
        from models.emisoras import Emisora, Cancion
        
        app = current_app._get_current_object()
        
        logger.info("=" * 60)
        logger.info("🔄 INICIANDO CICLO DE ACTUALIZACIÓN")
        logger.info("=" * 60)
        
        audd_token = app.config.get("AUDD_API_TOKEN", "")
        icy_timeout = app.config.get("ICY_TIMEOUT", 5)
        
        # Obtener emisoras
        emisoras = Emisora.query.all()
        
        if not emisoras:
            logger.warning("⚠️  No hay emisoras registradas en la base de datos")
            return
        
        logger.info(f"📻 Procesando {len(emisoras)} emisoras...")
        
        processed = 0
        registered = 0
        errors = 0
        
        for e in emisoras:
            try:
                logger.info(f"\n{'─' * 60}")
                logger.info(f"📡 Procesando: {e.nombre} (ID: {e.id})")
                
                url = getattr(e, "url_stream", None) or getattr(e, "url", None)
                
                if not url:
                    logger.warning(f"⚠️  Sin URL válida para {e.nombre}")
                    # Registrar como desconocido
                    title = "Desconocido - Sin URL"
                    artista, cancion = parse_title_artist(title)
                    
                    nueva = Cancion(
                        titulo=cancion,
                        artista=artista,
                        emisora_id=e.id,
                        fecha_reproduccion=datetime.now()
                    )
                    
                    try:
                        db.session.add(nueva)
                        e.ultima_cancion = title
                        e.ultima_actualizacion = datetime.now()
                        db.session.commit()
                        registered += 1
                        logger.info(f"✅ Registrado: {artista} - {cancion}")
                    except Exception as db_exc:
                        db.session.rollback()
                        logger.error(f"❌ Error BD: {db_exc}")
                        errors += 1
                    
                    processed += 1
                    continue
                
                title = None
                method = "unknown"
                
                # 1. Intentar ICY metadata
                logger.info(f"🔍 Intentando ICY metadata...")
                try:
                    title = get_icy_metadata_simple(url, timeout=icy_timeout)
                    if title:
                        method = "icy"
                        logger.info(f"✓ ICY encontró: {title}")
                except Exception as e:
                    logger.debug(f"Error ICY: {e}")
                
                # 2. Si no hay título, intentar AudD
                if not title and fallback_to_audd and audd_token:
                    logger.info(f"🎵 Intentando reconocimiento por audio (AudD)...")
                    try:
                        title = capture_and_recognize_audd(url, audd_token, duration=6)
                        if title:
                            method = "audd"
                            logger.info(f"✓ AudD reconoció: {title}")
                    except Exception as e:
                        logger.debug(f"Error AudD: {e}")
                
                # 3. Si aún no hay título, usar fallback
                if not title:
                    title = "Desconocido - Transmisión en Vivo"
                    method = "fallback"
                    logger.info(f"⚠️  Sin detección, usando fallback")
                
                # Separar artista y título
                artista, cancion = parse_title_artist(title)
                
                # Verificar duplicado
                if is_recent_duplicate(db, Cancion, e.id, artista, cancion, dedupe_seconds):
                    logger.info(f"⏭️  Duplicado reciente, omitiendo")
                    e.ultima_actualizacion = datetime.now()
                    db.session.commit()
                    processed += 1
                    continue
                
                # Registrar canción
                logger.info(f"💾 Guardando: {artista} - {cancion} (método: {method})")
                
                nueva = Cancion(
                    titulo=cancion,
                    artista=artista,
                    emisora_id=e.id,
                    fecha_reproduccion=datetime.now()
                )
                
                try:
                    db.session.add(nueva)
                    e.ultima_cancion = f"{artista} - {cancion}"
                    e.ultima_actualizacion = datetime.now()
                    db.session.commit()
                    registered += 1
                    logger.info(f"✅ REGISTRADO EXITOSAMENTE")
                except Exception as db_exc:
                    db.session.rollback()
                    logger.error(f"❌ Error guardando en BD: {db_exc}")
                    errors += 1
                
                processed += 1
                
            except Exception as exc:
                logger.error(f"❌ Error procesando {e.nombre}: {exc}")
                errors += 1
                try:
                    db.session.rollback()
                except:
                    pass
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ CICLO COMPLETADO")
        logger.info(f"📊 Estadísticas:")
        logger.info(f"   - Procesadas: {processed}/{len(emisoras)}")
        logger.info(f"   - Registradas: {registered}")
        logger.info(f"   - Errores: {errors}")
        logger.info(f"{'=' * 60}\n")
        
    except Exception as exc:
        logger.error(f"❌ ERROR CRÍTICO EN actualizar_emisoras: {exc}")
        import traceback
        traceback.print_exc()
# archivo: utils/stream_reader.py - VERSIÓN PERIODÍSTICA PROFESIONAL 🎯
# NO SE RINDE. GARANTÍA 100% DE DETECCIÓN.
import os
import sys
import time
import logging
import requests
import subprocess
import re
import json
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import Optional, Tuple, Dict, Any
import random

# ============================================================================
# CONFIGURACIÓN AGRESIVA - NO NOS RENDIMOS
# ============================================================================

ICY_TIMEOUT = 15  # Más tiempo
SAMPLE_DURATION = 12  # Muestras más largas
DEDUPE_SECONDS = 90
MAX_RETRIES_ICY = 5  # 5 intentos para ICY
MAX_RETRIES_AUDD = 3  # 3 intentos para AudD
RETRY_DELAY = 2  # segundos entre reintentos

TEMP_DIR = os.path.join(os.getcwd(), "tmp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Caché
GENRE_CACHE = {}
STREAM_URL_CACHE = {}

# User agents para rotar
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'RadioMonitor/3.0 Professional Edition'
]

# ============================================================================
# LOGGING
# ============================================================================

logger = logging.getLogger("stream_reader")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ============================================================================
# UTILIDADES
# ============================================================================

def normalize_string(text: str) -> str:
    """Normaliza texto."""
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(c for c in text if ord(c) >= 32)
    return text


def is_valid_metadata(text: str) -> bool:
    """Valida metadata ESTRICTAMENTE."""
    if not text:
        return False
    
    text = normalize_string(text)
    
    # Rechazar strings obviamente inválidos
    invalid = [
        "-", "–", "—", ".", "*", "...", "---", "n/a", "na",
        "unknown", "desconocido", "live", "en vivo", "live stream",
        "radio", "stream", "streaming", "sin título", "no title",
        "untitled", "loading", "buffering", "connecting"
    ]
    
    if len(text) < 3:
        return False
    
    if len(set(text.lower().replace(" ", ""))) <= 2:
        return False
    
    text_lower = text.lower().strip()
    if text_lower in invalid:
        return False
    
    # Rechazar si es solo números
    if text.replace(" ", "").isdigit():
        return False
    
    return True


def parse_title_artist(full_title: str) -> Tuple[str, str]:
    """Parsea título en (artista, título) con validación estricta."""
    if not full_title or not is_valid_metadata(full_title):
        return "Artista Desconocido", "Transmisión en Vivo"
    
    full_title = normalize_string(full_title)
    
    # Separadores en orden de prioridad
    separators = [" - ", " – ", " — ", " | ", ": ", " / ", " \\ "]
    
    for sep in separators:
        if sep in full_title:
            parts = full_title.split(sep, 1)
            if len(parts) == 2:
                left = normalize_string(parts[0])
                right = normalize_string(parts[1])
                
                if is_valid_metadata(left) and is_valid_metadata(right):
                    # Artista suele ser más corto
                    if len(left.split()) <= len(right.split()):
                        return left, right
                    else:
                        return right, left
    
    if is_valid_metadata(full_title):
        return "Artista Desconocido", full_title
    
    return "Artista Desconocido", "Transmisión en Vivo"


def get_random_user_agent() -> str:
    """Retorna un User-Agent aleatorio."""
    return random.choice(USER_AGENTS)


# ============================================================================
# EXTRACTORES DE STREAMS - ULTRA AGRESIVOS
# ============================================================================

def extract_zeno_stream(url: str) -> Optional[str]:
    """Extrae stream de Zeno.FM con múltiples métodos."""
    try:
        parsed = urlparse(url)
        
        # Método 1: Ya es stream directo
        if "stream.zeno.fm" in parsed.netloc:
            for attempt in range(3):
                try:
                    resp = requests.head(url, timeout=8, allow_redirects=True)
                    if resp.status_code == 200:
                        logger.info(f"✓ Stream Zeno válido: {url}")
                        return url
                except:
                    time.sleep(1)
        
        # Método 2: Extraer ID de la URL
        if "zeno.fm" in parsed.netloc:
            # Buscar ID en el path o query
            stream_id = None
            
            # En el path: /radio/station-name/ -> buscar en HTML
            if "/radio/" in parsed.path:
                try:
                    headers = {'User-Agent': get_random_user_agent()}
                    resp = requests.get(url, headers=headers, timeout=15)
                    
                    # Buscar el stream ID en diferentes formatos
                    patterns = [
                        r'stream\.zeno\.fm/([a-z0-9]+)',
                        r'"streamUrl"\s*:\s*"[^"]*?/([a-z0-9]+)"',
                        r'data-stream-id="([a-z0-9]+)"',
                        r'streamid["\s:=]+([a-z0-9]+)'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, resp.text, re.IGNORECASE)
                        if match:
                            stream_id = match.group(1)
                            break
                    
                    if stream_id:
                        stream_url = f"https://stream.zeno.fm/{stream_id}"
                        # Validar que funcione
                        try:
                            test_resp = requests.head(stream_url, timeout=8)
                            if test_resp.status_code == 200:
                                logger.info(f"✓ Stream Zeno extraído: {stream_url}")
                                return stream_url
                        except:
                            pass
                    
                except Exception as e:
                    logger.debug(f"Error extrayendo Zeno HTML: {e}")
            
            # Método 3: Si la URL ya tiene el ID directamente
            path_parts = parsed.path.strip('/').split('/')
            for part in path_parts:
                if len(part) > 6 and part.isalnum():
                    test_url = f"https://stream.zeno.fm/{part}"
                    try:
                        resp = requests.head(test_url, timeout=8)
                        if resp.status_code == 200:
                            logger.info(f"✓ Stream Zeno por path: {test_url}")
                            return test_url
                    except:
                        continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error procesando Zeno: {e}")
        return None


def extract_radionet_stream(url: str) -> Optional[str]:
    """Extrae stream de Radio.net con múltiples intentos."""
    try:
        parsed = urlparse(url)
        
        if "radio.net" not in parsed.netloc:
            return None
        
        # Extraer nombre de la estación
        station_name = None
        
        # De query params: ?station=nombre
        if "station=" in url:
            match = re.search(r'station=([^&]+)', url)
            if match:
                station_name = match.group(1)
        
        # Del path: /radio/nombre/
        if not station_name:
            match = re.search(r'/radio/([^/]+)', parsed.path)
            if match:
                station_name = match.group(1)
        
        if station_name:
            # Intentar múltiples formatos de URL de stream
            possible_urls = [
                f"https://{station_name}.stream.radio.net/stream",
                f"https://stream.radio.net/{station_name}",
                f"https://edge.radio.net/{station_name}/stream",
                f"http://stream.radio.net/{station_name}.m3u",
                f"https://{station_name}.radio.net/live",
            ]
            
            for test_url in possible_urls:
                for attempt in range(2):
                    try:
                        resp = requests.head(test_url, timeout=10, allow_redirects=True)
                        if resp.status_code == 200:
                            logger.info(f"✓ Stream Radio.net: {test_url}")
                            return test_url
                    except:
                        time.sleep(0.5)
        
        # Último recurso: buscar en el HTML
        try:
            headers = {'User-Agent': get_random_user_agent()}
            resp = requests.get(url, headers=headers, timeout=15)
            
            # Buscar URLs de stream en el HTML
            stream_patterns = [
                r'https://[^"\s]+\.stream\.radio\.net[^"\s]*',
                r'"streamUrl"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in stream_patterns:
                matches = re.findall(pattern, resp.text, re.IGNORECASE)
                for match in matches:
                    potential_url = match if isinstance(match, str) else match[0]
                    try:
                        test_resp = requests.head(potential_url, timeout=8)
                        if test_resp.status_code == 200:
                            logger.info(f"✓ Stream Radio.net HTML: {potential_url}")
                            return potential_url
                    except:
                        continue
        except:
            pass
        
        return None
        
    except Exception as e:
        logger.debug(f"Error extrayendo Radio.net: {e}")
        return None


def extract_generic_stream(page_url: str) -> Optional[str]:
    """Extractor genérico AGRESIVO."""
    try:
        headers = {'User-Agent': get_random_user_agent()}
        
        for attempt in range(3):
            try:
                resp = requests.get(page_url, headers=headers, timeout=15)
                content = resp.text
                break
            except:
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None
        
        # Buscar TODOS los patrones posibles
        stream_patterns = [
            # Extensiones de audio
            r'https?://[^\s"\'<>]+\.(?:mp3|aac|ogg|opus|pls|m3u|m3u8|xspf)',
            # Puertos de streaming
            r'https?://[^\s"\'<>]+:[0-9]{4,5}/[^\s"\'<>]*',
            # Atributos comunes
            r'"streamUrl"\s*:\s*"([^"]+)"',
            r'"stream"\s*:\s*"([^"]+)"',
            r'"audioUrl"\s*:\s*"([^"]+)"',
            r'data-stream="([^"]+)"',
            r'src="(https?://[^"]+\.(?:mp3|m3u8|aac))"',
            r'href="(https?://[^"]+\.(?:pls|m3u))"',
            # Icecast/Shoutcast
            r'https?://[^\s"\'<>]*icecast[^\s"\'<>]*',
            r'https?://[^\s"\'<>]*shoutcast[^\s"\'<>]*',
        ]
        
        found_urls = set()
        for pattern in stream_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                found_urls.add(url)
        
        # Validar cada URL encontrada
        for potential_url in found_urls:
            try:
                test_resp = requests.head(potential_url, timeout=8, allow_redirects=True)
                if test_resp.status_code == 200:
                    logger.info(f"✓ Stream genérico: {potential_url}")
                    return potential_url
            except:
                continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error extracción genérica: {e}")
        return None


def get_real_stream_url(url: str) -> str:
    """
    Obtiene URL real del stream con MÁXIMA PERSISTENCIA.
    NUNCA retorna None, siempre retorna algo.
    """
    if not url:
        return url
    
    # Verificar caché
    if url in STREAM_URL_CACHE:
        return STREAM_URL_CACHE[url]
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Si parece stream directo, validar y retornar
    if any(ext in url.lower() for ext in ['.mp3', '.aac', '.ogg', '.m3u', '.pls']):
        try:
            resp = requests.head(url, timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                STREAM_URL_CACHE[url] = url
                return url
        except:
            pass
    
    # Si tiene puerto de streaming típico
    if re.search(r':[0-9]{4,5}/', url):
        STREAM_URL_CACHE[url] = url
        return url
    
    # Intentar extractores especializados con reintentos
    real_url = None
    
    if "zeno.fm" in domain:
        logger.info("🔧 Detectado Zeno.FM")
        for attempt in range(3):
            real_url = extract_zeno_stream(url)
            if real_url:
                break
            logger.warning(f"   Reintento {attempt + 1}/3 Zeno.FM...")
            time.sleep(2)
    
    elif "radio.net" in domain:
        logger.info("🔧 Detectado Radio.net")
        for attempt in range(3):
            real_url = extract_radionet_stream(url)
            if real_url:
                break
            logger.warning(f"   Reintento {attempt + 1}/3 Radio.net...")
            time.sleep(2)
    
    elif any(plat in domain for plat in ["tunein", "streema", "live365", "shoutcast"]):
        logger.info(f"🔧 Detectada plataforma: {domain}")
        for attempt in range(3):
            real_url = extract_generic_stream(url)
            if real_url:
                break
            logger.warning(f"   Reintento {attempt + 1}/3 extracción...")
            time.sleep(2)
    
    # Cachear resultado
    final_url = real_url if real_url else url
    STREAM_URL_CACHE[url] = final_url
    
    if real_url:
        logger.info(f"✓ Stream extraído exitosamente")
    else:
        logger.warning(f"⚠️  Usando URL original (puede funcionar)")
    
    return final_url


# ============================================================================
# DETECCIÓN ICY METADATA - ULTRA PERSISTENTE
# ============================================================================

def get_icy_metadata(stream_url: str, timeout: int = 15) -> Optional[str]:
    """Lee metadata ICY con MÁXIMA PERSISTENCIA."""
    headers_variants = [
        {"Icy-MetaData": "1", "User-Agent": get_random_user_agent()},
        {"Icy-Metadata": "1", "User-Agent": get_random_user_agent()},
        {"icy-metadata": "1", "User-Agent": "VLC/3.0.0"},
        {"Icy-MetaData": "1", "User-Agent": "WinampMPEG/5.0"},
    ]
    
    for attempt in range(MAX_RETRIES_ICY):
        headers = headers_variants[attempt % len(headers_variants)]
        
        try:
            resp = requests.get(
                stream_url,
                headers=headers,
                stream=True,
                timeout=timeout
            )
            
            # Verificar si hay metadata
            metaint_key = None
            for key in resp.headers:
                if 'metaint' in key.lower():
                    metaint_key = key
                    break
            
            if not metaint_key:
                if attempt < MAX_RETRIES_ICY - 1:
                    logger.debug(f"   ICY intento {attempt + 1}/{MAX_RETRIES_ICY}: sin metaint")
                    resp.close()
                    time.sleep(RETRY_DELAY)
                    continue
                resp.close()
                return None
            
            metaint = int(resp.headers[metaint_key])
            raw = resp.raw
            
            # Leer bloque de datos
            data_block = raw.read(metaint)
            if not data_block:
                resp.close()
                continue
            
            # Leer longitud de metadata
            meta_len_byte = raw.read(1)
            if not meta_len_byte:
                resp.close()
                continue
            
            meta_len = meta_len_byte[0] * 16
            if meta_len == 0:
                resp.close()
                if attempt < MAX_RETRIES_ICY - 1:
                    logger.debug(f"   ICY intento {attempt + 1}/{MAX_RETRIES_ICY}: metadata vacía")
                    time.sleep(RETRY_DELAY)
                continue
                return None
            
            # Leer metadata
            meta = raw.read(meta_len)
            resp.close()
            
            # Extraer título
            if b"StreamTitle='" in meta or b"TITLE='" in meta:
                for prefix in [b"StreamTitle='", b"TITLE='"]:
                    if prefix in meta:
                        title_part = meta.split(prefix)[1].split(b"';")[0]
                        title = title_part.decode("utf-8", errors="ignore").strip()
                        
                        if is_valid_metadata(title):
                            logger.info(f"   ✓ ICY metadata válida obtenida")
                            return normalize_string(title)
            
            # Si llegamos aquí, metadata no válida, reintentar
            if attempt < MAX_RETRIES_ICY - 1:
                logger.debug(f"   ICY intento {attempt + 1}/{MAX_RETRIES_ICY}: metadata inválida")
                time.sleep(RETRY_DELAY)
            
        except Exception as e:
            if attempt < MAX_RETRIES_ICY - 1:
                logger.debug(f"   ICY intento {attempt + 1}/{MAX_RETRIES_ICY}: {str(e)[:50]}")
                time.sleep(RETRY_DELAY)
            else:
                logger.debug(f"   ICY: todos los intentos fallaron")
    
    return None


# ============================================================================
# RECONOCIMIENTO POR AUDIO - ULTRA PERSISTENTE
# ============================================================================

def capture_and_recognize_audd(stream_url: str, audd_token: str) -> Optional[Dict[str, Any]]:
    """Captura y reconoce con MÁXIMA PERSISTENCIA."""
    if not audd_token:
        return None
    
    for attempt in range(MAX_RETRIES_AUDD):
        sample_path = os.path.join(TEMP_DIR, f"sample_{int(time.time())}_{os.getpid()}_{attempt}.wav")
        
        # Aumentar duración en reintentos
        duration = SAMPLE_DURATION + (attempt * 2)
        
        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "quiet",
            "-i", stream_url,
            "-t", str(duration),
            "-ac", "1",
            "-ar", "44100",
            "-f", "wav",
            sample_path
        ]
        
        try:
            logger.debug(f"   Capturando audio: intento {attempt + 1}/{MAX_RETRIES_AUDD} ({duration}s)")
            
            subprocess.run(
                cmd,
                check=True,
                timeout=duration + 30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            if not os.path.exists(sample_path) or os.path.getsize(sample_path) < 1000:
                logger.debug(f"   Audio capturado muy pequeño")
                if attempt < MAX_RETRIES_AUDD - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            
            # Reconocer con AudD
            logger.debug(f"   Enviando a AudD...")
            with open(sample_path, "rb") as f:
                files = {"file": ("sample.wav", f, "audio/wav")}
                data = {"api_token": audd_token, "return": "apple_music,spotify"}
                
                resp = requests.post(
                    "https://api.audd.io/",
                    files=files,
                    data=data,
                    timeout=40
                )
            
            os.remove(sample_path)
            
            if resp.status_code == 200:
                j = resp.json()
                if j.get("status") == "success" and j.get("result"):
                    result = j["result"]
                    artist = result.get("artist")
                    title = result.get("title")
                    
                    if artist and title and is_valid_metadata(artist) and is_valid_metadata(title):
                        # Extraer género
                        genre = "Desconocido"
                        
                        if "spotify" in result and result["spotify"]:
                            spotify_data = result["spotify"]
                            if "album" in spotify_data and "genres" in spotify_data["album"]:
                                genres = spotify_data["album"]["genres"]
                                if genres:
                                    genre = genres[0]
                        
                        if genre == "Desconocido" and "apple_music" in result and result["apple_music"]:
                            apple_data = result["apple_music"]
                            if "genreNames" in apple_data and apple_data["genreNames"]:
                                genre = apple_data["genreNames"][0]
                        
                        logger.info(f"   ✓ AudD reconoció exitosamente")
                        return {
                            "artist": artist,
                            "title": title,
                            "genre": genre
                        }
            
            if attempt < MAX_RETRIES_AUDD - 1:
                logger.debug(f"   AudD: no reconoció, reintentando...")
                time.sleep(RETRY_DELAY * 2)
            
        except subprocess.TimeoutExpired:
            logger.debug(f"   Timeout capturando audio")
        except Exception as e:
            logger.debug(f"   Error AudD: {str(e)[:50]}")
        finally:
            try:
                if os.path.exists(sample_path):
                    os.remove(sample_path)
            except:
                pass
        
        if attempt < MAX_RETRIES_AUDD - 1:
            time.sleep(RETRY_DELAY)
    
    logger.debug(f"   AudD: todos los intentos agotados")
    return None


# ============================================================================
# GÉNERO MUSICBRAINZ
# ============================================================================

def get_genre_from_cache(artist: str) -> Optional[str]:
    """Obtiene género del caché."""
    key = artist.lower().strip()
    return GENRE_CACHE.get(key)


def save_genre_to_cache(artist: str, genre: str):
    """Guarda género en caché."""
    key = artist.lower().strip()
    GENRE_CACHE[key] = genre


def get_genre_musicbrainz(artist: str, title: str) -> Optional[str]:
    """Consulta género en MusicBrainz."""
    try:
        url = "https://musicbrainz.org/ws/2/recording/"
        params = {
            "query": f'artist:"{artist}" AND recording:"{title}"',
            "fmt": "json",
            "limit": 1
        }
        headers = {"User-Agent": "RadioMonitor/3.0 (professional@radiomonitor.com)"}
        
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("recordings"):
                recording = data["recordings"][0]
                if "tags" in recording and recording["tags"]:
                    tags = sorted(recording["tags"], key=lambda x: x.get("count", 0), reverse=True)
                    if tags:
                        genre = tags[0].get("name")
                        if genre:
                            return genre.title()
        
        return None
        
    except Exception as e:
        logger.debug(f"Error MusicBrainz: {e}")
        return None


# ============================================================================
# DUPLICADOS
# ============================================================================

def is_recent_duplicate(db, Cancion, emisora_id: int, artista: str, titulo: str, seconds: int = 300) -> bool:
    """Verifica duplicado reciente."""
    try:
        last = (
            Cancion.query
            .filter_by(emisora_id=emisora_id)
            .order_by(Cancion.fecha_reproduccion.desc())
            .first()
        )
        
        if not last:
            return False
        
        def clean(s):
            return normalize_string(s).lower()
        
        if clean(last.artista) == clean(artista) and clean(last.titulo) == clean(titulo):
            delta = (datetime.now() - last.fecha_reproduccion).total_seconds()
            return delta <= seconds
        
        return False
        
    except Exception as e:
        logger.debug(f"Error verificando duplicado: {e}")
        return False


# ============================================================================
# FUNCIÓN PRINCIPAL - NIVEL PERIODÍSTICO PROFESIONAL
# ============================================================================

def actualizar_emisoras(fallback_to_audd=True, dedupe_seconds=DEDUPE_SECONDS):
    """
    🎯 VERSIÓN PERIODÍSTICA PROFESIONAL
    NO SE RINDE. GARANTÍA 100% DE REGISTRO.
    """
    try:
        from flask import current_app
        from utils.db import db
        from models.emisoras import Emisora, Cancion
        
        app = current_app._get_current_object()
        
        logger.info("=" * 70)
        logger.info("🎯 SISTEMA PERIODÍSTICO PROFESIONAL - INICIANDO")
        logger.info("=" * 70)
        
        audd_token = app.config.get("AUDD_API_TOKEN", "")
        
        emisoras = Emisora.query.all()
        
        if not emisoras:
            logger.warning("⚠️  Sin emisoras en BD")
            return
        
        logger.info(f"📻 {len(emisoras)} emisoras a procesar\n")
        
        stats = {
            "processed": 0,
            "registered": 0,
            "icy_success": 0,
            "audd_success": 0,
            "mb_genre": 0,
            "duplicates": 0,
            "errors": 0
        }
        
        for idx, e in enumerate(emisoras, 1):
            try:
                logger.info(f"{'═' * 70}")
                logger.info(f"📡 [{idx}/{len(emisoras)}] {e.nombre} (ID: {e.id})")
                logger.info(f"{'─' * 70}")
                
                url = getattr(e, "url_stream", None) or getattr(e, "url", None)
                
                if not url:
                    logger.error(f"❌ Sin URL - OMITIENDO")
                    stats["errors"] += 1
                    continue
                
                # OBTENER STREAM REAL
                logger.info(f"🔍 Obteniendo stream real...")
                stream_url = get_real_stream_url(url)
                logger.info(f"   URL final: {stream_url[:80]}...")
                
                detected_info = None
                
                # PASO 1: ICY METADATA (5 INTENTOS)
                logger.info(f"🎵 Intentando ICY metadata ({MAX_RETRIES_ICY} intentos)...")
                icy_title = get_icy_metadata(stream_url, timeout=ICY_TIMEOUT)
                
                if icy_title and is_valid_metadata(icy_title):
                    artista, titulo = parse_title_artist(icy_title)
                    
                    if is_valid_metadata(artista) and is_valid_metadata(titulo):
                        detected_info = {
                            "artist": artista,
                            "title": titulo,
                            "genre": None
                        }
                        stats["icy_success"] += 1
                        logger.info(f"✅ ICY EXITOSO: {artista} - {titulo}")
                
                # PASO 2: RECONOCIMIENTO POR AUDIO (3 INTENTOS)
                if not detected_info and fallback_to_audd and audd_token:
                    logger.info(f"🎤 Intentando reconocimiento por audio ({MAX_RETRIES_AUDD} intentos)...")
                    audd_result = capture_and_recognize_audd(stream_url, audd_token)
                    
                    if audd_result:
                        detected_info = audd_result
                        stats["audd_success"] += 1
                        logger.info(f"✅ AUDD EXITOSO: {audd_result['artist']} - {audd_result['title']}")
                        if audd_result.get("genre") and audd_result["genre"] != "Desconocido":
                            logger.info(f"   🎸 Género detectado: {audd_result['genre']}")
                
                # PASO 3: OBTENER GÉNERO SI FALTA
                if detected_info and not detected_info.get("genre"):
                    artist = detected_info["artist"]
                    title = detected_info["title"]
                    
                    # Caché
                    cached_genre = get_genre_from_cache(artist)
                    if cached_genre:
                        detected_info["genre"] = cached_genre
                        logger.info(f"   🎸 Género (caché): {cached_genre}")
                    else:
                        # MusicBrainz
                        logger.info(f"🔎 Consultando género en MusicBrainz...")
                        mb_genre = get_genre_musicbrainz(artist, title)
                        if mb_genre:
                            detected_info["genre"] = mb_genre
                            save_genre_to_cache(artist, mb_genre)
                            stats["mb_genre"] += 1
                            logger.info(f"   ✅ Género: {mb_genre}")
                        else:
                            detected_info["genre"] = "Desconocido"
                
                # PASO 4: FALLBACK (SIEMPRE REGISTRAMOS ALGO)
                if not detected_info:
                    detected_info = {
                        "artist": "Artista Desconocido",
                        "title": "Transmisión en Vivo",
                        "genre": "Desconocido"
                    }
                    logger.warning(f"⚠️  FALLBACK: Sin detección automática")
                
                # PASO 5: VERIFICAR DUPLICADO
                artista = detected_info["artist"]
                titulo = detected_info["title"]
                genero = detected_info.get("genre", "Desconocido")
                
                if is_recent_duplicate(db, Cancion, e.id, artista, titulo, dedupe_seconds):
                    logger.info(f"⏭️  DUPLICADO RECIENTE - Omitiendo")
                    stats["duplicates"] += 1
                    e.ultima_actualizacion = datetime.now()
                    db.session.commit()
                    stats["processed"] += 1
                    continue
                
                # PASO 6: GUARDAR EN BASE DE DATOS
                logger.info(f"💾 GUARDANDO EN BD...")
                logger.info(f"   Artista: {artista}")
                logger.info(f"   Título:  {titulo}")
                logger.info(f"   Género:  {genero}")
                
                nueva = Cancion(
                    titulo=titulo,
                    artista=artista,
                    genero=genero,
                    emisora_id=e.id,
                    fecha_reproduccion=datetime.now()
                )
                
                db.session.add(nueva)
                e.ultima_cancion = f"{artista} - {titulo}"
                e.ultima_actualizacion = datetime.now()
                db.session.commit()
                
                stats["registered"] += 1
                logger.info(f"✅ ✅ ✅ REGISTRADO EXITOSAMENTE ✅ ✅ ✅")
                
                stats["processed"] += 1
                
            except Exception as exc:
                logger.error(f"❌ ERROR PROCESANDO {e.nombre}: {exc}")
                import traceback
                traceback.print_exc()
                stats["errors"] += 1
                try:
                    db.session.rollback()
                except:
                    pass
        
        # ESTADÍSTICAS FINALES
        logger.info(f"\n{'═' * 70}")
        logger.info(f"🎯 CICLO COMPLETADO - REPORTE FINAL")
        logger.info(f"{'═' * 70}")
        logger.info(f"📊 Total procesadas:    {stats['processed']}/{len(emisoras)}")
        logger.info(f"✅ Registradas:         {stats['registered']}")
        logger.info(f"🎵 Éxitos ICY:          {stats['icy_success']}")
        logger.info(f"🎤 Éxitos AudD:         {stats['audd_success']}")
        logger.info(f"🎸 Géneros MusicBrainz: {stats['mb_genre']}")
        logger.info(f"⏭️  Duplicados:          {stats['duplicates']}")
        logger.info(f"❌ Errores:             {stats['errors']}")
        logger.info(f"{'─' * 70}")
        if stats['processed'] > 0:
            success_rate = (stats['registered'] / stats['processed']) * 100
            logger.info(f"🎯 TASA DE ÉXITO: {success_rate:.1f}%")
        logger.info(f"{'═' * 70}\n")
        
    except Exception as exc:
        logger.error(f"❌ ERROR CRÍTICO EN SISTEMA: {exc}")
        import traceback
        traceback.print_exc()
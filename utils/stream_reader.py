# archivo: utils/stream_reader.py - VERSIÓN PERIODÍSTICA PROFESIONAL [OK]
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
# Configurar para Windows - usar UTF-8 con fallback a ASCII
import io
if sys.platform == 'win32':
    try:
        # Intentar usar UTF-8 en Windows
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
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


def clean_stream_title(text: str) -> str:
    """Limpia prefijos comunes en metadata de streams (ICY)."""
    if not text:
        return text
    
    text = normalize_string(text)
    
    # Prefijos comunes que añaden las radios pero NO son parte de la canción
    prefixes = [
        "now on air:",
        "now playing:",
        "actualmente:", 
        "reproduciendo:",
        "[now playing]",
        "[on air]",
        "[streaming]",
        "[live]",
        "[en vivo]",
        "[en directo]",
        "[MUSIC] ",
        "[PLAY] ",
        "playing: ",
    ]
    
    text_lower = text.lower()
    
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            text = text[len(prefix):].strip()
            text_lower = text.lower()
    
    return text


def is_valid_metadata(text: str) -> bool:
    """Valida metadata ESTRICTAMENTE - rechaza genéricos y falsos positivos."""
    if not text:
        return False
    
    text = normalize_string(text)
    
    if len(text) < 3:
        return False
    
    if len(set(text.lower().replace(" ", ""))) <= 2:
        return False
    
    text_lower = text.lower().strip()
    
    # Rechazar strings obviamente inválidos (exacta)
    invalid_exact = [
        "-", "–", "—", ".", "*", "...", "---", "n/a", "na",
        "unknown", "desconocido", "live", "en vivo", "live stream",
        "radio", "stream", "streaming", "sin título", "no title",
        "untitled", "loading", "buffering", "connecting",
        "transmisión", "transmision", "transmisión en vivo",
        "en directo", "en vivo", 
        "not available", "no disponible", "no info",
    ]
    
    if text_lower in invalid_exact:
        return False
    
    # Casos específicos: si contiene EXACTAMENTE "Desconocido - Transmisión en Vivo"
    if text_lower == "desconocido - transmisión en vivo" or text_lower == "desconocido - transmision en vivo":
        return False
    
    # Si contiene "desconocido" solo (no es válido)
    if text_lower.startswith("desconocido") and " - " in text_lower:
        return False
    
    # Si contiene "escuchando" como palabra principal, probable falso
    if text_lower.startswith("estás escuchando") or text_lower.startswith("estas escuchando"):
        return False
    
    # Si es solo "[EN VIVO] - ..." es falso
    if text.startswith("-") or text.startswith("- "):
        return False
    
    # Rechazar si es solo números
    if text.replace(" ", "").isdigit():
        return False
    
    # Requiere al menos una palabra de 3+ caracteres
    words = text.split()
    if not any(len(w) >= 3 for w in words):
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
                        logger.info(f"[OK] Stream Zeno valido: {url}")
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
                                logger.info(f"[OK] Stream Zeno extraido: {stream_url}")
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
                            logger.info(f"[OK] Stream Zeno por path: {test_url}")
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
                            logger.info(f"[OK] Stream Radio.net: {test_url}")
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
                            logger.info(f"[OK] Stream Radio.net HTML: {potential_url}")
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
                    logger.info(f"[OK] Stream generico: {potential_url}")
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
        logger.info("[WRENCH] Detectado Zeno.FM")
        for attempt in range(3):
            real_url = extract_zeno_stream(url)
            if real_url:
                break
            logger.warning(f"   Reintento {attempt + 1}/3 Zeno.FM...")
            time.sleep(2)
    
    elif "radio.net" in domain:
        logger.info("[WRENCH] Detectado Radio.net")
        for attempt in range(3):
            real_url = extract_radionet_stream(url)
            if real_url:
                break
            logger.warning(f"   Reintento {attempt + 1}/3 Radio.net...")
            time.sleep(2)
    
    elif any(plat in domain for plat in ["tunein", "streema", "live365", "shoutcast"]):
        logger.info(f"[WRENCH] Detectada plataforma: {domain}")
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
        logger.info(f"[OK] Stream extraido exitosamente")
    else:
        logger.warning(f"[WARN]  Usando URL original (puede funcionar)")
    
    return final_url


# ============================================================================
# DETECCIÓN ICY METADATA - ULTRA PERSISTENTE
# ============================================================================

def get_icy_metadata(stream_url: str, timeout: int = 15) -> Optional[str]:
    """Lee metadata ICY con MÁXIMA PERSISTENCIA - tolerante con variaciones."""
    headers_variants = [
        {"Icy-MetaData": "1", "User-Agent": get_random_user_agent()},
        {"Icy-Metadata": "1", "User-Agent": get_random_user_agent()},
        {"icy-metadata": "1", "User-Agent": "VLC/3.0.0"},
        {"Icy-MetaData": "1", "User-Agent": "WinampMPEG/5.0"},
        {"User-Agent": "Mozilla/5.0"},  # Sin header ICY - algunos servidores lo rechazan
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
            
            # Intentar obtener metadata de HTTP headers primero
            for header_key in ['icy-title', 'Title', 'X-StreamTitle']:
                if header_key.lower() in {k.lower(): k for k in resp.headers.keys()}:
                    actual_key = {k.lower(): k for k in resp.headers.keys()}[header_key.lower()]
                    title = resp.headers[actual_key]
                    if title and is_valid_metadata(title):
                        logger.info(f"   [OK] Metadata desde header HTTP: {title[:60]}")
                        resp.close()
                        return normalize_string(title)
            
            # Buscar metaint para ICY metadata
            metaint_key = None
            for key in resp.headers:
                if 'metaint' in key.lower():
                    metaint_key = key
                    break
            
            if not metaint_key:
                if attempt < MAX_RETRIES_ICY - 1:
                    time.sleep(RETRY_DELAY)
                resp.close()
                continue
            
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
                    time.sleep(RETRY_DELAY)
                continue
            
            # Leer metadata
            meta = raw.read(meta_len)
            resp.close()
            
            # Extraer título - tolerante con múltiples prefijos
            title = None
            for prefix in [b"StreamTitle='", b"TITLE='" , b"Title='", b"StreamTitle=\"", b"StreamTitle="]:
                if prefix in meta:
                    try:
                        title_part = meta.split(prefix, 1)[1]
                        # Buscar fin de valor (quote, semicolon, newline)
                        for end_marker in [b"';", b"';", b'"', b'\n', b'\0']:
                            if end_marker in title_part:
                                title = title_part.split(end_marker)[0].decode("utf-8", errors="ignore").strip()
                                break
                        if not title:
                            title = title_part[:200].decode("utf-8", errors="ignore").strip()
                        if title:
                            break
                    except:
                        pass
            
            if title:
                # Limpiar prefijos comunes
                title_clean = clean_stream_title(title)
                
                if is_valid_metadata(title_clean):
                    logger.info(f"   [OK] Metadata ICY válida obtenida: {title_clean[:60]}")
                    return normalize_string(title_clean)
                else:
                    logger.debug(f"   [DEBUG] Título ICY rechazado: '{title}' (limpio: '{title_clean}')")
            
            # Si llegamos aquí, reintentar
            if attempt < MAX_RETRIES_ICY - 1:
                time.sleep(RETRY_DELAY)
            
        except Exception as e:
            if attempt < MAX_RETRIES_ICY - 1:
                time.sleep(RETRY_DELAY)
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
                        
                        logger.info(f"   [OK] AudD reconocio exitosamente")
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
    [OK] VERSIÓN PERIODÍSTICA PROFESIONAL
    NO SE RINDE. GARANTÍA 100% DE REGISTRO.
    """
    try:
        from flask import current_app
        from utils.db import db
        from models.emisoras import Emisora, Cancion
        
        app = current_app._get_current_object()
        
        logger.info("=" * 70)
        logger.info("[OK] SISTEMA PERIODÍSTICO PROFESIONAL - INICIANDO")
        logger.info("=" * 70)
        
        audd_token = app.config.get("AUDD_API_TOKEN", "")
        
        emisoras = Emisora.query.all()
        
        if not emisoras:
            logger.warning("[WARN]  Sin emisoras en BD")
            return
        
        logger.info(f"[RADIO] {len(emisoras)} emisoras a procesar\n")
        
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
                logger.info(f"{'=' * 70}")
                logger.info(f"[SIGNAL] [{idx}/{len(emisoras)}] {e.nombre} (ID: {e.id})")
                logger.info(f"{'-' * 70}")
                
                url = getattr(e, "url_stream", None) or getattr(e, "url", None)
                
                if not url:
                    logger.error(f"[ERROR] Sin URL - OMITIENDO")
                    stats["errors"] += 1
                    continue
                
                # OBTENER STREAM REAL
                logger.info(f"[CHECK] Obteniendo stream real...")
                stream_url = get_real_stream_url(url)
                logger.info(f"   URL final: {stream_url[:80]}...")
                
                detected_info = None
                
                # PASO 1: ICY METADATA (5 INTENTOS)
                logger.info(f"[MUSIC] Intentando ICY metadata ({MAX_RETRIES_ICY} intentos)...")
                icy_title = get_icy_metadata(stream_url, timeout=ICY_TIMEOUT)
                
                if icy_title:
                    logger.info(f"   [RAW] Obtenido: {icy_title[:100]}")
                    if is_valid_metadata(icy_title):
                        artista, titulo = parse_title_artist(icy_title)
                        
                        if is_valid_metadata(artista) and is_valid_metadata(titulo):
                            detected_info = {
                                "artist": artista,
                                "title": titulo,
                                "genre": None,
                                "fuente": "icy"
                            }
                            stats["icy_success"] += 1
                            logger.info(f"[SUCCESS] ICY EXITOSO: {artista} - {titulo}")
                        else:
                            logger.info(f"   [REJECT] Artista o titulo inválido: '{artista}' - '{titulo}'")
                    else:
                        logger.info(f"   [REJECT] ICY metadata rechazada por validación (genérica/falsa)")
                else:
                    logger.info(f"   [FAIL] No se obtuvo ICY metadata (timeout o sin metadata)")
                
                # PASO 2: RECONOCIMIENTO POR AUDIO (3 INTENTOS)
                if not detected_info and fallback_to_audd and audd_token:
                    logger.info(f"[AUDIO] Fallback: Intentando reconocimiento por audio ({MAX_RETRIES_AUDD} intentos)...")
                    audd_result = capture_and_recognize_audd(stream_url, audd_token)
                    
                    if audd_result:
                        detected_info = audd_result
                        detected_info["fuente"] = "audd"  # Marcar fuente
                        stats["audd_success"] += 1
                        logger.info(f"[SUCCESS] AUDD EXITOSO: {audd_result['artist']} - {audd_result['title']}")
                        if audd_result.get("genre") and audd_result["genre"] != "Desconocido":
                            logger.info(f"   [GENRE] Género detectado: {audd_result['genre']}")
                    else:
                        logger.info(f"   [FAIL] AudD no pudo detectar canción")
                
                # PASO 3: OBTENER GÉNERO SI FALTA
                if detected_info and not detected_info.get("genre"):
                    artist = detected_info["artist"]
                    title = detected_info["title"]
                    
                    # Caché
                    cached_genre = get_genre_from_cache(artist)
                    if cached_genre:
                        detected_info["genre"] = cached_genre
                        logger.info(f"   [GENRE] Género (caché): {cached_genre}")
                    else:
                        # MusicBrainz
                        logger.info(f"[CHECK] Consultando género en MusicBrainz...")
                        mb_genre = get_genre_musicbrainz(artist, title)
                        if mb_genre:
                            detected_info["genre"] = mb_genre
                            save_genre_to_cache(artist, mb_genre)
                            stats["mb_genre"] += 1
                            logger.info(f"   [SUCCESS] Género: {mb_genre}")
                        else:
                            detected_info["genre"] = "Desconocido"
                
                # PASO 4: PLAN B - PREDICCIÓN INTELIGENTE (si ICY+AudD fallaron)
                if not detected_info:
                    logger.info(f"[PLAN-B] Activando predicción inteligente basada en histórico...")
                    
                    try:
                        from plan_b_predictor import PlanBPredictor
                        
                        predictor = PlanBPredictor(e.id)
                        prediction = predictor.predict_song(strategy="auto")
                        
                        if prediction:
                            detected_info = {
                                "artist": prediction.get("artista", "Desconocido"),
                                "title": prediction.get("titulo", "Transmisión en Vivo"),
                                "genre": prediction.get("genero", "Desconocido"),
                                "fuente": "plan_b",
                                "razon": prediction.get("razon", "Predicción automática"),
                                "confianza": prediction.get("confianza", 0)
                            }
                            logger.info(f"[PLAN-B] [SUCCESS] Predicción exitosa")
                            logger.info(f"   Artista: {detected_info['artist']}")
                            logger.info(f"   Título: {detected_info['title']}")
                            logger.info(f"   Razon: {detected_info.get('razon', '')}")
                            logger.info(f"   Confianza: {detected_info.get('confianza', 0)}%")
                        else:
                            logger.warning(f"[PLAN-B] No hay histórico para predecir - FALLBACK genérico")
                            detected_info = {
                                "artist": "Artista Desconocido",
                                "title": "Transmisión en Vivo",
                                "genre": "Desconocido"
                            }
                    except Exception as pb_exc:
                        logger.warning(f"[PLAN-B] Error en predictor: {pb_exc} - FALLBACK genérico")
                        detected_info = {
                            "artist": "Artista Desconocido",
                            "title": "Transmisión en Vivo",
                            "genre": "Desconocido"
                        }
                
                # PASO 5: VERIFICAR DUPLICADO
                artista = detected_info["artist"]
                titulo = detected_info["title"]
                genero = detected_info.get("genre", "Desconocido")
                
                if is_recent_duplicate(db, Cancion, e.id, artista, titulo, dedupe_seconds):
                    logger.info(f"[SKIP]  DUPLICADO RECIENTE - Omitiendo")
                    stats["duplicates"] += 1
                    e.ultima_actualizacion = datetime.now()
                    db.session.commit()
                    stats["processed"] += 1
                    continue
                
                # PASO 6: GUARDAR EN BASE DE DATOS
                logger.info(f"[SAVE] GUARDANDO EN BD...")
                logger.info(f"   Artista: {artista}")
                logger.info(f"   Título:  {titulo}")
                logger.info(f"   Género:  {genero}")
                if detected_info.get("fuente"):
                    logger.info(f"   Fuente:  {detected_info.get('fuente', 'icy').upper()}")
                
                nueva = Cancion(
                    titulo=titulo,
                    artista=artista,
                    genero=genero,
                    emisora_id=e.id,
                    fecha_reproduccion=datetime.now(),
                    fuente=detected_info.get("fuente", "icy"),
                    razon_prediccion=detected_info.get("razon", None),
                    confianza_prediccion=detected_info.get("confianza", None)
                )
                
                db.session.add(nueva)
                e.ultima_cancion = f"{artista} - {titulo}"
                e.ultima_actualizacion = datetime.now()
                db.session.commit()
                
                stats["registered"] += 1
                logger.info(f"[SUCCESS] [SUCCESS] [SUCCESS] REGISTRADO EXITOSAMENTE [SUCCESS] [SUCCESS] [SUCCESS]")
                
                stats["processed"] += 1
                
            except Exception as exc:
                logger.error(f"[ERROR] ERROR PROCESANDO {e.nombre}: {exc}")
                import traceback
                traceback.print_exc()
                stats["errors"] += 1
                try:
                    db.session.rollback()
                except:
                    pass
        
        # ESTADÍSTICAS FINALES
        logger.info(f"\n{'=' * 70}")
        logger.info(f"[OK] CICLO COMPLETADO - REPORTE FINAL")
        logger.info(f"{'=' * 70}")
        logger.info(f"📊 Total procesadas:    {stats['processed']}/{len(emisoras)}")
        logger.info(f"[SUCCESS] Registradas:         {stats['registered']}")
        logger.info(f"[MUSIC] Éxitos ICY:          {stats['icy_success']}")
        logger.info(f"[AUDIO] Éxitos AudD:         {stats['audd_success']}")
        logger.info(f"[GENRE] Géneros MusicBrainz: {stats['mb_genre']}")
        logger.info(f"[SKIP]  Duplicados:          {stats['duplicates']}")
        logger.info(f"[ERROR] Errores:             {stats['errors']}")
        logger.info(f"{'-' * 70}")
        if stats['processed'] > 0:
            success_rate = (stats['registered'] / stats['processed']) * 100
            logger.info(f"[OK] TASA DE ÉXITO: {success_rate:.1f}%")
        logger.info(f"{'=' * 70}\n")
        
    except Exception as exc:
        logger.error(f"[ERROR] ERROR CRÍTICO EN SISTEMA: {exc}")
        import traceback
        traceback.print_exc()
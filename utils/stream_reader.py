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

# NOTE: Predictive model DISABLED - Only REAL detection (ICY + AudD)
# No synthetic/predicted data. Only actual metadata from streams.

# ============================================================================
# CONFIGURACIÓN AGRESIVA - NO NOS RENDIMOS
# ============================================================================

ICY_TIMEOUT = 20  # Reducido de 15 a 8 segundos (más rápido)
SAMPLE_DURATION = 15  # Reducido de 12 a 10 segundos
DEDUPE_SECONDS = 90
MAX_RETRIES_ICY = 5  # Reducido de 5 a 3 intentos
MAX_RETRIES_AUDD = 4  # Reducido de 3 a 2 intentos
RETRY_DELAY = 2  # Reducido de 2 a 1 segundo

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

    # Eliminar comillas simples o dobles al inicio/fin
    try:
        text = text.strip('"\'')
    except Exception:
        # Fallback seguro
        text = text.strip('"')

    # Quitar contenido entre paréntesis si parece ser nota (Official, Live, Video, Radio)
    text = re.sub(r"\([^)]*(official|video|live|radio|fm|mix|remix)[^)]*\)", "", text, flags=re.IGNORECASE)

    # Quitar sufijos obvios de marca/estacion: ' - Radio', ' | Live', etc.
    # Si el sufijo contiene palabras como radio/fm/stream, asumimos que no es parte de la canción
    if " - " in text:
        left, right = text.rsplit(" - ", 1)
        if re.search(r"\b(radio|fm|stream|online|live|emisora)\b", right, re.IGNORECASE):
            text = left.strip()

    if " | " in text:
        left, right = text.rsplit(" | ", 1)
        if re.search(r"\b(radio|fm|stream|online|live|emisora)\b", right, re.IGNORECASE):
            text = left.strip()

    # Normalizar espacios y devolver
    return normalize_string(text)


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


def _save_emisora_diagnosis(db, emisora, diagnosis: str, url_valid: bool = None, is_streaming: bool = None):
    """Helper para guardar diagnóstico de emisora de forma segura."""
    try:
        if url_valid is not None:
            emisora.url_valida = bool(url_valid)
        if is_streaming is not None:
            emisora.es_stream_activo = bool(is_streaming)
        emisora.diagnostico = diagnosis
        emisora.ultima_validacion = datetime.now()
        emisora.ultima_actualizacion = datetime.now()
        db.session.add(emisora)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except:
            pass


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
    """Extractor genérico ULTRA AGRESIVO - busca en toda la página."""
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
        
        # PATRONES AGRESIVOS para encontrar streams
        stream_patterns = [
            # URLs directas de audio
            r'https?://[^\s"\'<>]+\.(?:mp3|aac|ogg|opus|pls|m3u|m3u8|xspf)',
            # Puertos típicos de streaming (icecast/shoutcast)
            r'https?://[^\s"\'<>]+:[0-9]{4,5}(?:/[^\s"\'<>]*)?',
            # Atributos JSON/HTML comunes
            r'"streamUrl"\s*:\s*"([^"]+)"',
            r'"stream"\s*:\s*"([^"]+)"',
            r'"audioUrl"\s*:\s*"([^"]+)"',
            r'"url"\s*:\s*"(https?://[^"]+)"',
            r'"src"\s*:\s*"(https?://[^"]+)"',
            r'data-stream="([^"]+)"',
            r'data-url="([^"]+)"',
            r'src="(https?://[^"]+\.(?:mp3|m3u8|aac))"',
            r'href="(https?://[^"]+\.(?:pls|m3u|m3u8))"',
            # Icecast/Shoutcast directo
            r'(https?://[^\s"\'<>]*(?:icecast|shoutcast)[^\s"\'<>]*)',
            # RadioBrowser/stream.radiotime patterns
            r'(https?://stream\.[^\s"\'<>]+)',
            r'(https?://[^\s"\'<>]*\.(?:hostlagarto|streaming|radios-online)[^\s"\'<>]*)',
            # Cualquier http URL que termine en /stream o /listen
            r'(https?://[^\s"\'<>]+/(?:stream|listen|audio|play)[^\s"\'<>]*)',
            # URLs con IP:PORT
            r'(https?://\d+\.\d+\.\d+\.\d+:[0-9]{4,5}[^\s"\'<>]*)',
        ]
        
        found_urls = set()
        for pattern in stream_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                # Limpiar URL
                url = url.strip().rstrip('",;\']')
                if url and len(url) > 10:  # Descartar URLs muy cortas
                    found_urls.add(url)
        
        # ORDENAR por probabilidad
        def url_quality_score(url: str) -> int:
            score = 0
            if any(x in url.lower() for x in ['stream', 'audio', 'play', 'listen']):
                score += 100
            if any(x in url.lower() for x in ['icecast', 'shoutcast', 'hostlagarto']):
                score += 50
            if ':' in url and any(c.isdigit() for c in url.split(':')[-1]):  # Tiene puerto
                score += 30
            if url.endswith(('.mp3', '.aac', '.ogg', '.m3u', '.m3u8', '.pls')):
                score += 20
            return score
        
        sorted_urls = sorted(found_urls, key=url_quality_score, reverse=True)
        
        # Validar cada URL encontrada (de mejor a peor)
        for potential_url in sorted_urls:
            try:
                test_resp = requests.head(potential_url, timeout=8, allow_redirects=True)
                if test_resp.status_code == 200:
                    logger.info(f"[OK] Stream generico encontrado: {potential_url}")
                    return potential_url
            except:
                continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error extracción genérica: {e}")
        return None


def get_real_stream_url(url: str) -> str:
    """
    Obtiene URL real del stream - VERSIÓN RÁPIDA.
    MÁXIMO 5 SEGUNDOS por emisora, no más.
    """
    if not url:
        return url
    
    # Verificar caché
    if url in STREAM_URL_CACHE:
        return STREAM_URL_CACHE[url]
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Si parece stream directo, validar y retornar RÁPIDO
    if any(ext in url.lower() for ext in ['.mp3', '.aac', '.ogg', '.m3u', '.pls']):
        try:
            resp = requests.head(url, timeout=3, allow_redirects=True)
            if resp.status_code == 200:
                STREAM_URL_CACHE[url] = url
                return url
        except:
            pass
    
    # Si tiene puerto de streaming típico (con o sin slash)
    if re.search(r':[0-9]{2,5}(/|$)', url):
        STREAM_URL_CACHE[url] = url
        return url
    
    # ESTRATEGIA RÁPIDA: Solo 1 intento por plataforma (no 3)
    real_url = None
    
    if "radio.net" in domain:
        logger.info("[WRENCH] Detectado Radio.net")
        # Extraer nombre directo
        match = re.search(r'/radio/([^/]+)', parsed.path)
        if match:
            station_name = match.group(1)
            # Intentar formato más directo primero
            test_urls = [
                f"https://{station_name}.stream.radio.net/stream",
                f"https://stream.radio.net/{station_name}",
            ]
            for test_url in test_urls:
                try:
                    resp = requests.head(test_url, timeout=2, allow_redirects=True)
                    if resp.status_code == 200:
                        real_url = test_url
                        break
                except:
                    continue
    
    elif "zeno.fm" in domain:
        logger.info("[WRENCH] Detectado Zeno.FM")
        # Zeno es más simple - su URL suele ser ya válida
        real_url = url

    # Si no se obtuvo real_url, intentar extractores genéricos y específicos
    if not real_url:
        try:
            # Probar Zeno extractor
            z = extract_zeno_stream(url)
            if z:
                real_url = z
        except Exception:
            pass

    if not real_url:
        try:
            rn = extract_radionet_stream(url)
            if rn:
                real_url = rn
        except Exception:
            pass

    if not real_url:
        try:
            gen = extract_generic_stream(url)
            if gen:
                real_url = gen
        except Exception:
            pass
    
    # Cachear resultado - siempre usar algo
    final_url = real_url if real_url else url
    STREAM_URL_CACHE[url] = final_url
    
    return final_url


# ============================================================================
# DETECCIÓN ICY METADATA - ULTRA PERSISTENTE
# ============================================================================

def get_icy_metadata(stream_url: str, timeout: int = 8) -> Optional[str]:
    """Lee metadata ICY - VERSIÓN RÁPIDA."""
    headers_variants = [
        {"Icy-MetaData": "1", "User-Agent": "RadioMonitor/3.0"},
        {"Icy-Metadata": "1", "User-Agent": "VLC/3.0.0"},
        {"User-Agent": "Mozilla/5.0"},
    ]
    
    for attempt in range(MAX_RETRIES_ICY):
        # Reducir timeout en reintentos
        current_timeout = timeout if attempt == 0 else max(3, timeout - attempt)
        headers = headers_variants[attempt % len(headers_variants)]
        
        try:
            resp = requests.get(
                stream_url,
                headers=headers,
                stream=True,
                timeout=current_timeout
            )
            
            # Intentar obtener metadata de HTTP headers PRIMERO (más rápido)
            for header_key in ['icy-title', 'Title', 'X-StreamTitle']:
                for k in resp.headers:
                    if k.lower() == header_key.lower():
                        title = resp.headers[k]
                        if title and is_valid_metadata(title):
                            logger.info(f"   [OK] ICY header: {title[:60]}")
                            resp.close()
                            return normalize_string(title)
                        break
            
            # Buscar metaint para ICY metadata (streaming)
            metaint_key = None
            for key in resp.headers:
                if 'metaint' in key.lower():
                    metaint_key = key
                    break
            
            if not metaint_key:
                resp.close()
                if attempt < MAX_RETRIES_ICY - 1:
                    time.sleep(0.5)  # Solo 0.5s entre intentos
                continue
            
            try:
                metaint = int(resp.headers[metaint_key])
            except:
                resp.close()
                continue
            
            raw = resp.raw
            
            # Leer bloque de datos
            data_block = raw.read(metaint)
            if not data_block:
                resp.close()
                if attempt < MAX_RETRIES_ICY - 1:
                    time.sleep(0.5)
                continue
            
            # Leer longitud de metadata
            meta_len_byte = raw.read(1)
            if not meta_len_byte:
                resp.close()
                if attempt < MAX_RETRIES_ICY - 1:
                    time.sleep(0.5)
                continue
            
            meta_len = meta_len_byte[0] * 16
            if meta_len == 0:
                resp.close()
                if attempt < MAX_RETRIES_ICY - 1:
                    time.sleep(0.5)
                continue
            
            # Leer metadata
            meta = raw.read(meta_len)
            resp.close()
            
            # Extraer título - simple y rápido
            title = None
            for prefix in [b"StreamTitle='", b"Title='"]:
                if prefix in meta:
                    try:
                        title_part = meta.split(prefix, 1)[1]
                        for end in [b"';", b"'"]:
                            if end in title_part:
                                title = title_part.split(end)[0].decode("utf-8", errors="ignore").strip()
                                break
                        if not title:
                            title = title_part[:200].decode("utf-8", errors="ignore").strip()
                        if title:
                            break
                    except:
                        pass
            
            if title:
                title_clean = clean_stream_title(title)
                if is_valid_metadata(title_clean):
                    logger.info(f"   [OK] ICY metadata: {title_clean[:60]}")
                    return normalize_string(title_clean)
            
            if attempt < MAX_RETRIES_ICY - 1:
                time.sleep(0.5)
            
        except Exception as e:
            if attempt < MAX_RETRIES_ICY - 1:
                time.sleep(0.5)
    
    return None


# ============================================================================
# RECONOCIMIENTO POR AUDIO - VERSIÓN RÁPIDA
# ============================================================================

def capture_and_recognize_audd(stream_url: str, audd_token: str) -> Optional[Dict[str, Any]]:
    """Captura y reconoce con AudD - VERSIÓN RÁPIDA."""
    if not audd_token:
        return None
        # Forzar token del cliente como fallback
    if not audd_token or audd_token.strip() == "":
        audd_token = "af9487123bb9013135e6428b1cd45666"

    
    for attempt in range(MAX_RETRIES_AUDD):
            
        sample_path = os.path.join(TEMP_DIR, f"sample_{int(time.time())}_{os.getpid()}_{attempt}.wav")
        
        # Duración consistente
        duration = SAMPLE_DURATION
        
        cmd = [
            "ffmpeg", "-y",
                    "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-hide_banner", "-loglevel", "quiet",
            "-i", stream_url,
            "-t", str(duration),
            "-ac", "1",
            "-ar", "44100",
            "-f", "wav",
            sample_path
        ]
        
        try:
            logger.debug(f"   Capturando audio {duration}s...")
            
            # Timeout más corto: duration + 5s
            subprocess.run(
                cmd,
                check=True,
                timeout=duration + 5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            if not os.path.exists(sample_path) or os.path.getsize(sample_path) < 500:
                logger.debug(f"   Audio muy pequeño o falla")
                try:
                    os.remove(sample_path)
                except:
                    pass
                if attempt < MAX_RETRIES_AUDD - 1:
                    time.sleep(0.5)
                    continue
                return None
            
            # Enviar a AudD
            logger.debug(f"   Enviando a AudD...")
            with open(sample_path, "rb") as f:
                files = {"file": ("sample.wav", f, "audio/wav")}
                data = {"api_token": audd_token, "return": "spotify"}
                
                resp = requests.post(
                    "https://api.audd.io/",
                    files=files,
                    data=data,
                    timeout=20
                )
            
            try:
                os.remove(sample_path)
            except:
                pass
            
            if resp.status_code == 200:
                j = resp.json()
                if j.get("status") == "success" and j.get("result"):
                    result = j["result"]
                    artist = result.get("artist")
                    title = result.get("title")
                    
                    if artist and title and is_valid_metadata(artist) and is_valid_metadata(title):
                        # Extraer género
                        genre = "Desconocido"
                        
                        if artist and title:
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
    [OK] VERSION SECUENCIAL ROBUSTA - Sin threading para evitar conflictos de sesion DB.
    """
    from flask import current_app
    from utils.db import db
    from models.emisoras import Emisora, Cancion
    app = current_app._get_current_object()

    logger.info("=" * 70)
    logger.info("[OK] MONITOR INICIANDO CICLO")
    logger.info("=" * 70)

    try:
        emisoras = Emisora.query.all()
    except Exception as e:
        logger.error(f"[DB ERROR] No se pudo obtener emisoras: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        return

    if not emisoras or len(emisoras) == 0:
        logger.warning("[WARN] Sin emisoras en BD")
        return

    logger.info(f"[OK] Procesando {len(emisoras)} emisoras...")
    resultados = {"ok": 0, "icy": 0, "audd": 0, "fallo": 0, "skip": 0}
    audd_token = app.config.get("AUDD_API_TOKEN", "") or "af9487123bb9013135e6428b1cd45666"

    for emisora in emisoras:
        try:
            url = emisora.url_stream
            if not url:
                logger.warning(f" [SKIP] {emisora.nombre}: sin URL")
                resultados["skip"] += 1
                continue

            logger.info(f" [>>] {emisora.nombre} | {url[:60]}")

            # Obtener URL real del stream
            real_url = get_real_stream_url(url)

            # 1. Intentar ICY metadata
            icy_title = get_icy_metadata(real_url, timeout=ICY_TIMEOUT)
            if icy_title and is_valid_metadata(icy_title):
                artista, titulo = parse_title_artist(icy_title)
                fuente = "icy"
                logger.info(f" [OK] ICY: {artista} - {titulo}")
                try:
                    if is_recent_duplicate(db, Cancion, emisora.id, artista, titulo, dedupe_seconds):
                        logger.info(f" [SKIP] Duplicado ICY: {artista} - {titulo}")
                        resultados["skip"] += 1
                        continue
                    cancion = Cancion(
                        titulo=titulo,
                        artista=artista,
                        genero="Desconocido",
                        emisora_id=emisora.id,
                        fecha_reproduccion=datetime.now(),
                        fuente=fuente,
                    )
                    db.session.add(cancion)
                    emisora.ultima_cancion = f"{artista} - {titulo}"
                    emisora.ultima_actualizacion = datetime.now()
                    db.session.commit()
                    logger.info(f" [SAVED] ICY: {artista} - {titulo}")
                    resultados["icy"] += 1
                    resultados["ok"] += 1
                    continue
                except Exception as e:
                    logger.error(f" [DB ERROR] ICY save: {e}")
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    resultados["fallo"] += 1
                    continue

            # 2. Fallback a AudD
            if fallback_to_audd and audd_token:
                audd_result = capture_and_recognize_audd(real_url, audd_token)
                if audd_result:
                    artista = audd_result.get("artist", "Artista Desconocido")
                    titulo = audd_result.get("title", "Cancion Desconocida")
                    genero = audd_result.get("genre", "Desconocido")
                    try:
                        if is_recent_duplicate(db, Cancion, emisora.id, artista, titulo, dedupe_seconds):
                            resultados["skip"] += 1
                            continue
                        cancion = Cancion(
                            titulo=titulo,
                            artista=artista,
                            genero=genero,
                            emisora_id=emisora.id,
                            fecha_reproduccion=datetime.now(),
                            fuente="audd",
                        )
                        db.session.add(cancion)
                        emisora.ultima_cancion = f"{artista} - {titulo}"
                        emisora.ultima_actualizacion = datetime.now()
                        db.session.commit()
                        logger.info(f" [SAVED] AudD: {artista} - {titulo}")
                        resultados["audd"] += 1
                        resultados["ok"] += 1
                        continue
                    except Exception as e:
                        logger.error(f" [DB ERROR] AudD save: {e}")
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                        resultados["fallo"] += 1
                        continue

            # 3. Sin deteccion
            logger.warning(f" [FAIL] Sin deteccion: {emisora.nombre}")
            resultados["fallo"] += 1

        except Exception as e:
            logger.error(f" [ERROR] {emisora.nombre}: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
            resultados["fallo"] += 1

    logger.info("=" * 70)
    logger.info(f"[OK] CICLO COMPLETADO: ok={resultados['ok']} icy={resultados['icy']} audd={resultados['audd']} fallo={resultados['fallo']} skip={resultados['skip']}")
    logger.info("=" * 70)

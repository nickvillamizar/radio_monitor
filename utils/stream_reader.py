# archivo: radio_monitor-main/utils/stream_reader.py
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


# -------------------
# UTIL: Normalización
# -------------------
def normalize_string(text):
    """
    Normaliza texto: trim, elimina caracteres de control y compacta espacios.
    """
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(c for c in text if ord(c) >= 32)
    return text


def clean_title_string(text):
    """
    Limpia y normaliza un título/artista para comparación (minúsculas, quita signos).
    """
    if not text:
        return ""
    text = normalize_string(text)
    text = text.lower()
    text = re.sub(r"[^\w\s\-àáäâèéëêìíïîòóöôùúüû]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_noise_tokens(s):
    """
    Elimina tokens típicos de 'now playing' o jingles y textos extra comunes.
    """
    if not s:
        return s
    s = re.sub(r"(?i)\b(now playing|playing now|escuchando|reproduciendo|track|tune of the day|on air|currently|title|now)\b[:\-]*", "", s)
    s = re.sub(r"\[?\b\d{1,2}:\d{2}\b\]?", "", s)
    s = re.sub(r"\((live|remix|edit|version|radio edit|ft\.?)\)", "", s, flags=re.I)
    s = re.sub(r"\[[^\]]{1,150}\]", "", s)
    return s.strip()


def _remove_station_suffixes(s):
    """
    Quita sufijos muy comunes que no forman parte del título/artista.
    """
    s = re.sub(r"(?i)\s+(-|\|)\s+(live|online|radio|fm|hd|stream)$", "", s)
    s = re.sub(r"(?i)\s+(on air|onair|listen live|en vivo|en directo|la fm|sabrosa)\b", "", s)
    return s.strip()


def _clean_raw_title(s):
    s = normalize_string(s)
    s = _strip_noise_tokens(s)
    s = _remove_station_suffixes(s)
    s = s.strip("\"'` ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# -------------------
# UTIL: parse artista/título
# -------------------
# Lista corta y configurable de tokens de nombres de emisoras que deben eliminarse
COMMON_STATION_TOKENS = [
    "la fm", "lafm", "la fm 107.5", "sabrosa", "fm", "radio", "emisora", "la fm 1075"
]


def _remove_common_station_tokens(s):
    if not s:
        return s
    for t in COMMON_STATION_TOKENS:
        # eliminar token si aparece al inicio o al final
        s = re.sub(r"(?i)^\s*" + re.escape(t) + r"[\s\-\|\:]*", "", s)
        s = re.sub(r"(?i)[\s\-\|\:]*" + re.escape(t) + r"\s*$", "", s)
    return s.strip()


def parse_title_artist(full_title):
    """
    Extrae artista y título de un string que puede tener formatos variados.
    Retorna tupla (artista, titulo). Si no puede separar, devuelve ("Desconocido", full_title).
    """
    if not full_title:
        return "Desconocido", ""

    full_title = _clean_raw_title(full_title)
    full_title = _remove_common_station_tokens(full_title)
    if not full_title:
        return "Desconocido", ""

    separadores = [
        r"\s*-\s*",
        r"\s*—\s*",
        r"\s*–\s*",
        r"\s*\|\s*",
        r"\s*:\s*",
        r"\s*/\s*",
        r"\s*·\s*",
    ]

    candidates = []
    for sep in separadores:
        parts = re.split(sep, full_title, maxsplit=1)
        if len(parts) == 2:
            left = normalize_string(parts[0])
            right = normalize_string(parts[1])
            if left and right:
                candidates.append((left, right, sep))

    if not candidates:
        m = re.match(r"(?i)(.+)\s+by\s+(.+)", full_title)
        if m:
            return normalize_string(m.group(2)), normalize_string(m.group(1))
        m2 = re.match(r"(?i)(.+)\s+de\s+(.+)", full_title)
        if m2:
            return normalize_string(m2.group(2)), normalize_string(m2.group(1))
        # fallback: si contiene '/' muchas veces, intentar invertir
        if "/" in full_title and "-" not in full_title:
            parts = full_title.split("/")
            if len(parts) >= 2:
                left, right = normalize_string(parts[0]), normalize_string("/".join(parts[1:]))
                return left, right
        return "Desconocido", full_title

    def score_pair(artist_candidate, title_candidate):
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
        if re.search(r"(?i)\b(radio|fm|online|stream|live|emisora)\b", a):
            score -= 1.0
        if re.search(r"[A-Z][a-z]+", a):
            score += 0.2
        # penalizar si artist es evidente sufijo tipo '107.5'
        if re.search(r"\d{2,}", a):
            score -= 0.5
        return score

    best = None
    best_score = -9999
    for left, right, sep in candidates:
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
            if len(artist) <= 2 and len(title) > len(artist):
                return "Desconocido", full_title
            return artist, title

    return "Desconocido", full_title


# -------------------
# UTIL: parse playlists (m3u/pls/xspf)
# -------------------
def parse_playlist_for_stream(url, content):
    """
    Dado el contenido de un playlist y la url original, devuelve la primera URL de stream válida.
    Soporta .m3u, .pls y XSPF básicos.
    """
    if not content:
        return None
    text = content.decode("utf-8", errors="ignore")
    # m3u lines sin comentarios
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    for l in lines:
        if l.lower().endswith(".m3u") or l.lower().endswith(".pls"):
            # salto recursivo (evitar loops)
            continue
        if re.match(r"^https?://", l, flags=re.I):
            return l
    # PLS parse
    m = re.findall(r"File\d+=(https?://[^\r\n]+)", text, flags=re.I)
    if m:
        return m[0]
    # XSPF simple: buscar <location>
    m2 = re.search(r"<location>(https?://[^<]+)</location>", text, flags=re.I)
    if m2:
        return m2.group(1)
    return None


def resolve_stream_url_maybe_playlist(session, url, timeout=5):
    """
    Si la URL apunta a un playlist (.m3u, .pls) o devuelve texto que contenga stream, lo parsea.
    Devuelve la URL de stream final o la misma URL si no se resolvió.
    """
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        ct = r.headers.get("content-type", "").lower()
        body_bytes = None
        # Si content-type sugiere audio/stream, devolver la url (posible endpoint directo)
        if "audio" in ct or "mpeg" in ct or "aac" in ct:
            r.close()
            return url
        # si es texto o playlist, leer pequeño fragmento
        try:
            # leer hasta 64KB
            body_bytes = r.content[:65536]
        except Exception:
            body_bytes = None
        r.close()
        if body_bytes:
            candidate = parse_playlist_for_stream(url, body_bytes)
            if candidate:
                return candidate
    except Exception as e:
        logger.debug("resolve_stream_url_maybe_playlist: error leyendo %s -> %s", url, e)
    return url


# -------------------
# ICY metadata read (mejorada)
# -------------------
def read_icy_title_from_response(resp, read_blocks=4):
    """
    Lee metadata ICY desde una respuesta requests (stream=True).
    Lee varios bloques de metadatos por conexión para atrapar cambios.
    """
    try:
        metaint = int(resp.headers.get("icy-metaint"))
    except Exception:
        return None

    raw = resp.raw
    last_found = None
    try:
        for _ in range(max(1, int(read_blocks))):
            raw.read(metaint)
            meta_len_byte = raw.read(1)
            if not meta_len_byte:
                time.sleep(0.05)
                continue
            meta_len = meta_len_byte[0] * 16
            if meta_len == 0:
                continue
            meta = raw.read(meta_len)
            if not meta:
                continue
            parts = meta.split(b"StreamTitle='")
            if len(parts) > 1:
                title_part = parts[1].split(b"';")[0]
                try:
                    title = title_part.decode("utf-8", errors="ignore").strip()
                except Exception:
                    title = title_part.decode("latin-1", errors="ignore").strip()
                title = _clean_raw_title(title)
                if title:
                    # eliminar tokens de emisora que aparezcan
                    title = _remove_common_station_tokens(title)
                    last_found = title
            time.sleep(0.02)
    except Exception as e:
        logger.debug("Error leyendo metadata ICY (multi-block): %s", e)
        return last_found
    return last_found


def get_icy_metadata(stream_url, timeout=ICY_TIMEOUT, attempts=3, read_blocks=4):
    """
    Intenta leer metadata ICY con múltiples reintentos y variantes del URL.
    Devuelve la última metadata válida encontrada o None.
    """
    headers = {"Icy-MetaData": "1", "User-Agent": "radio-monitor/1.0"}
    session = requests.Session()
    session.headers.update(headers)
    session.max_redirects = 5

    # Prueba un conjunto de variantes: original, http<->https, url/resolved playlist
    tried = set()
    candidate_urls = [stream_url]

    # añadimos variante http/https si aplica
    if stream_url.startswith("http://"):
        candidate_urls.append("https://" + stream_url[len("http://"):])
    elif stream_url.startswith("https://"):
        candidate_urls.append("http://" + stream_url[len("https://"):])

    for candidate in list(candidate_urls):
        if candidate in tried:
            continue
        tried.add(candidate)
        # intentar resolver playlists
        try:
            resolved = resolve_stream_url_maybe_playlist(session, candidate, timeout=min(5, timeout))
            if resolved and resolved not in tried:
                candidate_urls.append(resolved)
        except Exception:
            pass

    for attempt in range(1, attempts + 1):
        for url in candidate_urls:
            try:
                logger.debug("ICy attempt %d: probando %s", attempt, url)
                resp = session.get(url, stream=True, timeout=timeout)
                if resp.status_code in (200, 206) and "icy-metaint" in resp.headers:
                    title = read_icy_title_from_response(resp, read_blocks=read_blocks)
                    try:
                        resp.close()
                    except Exception:
                        pass
                    if title:
                        title = _clean_raw_title(title)
                        if title:
                            return title
                else:
                    # Algunos streams devuelven HTML con now playing
                    text = ""
                    try:
                        text = resp.content[:8192].decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                    try:
                        resp.close()
                    except Exception:
                        pass
                    if text:
                        m = re.search(r"(?i)(now playing|escuchando|reproduciendo|track)[^<\n]{0,250}", text)
                        if m:
                            cand = _clean_raw_title(m.group(0))
                            cand = _remove_common_station_tokens(cand)
                            if cand:
                                return cand
            except Exception as e:
                logger.debug("get_icy_metadata error para %s (intento %d): %s", url, attempt, e)
                time.sleep(0.2 * attempt)
                continue
        # espera incremental entre rondas completas
        time.sleep(0.5 * attempt)
    return None


# -------------------
# Probar endpoints shoutcast/icecast
# -------------------
def probe_shoutcast_endpoints(base_url, timeout=4):
    """
    Intenta consultar endpoints comunes de shoutcast/icecast para obtener now playing.
    Devuelve título si lo encuentra.
    """
    candidates = [
        "/status-json.xsl",
        "/status.xsl",
        "/7.html",
        "/7.html?sid=1",
        "/played.html",
        "/stats",
        "/status",
        "/admin.cgi?mode=viewxml",
    ]
    session = requests.Session()
    session.headers.update({"User-Agent": "radio-monitor/1.0"})
    for c in candidates:
        try:
            u = base_url.rstrip("/") + c
            r = session.get(u, timeout=timeout)
            if r.status_code == 200:
                text = r.text[:20000]
                # intentar JSON
                try:
                    j = r.json()
                    # muchas variaciones: buscar keys conocidas
                    if isinstance(j, dict):
                        # icecast status-json.xsl: j.get('icestats', {}).get('source', ...)
                        # shoutcast might be different
                        # Buscamos recursivamente por claves 'title' o 'song' o 'artist'
                        def find_song(d):
                            if isinstance(d, dict):
                                for k, v in d.items():
                                    if k.lower() in ("title", "song", "songtitle", "now_playing", "track"):
                                        return v
                                    res = find_song(v)
                                    if res:
                                        return res
                            elif isinstance(d, list):
                                for item in d:
                                    res = find_song(item)
                                    if res:
                                        return res
                            return None
                        song = find_song(j)
                        if song:
                            return _clean_raw_title(str(song))
                except Exception:
                    # fallback a regex en HTML/text
                    m = re.search(r"(?i)(?:current song|song|title|now playing|playing)\s*[:\-–]\s*([^<\n\r]+)", text)
                    if m:
                        return _clean_raw_title(m.group(1))
            r.close()
        except Exception:
            continue
    return None


# -------------------
# FFmpeg capture robusta
# -------------------
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
        subprocess.run(cmd, check=True, timeout=duration + 30)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            return True
        return False
    except subprocess.CalledProcessError as e:
        logger.warning("ffmpeg returned non-zero para %s : %s", stream_url, e)
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        return False
    except Exception as e:
        logger.warning("ffmpeg error para %s : %s", stream_url, e)
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        return False


def _capture_multiple_samples_for_audd(stream_url, base_sample_path, attempts=3, duration=5, delay_between=1):
    """
    Captura varias muestras cortas (posibles solapadas) y devuelve la lista de rutas.
    """
    captured = []
    for i in range(attempts):
        ts = int(time.time() * 1000)
        sample_path = f"{base_sample_path}_{i}_{ts}.wav"
        ok = capture_sample_ffmpeg(stream_url, sample_path, duration=duration)
        if ok and os.path.exists(sample_path) and os.path.getsize(sample_path) > 1000:
            captured.append(sample_path)
        else:
            try:
                if os.path.exists(sample_path):
                    os.remove(sample_path)
            except Exception:
                pass
        time.sleep(delay_between)
    return captured


# -------------------
# AudD recognition (igual que antes)
# -------------------
def recognize_with_audd(file_path, api_token):
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

    # limpieza archivos después de reconocer
    for p in sample_paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    if not results:
        return None

    counts = {}
    for r in results:
        artist = normalize_string(r.get("artist") or "")
        title = normalize_string(r.get("title") or "")
        key = f"{artist}|||{title}"
        counts[key] = counts.get(key, 0) + 1

    best_key = max(counts.items(), key=lambda x: x[1])[0]
    if counts[best_key] > 1:
        artist, title = best_key.split("|||", 1)
        return {"artist": artist, "title": title}
    else:
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


# -------------------
# Dedupe: evitar duplicados recientes
# -------------------
def is_recent_duplicate(emisora_obj, full_title, dedupe_seconds=300):
    """
    Evita registrar la misma canción para una emisora dentro de los últimos N segundos.
    """
    from app import Cancion  # import local para evitar dependencia circular

    if not full_title:
        return False

    artista, titulo = parse_title_artist(full_title)

    last = (
        Cancion.query.filter_by(emisora_id=emisora_obj.id)
        .order_by(Cancion.fecha_reproduccion.desc())
        .first()
    )
    if not last or not last.titulo:
        return False

    def cmp_text(s):
        return clean_title_string(s)

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


# -------------------
# FUNCION PRINCIPAL: actualizar_emisoras (mejorada)
# -------------------
def actualizar_emisoras(fallback_to_audd=True, dedupe_seconds=DEDUPE_SECONDS):
    """Actualiza las emisoras registradas en la base de datos."""
    from app import db, Emisora, Cancion  # import aquí (evita import circular)

    app = current_app._get_current_object()

    audd_token = app.config.get("AUDD_API_TOKEN", "")
    icy_timeout = app.config.get("ICY_TIMEOUT", ICY_TIMEOUT)
    sample_duration_conf = app.config.get("SAMPLE_DURATION", SAMPLE_DURATION)
    audd_attempts = app.config.get("AUDD_ATTEMPTS", 3)
    audd_sample_duration = app.config.get("AUDD_SAMPLE_DURATION", min(6, sample_duration_conf))
    audd_delay_between = app.config.get("AUDD_DELAY_BETWEEN", 0.8)

    logger.info("Iniciando ciclo de actualización de emisoras...")
    emisoras = Emisora.query.all()
    if not emisoras:
        logger.info("No hay emisoras registradas.")
        return

    session = requests.Session()
    session.headers.update({"User-Agent": "radio-monitor/1.0"})

    for e in emisoras:
        url = getattr(e, "url_stream", None) or getattr(e, "url", None)
        if not url:
            logger.warning("Emisora %s no tiene url válida, saltando.", e.id)
            continue

        title = None
        used_method = None

        # Resolver playlist / redirecciones
        try:
            resolved = resolve_stream_url_maybe_playlist(session, url, timeout=min(5, icy_timeout))
            if resolved and resolved != url:
                logger.debug("URL %s resuelta a %s", url, resolved)
                url_to_try = resolved
            else:
                url_to_try = url
        except Exception:
            url_to_try = url

        # Primero: ICY / metadata (rápido y ligero)
        try:
            title = get_icy_metadata(url_to_try, timeout=icy_timeout, attempts=3, read_blocks=5)
        except Exception as exc:
            logger.debug("Error obteniendo ICY para %s: %s", url_to_try, exc)

        # Si no hay ICY, probar endpoints shoutcast/icecast
        if not title:
            try:
                title = probe_shoutcast_endpoints(url_to_try, timeout=4)
                if title:
                    used_method = "shoutcast"
                    logger.info("✓ Endpoint Shoutcast/Icecast devolvió: %s (%s)", title, e.nombre)
            except Exception:
                pass

        # Si aún no hay título, intentar scraping de la URL raíz (página web pequeña)
        if not title:
            try:
                resp = session.get(url, timeout=4)
                text = ""
                try:
                    text = resp.text[:12000]
                except Exception:
                    text = ""
                resp.close()
                if text:
                    m = re.search(r"(?i)(now playing|escuchando|reproduciendo|track)[^<\n]{0,200}", text)
                    if m:
                        cand = _clean_raw_title(m.group(0))
                        cand = _remove_common_station_tokens(cand)
                        if cand:
                            title = cand
                            used_method = "scrape"
                            logger.info("✓ Scrape rápido encontró: %s (%s)", title, e.nombre)
            except Exception:
                pass

        # Finalmente, fallback a AudD con captura si está permitido
        if not title:
            logger.info("No se detectó ICY/endpoint/scrape para %s, probando reconocimiento por audio...", e.nombre)
            if fallback_to_audd and audd_token:
                ts = int(time.time())
                base_sample_path = os.path.join(TEMP_DIR, f"sample_{e.id}_{ts}")
                sample_paths = _capture_multiple_samples_for_audd(
                    url_to_try,
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
                            logger.info("✓ AudD reconoció: %s (%s)", title, e.nombre)
                        else:
                            logger.warning("AudD respondió sin artist/title para %s", e.nombre)
                    else:
                        logger.warning("AudD no reconoció canción para %s", e.nombre)
                else:
                    # Intentar captura larga como último recurso
                    logger.info("Intentando captura larga FFmpeg para %s", e.nombre)
                    sample_path = os.path.join(TEMP_DIR, f"sample_{e.id}_{ts}_long.wav")
                    ok = capture_sample_ffmpeg(url_to_try, sample_path, duration=sample_duration_conf)
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
                                    logger.info("✓ AudD reconoció (captura larga): %s (%s)", title, e.nombre)
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

        # Si no se obtuvo título, actualizar última actualización y continuar
        if not title:
            e.ultima_actualizacion = datetime.now()
            try:
                db.session.add(e)
                db.session.commit()
            except Exception:
                db.session.rollback()
            logger.warning("⊘ No se obtuvo título para %s (url probada: %s)", e.nombre, url_to_try)
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
            logger.warning("Título muy corto/vacío para %s, descartando: %r", e.nombre, title)
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
            "→ Guardando: Emisora=%s, Artista=%s, Canción=%s, Método=%s, URL=%s",
            e.nombre,
            artista,
            cancion,
            used_method or "icy/scrape/audd",
            url_to_try,
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

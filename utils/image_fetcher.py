# radio_monitor-main/utils/image_fetcher.py
import os
import re
import time
import requests
from urllib.parse import quote_plus, urlparse
from flask import current_app
from pathlib import Path

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "radio-monitor-image-fetcher/1.0"})

# ---------- helpers para rutas de cache (evaluadas en tiempo de ejecución) ----------
def _get_cache_root():
    """
    Devuelve la carpeta de cache images. Intenta usar current_app.static_folder
    si estamos dentro de un contexto de Flask; si no, cae a cwd/static/cache_images.
    """
    try:
        # current_app only available in request/app context
        static_folder = current_app.static_folder
        base = os.path.join(static_folder, "cache_images")
    except Exception:
        base = os.path.join(os.getcwd(), "static", "cache_images")
    return base

def _ensure_cache_dirs():
    root = _get_cache_root()
    artist_dir = os.path.join(root, "artist")
    song_dir = os.path.join(root, "song")
    station_dir = os.path.join(root, "station")
    for d in (artist_dir, song_dir, station_dir):
        os.makedirs(d, exist_ok=True)
    return artist_dir, song_dir, station_dir

def _artist_dir():
    return _ensure_cache_dirs()[0]

def _song_dir():
    return _ensure_cache_dirs()[1]

def _station_dir():
    return _ensure_cache_dirs()[2]

# -------------------
# Utilidades
# -------------------
def _normalize_filename(s):
    if not s:
        s = "unknown"
    s = s.strip().lower()
    s = re.sub(r"[áàäâ]", "a", s)
    s = re.sub(r"[éèëê]", "e", s)
    s = re.sub(r"[íìïî]", "i", s)
    s = re.sub(r"[óòöô]", "o", s)
    s = re.sub(r"[úùüû]", "u", s)
    s = re.sub(r"[^a-z0-9_\-\.]+", "_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    if not s:
        s = "unknown"
    return s

def _download_and_save(url, dest_path, timeout=10):
    try:
        r = SESSION.get(url, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        ct = r.headers.get("content-type", "")
        # guard minimal bytes
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024 * 8):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(dest_path) < 512:
            try:
                os.remove(dest_path)
            except Exception:
                pass
            return False
        return True
    except Exception:
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except Exception:
            pass
        return False

# -------------------
# Providers (igual que antes)
# -------------------
def _itunes_search_song_image(artist, title):
    if not (artist or title):
        return None
    q = quote_plus(f"{artist} {title}")
    url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=3"
    try:
        r = SESSION.get(url, timeout=6)
        if r.status_code != 200:
            return None
        j = r.json()
        results = j.get("results", [])
        if results:
            for item in results:
                art = item.get("artworkUrl100") or item.get("artworkUrl60") or item.get("artworkUrl30")
                if art:
                    art = art.replace("100x100bb", "600x600bb")
                    return art
    except Exception:
        pass
    return None

def _itunes_search_artist_image(artist):
    if not artist:
        return None
    q = quote_plus(artist)
    # fallback search songs for artwork
    url2 = f"https://itunes.apple.com/search?term={q}&entity=song&limit=5"
    try:
        r2 = SESSION.get(url2, timeout=6)
        if r2.status_code == 200:
            j2 = r2.json()
            for item in j2.get("results", []):
                art = item.get("artworkUrl100")
                if art:
                    return art.replace("100x100bb", "600x600bb")
    except Exception:
        pass
    return None

def _radiobrowser_station_logo(name):
    if not name:
        return None
    try:
        q = quote_plus(name)
        url = f"https://de1.api.radio-browser.info/json/stations/byname/{q}"
        r = SESSION.get(url, timeout=6)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, list) and j:
                for s in j:
                    fav = s.get("favicon") or s.get("logo") or s.get("stationfavicon")
                    if fav:
                        return fav
                first = j[0]
                return first.get("favicon") or first.get("url") or None
    except Exception:
        pass
    return None

def _clearbit_logo_for_site(site_url):
    if not site_url:
        return None
    try:
        parsed = urlparse(site_url)
        domain = parsed.netloc or parsed.path
        domain = domain.split(":")[0]
        if not domain:
            return None
        return f"https://logo.clearbit.com/{domain}?size=800"
    except Exception:
        return None

# -------------------
# Cache + main fetch functions (ahora usan rutas dinámicas)
# -------------------
def get_song_image_path(artist, title, app_config=None):
    artist = (artist or "").strip()
    title = (title or "").strip()
    key = _normalize_filename(f"{artist}___{title}")
    dest = os.path.join(_song_dir(), f"{key}.jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 512:
        return dest

    img_url = _itunes_search_song_image(artist, title)
    if img_url and _download_and_save(img_url, dest):
        return dest

    artist_path = get_artist_image_path(artist=artist, app_config=app_config)
    if artist_path and os.path.exists(artist_path):
        try:
            with open(artist_path, "rb") as sf, open(dest, "wb") as df:
                df.write(sf.read())
            return dest
        except Exception:
            pass

    return None

def get_artist_image_path(artist, app_config=None):
    artist = (artist or "").strip()
    key = _normalize_filename(artist)
    dest = os.path.join(_artist_dir(), f"{key}.jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 512:
        return dest

    img_url = _itunes_search_artist_image(artist)
    if img_url and _download_and_save(img_url, dest):
        return dest

    return None

def get_station_image_path(name, site=None, emisora_obj=None, app_config=None):
    name = (name or "").strip()
    key = _normalize_filename(name or f"station_{int(time.time())}")
    dest = os.path.join(_station_dir(), f"{key}.jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 512:
        return dest

    if site:
        cb = _clearbit_logo_for_site(site)
        if cb and _download_and_save(cb, dest):
            return dest

    rb = _radiobrowser_station_logo(name)
    if rb:
        if rb.startswith("http"):
            if _download_and_save(rb, dest):
                return dest
        else:
            cb2 = _clearbit_logo_for_site(rb)
            if cb2 and _download_and_save(cb2, dest):
                return dest

    if site:
        try:
            parsed = urlparse(site)
            domain = parsed.netloc or parsed.path
            if domain:
                fav_url = f"https://{domain}/favicon.ico"
                if _download_and_save(fav_url, dest):
                    return dest
        except Exception:
            pass

    return None

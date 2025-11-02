# archivo: app.py este es el archivo que no imprime errores pero que no tiene la parte de filtrar por paises
import time
import threading
from datetime import datetime, timedelta
from urllib.parse import quote_plus, unquote_plus
import os
import mimetypes
from urllib.parse import unquote_plus as url_unquote_plus

from flask import Flask, render_template, jsonify, request, current_app, abort, send_file

from sqlalchemy import func, desc, and_

from config import Config
from utils import stream_reader
from utils.db import db
from models.emisoras import Emisora, Cancion  # Emisora and Cancion must exist

# Try importing optional summary models (if you created them)
try:
    from models.emisoras import CancionMaster, CancionPorEmisora  # optional
    HAS_MASTER = True
except Exception:
    CancionMaster = None
    CancionPorEmisora = None
    HAS_MASTER = False

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(Config)
db.init_app(app)

# Importar y registrar las rutas de administración de emisoras
# (si el import falla la app debe fallar pronto para que lo corrijas)
from routes.emisoras_api import emisoras_api
app.register_blueprint(emisoras_api)


# ---------------------------
# Optional image_fetcher import (no rompe si no existe)
# ---------------------------
try:
    from utils.image_fetcher import (
        get_song_image_path,
        get_artist_image_path,
        get_station_image_path,
    )

    _IMAGE_FETCHER_AVAILABLE = True
except Exception:
    # Si no existe el módulo, definimos stubs que devuelven None para no romper nada.
    _IMAGE_FETCHER_AVAILABLE = False

    def get_song_image_path(*args, **kwargs):
        return None

    def get_artist_image_path(*args, **kwargs):
        return None

    def get_station_image_path(*args, **kwargs):
        return None


def _guess_mimetype(path):
    """Guess mimetype from filename; fallback to image/png."""
    m, _ = mimetypes.guess_type(path)
    if not m:
        return "image/png"
    return m


def _send_image_or_404(path):
    """Send image file if exists, otherwise raise 404."""
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype=_guess_mimetype(path))


# ---------------------------
# Monitor thread
# ---------------------------
def monitor_loop():
    with app.app_context():
        db.create_all()
        app.logger.info("🛰️  Monitor iniciado correctamente")
        while True:
            try:
                stream_reader.actualizar_emisoras(
                    fallback_to_audd=bool(app.config.get("AUDD_API_TOKEN", ""))
                )
            except Exception as exc:
                app.logger.error(f"Error en ciclo de actualización: {exc}")
            time.sleep(int(app.config.get("MONITOR_INTERVAL", 60)))


def start_monitor_thread():
    for t in threading.enumerate():
        if t.name == "radio_monitor_thread":
            app.logger.info("🔁 Hilo del monitor ya en ejecución.")
            return
    t = threading.Thread(
        target=monitor_loop, name="radio_monitor_thread", daemon=True
    )
    t.start()
    app.logger.info("🚀 Hilo del monitor lanzado.")


# ---------------------------
# Helper utilities
# ---------------------------
def make_master_key(artist, title):
    """Create a stable url-safe key for a song (used when no CancionMaster exists)."""
    artist = artist or ""
    title = title or ""
    return quote_plus(f"{artist}|||{title}")


def parse_master_key(key):
    """Return (artist, title) from an encoded key. If key is integer and CancionMaster exists,
       caller should handle that case separately."""
    try:
        s = unquote_plus(key)
        if "|||" in s:
            artist, title = s.split("|||", 1)
            return artist or None, title or None
    except Exception:
        pass
    return None, None


def count_distinct_emisoras(titulo, artista):
    """Contar emisoras distintas que reproducen una canción."""
    return (
        db.session.query(func.count(Cancion.emisora_id.distinct()))
        .filter(Cancion.titulo == titulo, Cancion.artista == artista)
        .scalar()
        or 0
    )


def count_distinct_emisoras_master(master_id):
    """Contar emisoras distintas para una canción en tabla master."""
    if CancionPorEmisora is not None:
        return (
            db.session.query(func.count(CancionPorEmisora.emisora_id.distinct()))
            .filter(CancionPorEmisora.master_id == master_id)
            .scalar()
            or 0
        )
    return 0


def _assemble_top_from_rows(rows, use_master=False):
    """Convierte filas SQLAlchemy a lista de dicts consistentes para JSON."""
    out = []
    if use_master:
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "titulo": r.titulo,
                    "artista": r.artista,
                    "total_plays": int(getattr(r, "plays", r.total_plays or 0)),
                    "first_play": getattr(r, "first_play", None).isoformat() if getattr(r, "first_play", None) else None,
                    "last_play": getattr(r, "last_play", None).isoformat() if getattr(r, "last_play", None) else None,
                    "master_key": str(r.id),
                }
            )
    else:
        for r in rows:
            master_key = make_master_key(r.artista or "", r.titulo or "")
            out.append(
                {
                    "id": None,
                    "titulo": r.titulo,
                    "artista": r.artista,
                    "total_plays": int(r.plays),
                    "first_play": r.first_play.isoformat() if r.first_play else None,
                    "last_play": r.last_play.isoformat() if r.last_play else None,
                    "master_key": master_key,
                }
            )
    return out


def get_top_from_cancion(limit=20, since=None, emisora_id=None, country=None):
    """
    Obtiene top usando la tabla 'canciones' (ventana opcional 'since' como datetime).
    Puede filtrar por emisora_id o por país (join a emisora).
    """
    q = db.session.query(
        Cancion.titulo.label("titulo"),
        Cancion.artista.label("artista"),
        func.count(Cancion.id).label("plays"),
        func.min(Cancion.fecha_reproduccion).label("first_play"),
        func.max(Cancion.fecha_reproduccion).label("last_play"),
    )
    if emisora_id:
        q = q.filter(Cancion.emisora_id == emisora_id)
    if since:
        q = q.filter(Cancion.fecha_reproduccion >= since)
    if country:
        # join Emisora
        q = q.join(Emisora, Emisora.id == Cancion.emisora_id).filter(func.lower(Emisora.pais) == country.lower())

    q = q.group_by(Cancion.titulo, Cancion.artista).order_by(desc("plays")).limit(limit)
    rows = q.all()
    return _assemble_top_from_rows(rows, use_master=False)


def get_top_weekly(limit=20):
    since = datetime.now() - timedelta(days=7)
    return get_top_from_cancion(limit=limit, since=since)


def get_top_monthly(limit=20):
    since = datetime.now() - timedelta(days=30)
    return get_top_from_cancion(limit=limit, since=since)


def compute_rank_diff(current_list, previous_list):
    """
    current_list and previous_list: list of dicts with keys 'titulo' and 'artista'
    returns same list of current_list with added keys:
      - rank (1-based)
      - prev_rank (1-based or None)
      - diff = prev_rank - rank (positive => subió)
      - is_new (True if no prev_rank)
    """
    prev_map = {}
    for idx, s in enumerate(previous_list, start=1):
        key = (s.get("titulo") or "").strip().lower(), (s.get("artista") or "").strip().lower()
        prev_map[key] = idx

    out = []
    for idx, s in enumerate(current_list, start=1):
        key = (s.get("titulo") or "").strip().lower(), (s.get("artista") or "").strip().lower()
        prev_rank = prev_map.get(key)
        diff = None
        is_new = False
        if prev_rank is None:
            is_new = True
        else:
            diff = prev_rank - idx
        item = dict(s)
        item["rank"] = idx
        item["prev_rank"] = prev_rank
        item["diff"] = diff
        item["is_new"] = is_new
        out.append(item)
    return out


# ---------------------------
# RUTAS ADICIONALES: imágenes (song, artist, station)
# ---------------------------
@app.route("/image/song/<path:master_key>")
def image_song(master_key):
    """Devuelve imagen (cached) para canción (artist + title)."""
    # Resolver artista/título (soporta master_id si existe CancionMaster)
    artist = None
    title = None
    if HAS_MASTER and master_key.isdigit():
        try:
            master_id = int(master_key)
            master = CancionMaster.query.get(master_id)
            if master:
                artist = master.artista or ""
                title = master.titulo or ""
            else:
                # si no existe el master id, intentar parsear como key (fallback)
                artist, title = parse_master_key(master_key)
        except Exception:
            artist, title = parse_master_key(master_key)
    else:
        artist, title = parse_master_key(master_key)

    if title is None:
        abort(404)

    try:
        path = get_song_image_path(artist=artist or "", title=title or "", app_config=app.config)
    except Exception:
        path = None

    # Prefer cached path, otherwise fallback to static default images if present
    if path and os.path.exists(path):
        return _send_image_or_404(path)

    # fallback candidates
    fallback_png = os.path.join(app.static_folder, "img", "default_song.png")
    fallback_jpg = os.path.join(app.static_folder, "img", "default_song.jpg")
    if os.path.exists(fallback_png):
        return send_file(fallback_png, mimetype="image/png")
    if os.path.exists(fallback_jpg):
        return send_file(fallback_jpg, mimetype="image/jpeg")
    abort(404)


@app.route("/image/artist/<path:artist_name>")
def image_artist(artist_name):
    """Devuelve imagen cached para artista (nombre urlencoded)."""
    try:
        artist = url_unquote_plus(artist_name)
    except Exception:
        artist = artist_name
    try:
        path = get_artist_image_path(artist=artist or "", app_config=app.config)
    except Exception:
        path = None

    if path and os.path.exists(path):
        return _send_image_or_404(path)

    fallback_png = os.path.join(app.static_folder, "img", "default_artist.png")
    fallback_jpg = os.path.join(app.static_folder, "img", "default_artist.jpg")
    if os.path.exists(fallback_png):
        return send_file(fallback_png, mimetype="image/png")
    if os.path.exists(fallback_jpg):
        return send_file(fallback_jpg, mimetype="image/jpeg")
    abort(404)


@app.route("/image/station/<int:emisora_id>")
def image_station(emisora_id):
    """Devuelve imagen/logo cached para emisora (por id)."""
    emisora = Emisora.query.get_or_404(emisora_id)
    site = getattr(emisora, "sitio_web", None) or getattr(emisora, "url", None)
    name = emisora.nombre or ""
    try:
        path = get_station_image_path(name=name, site=site, emisora_obj=emisora, app_config=app.config)
    except Exception:
        path = None

    if path and os.path.exists(path):
        return _send_image_or_404(path)

    fallback_png = os.path.join(app.static_folder, "img", "default_station.png")
    fallback_jpg = os.path.join(app.static_folder, "img", "default_station.jpg")
    if os.path.exists(fallback_png):
        return send_file(fallback_png, mimetype="image/png")
    if os.path.exists(fallback_jpg):
        return send_file(fallback_jpg, mimetype="image/jpeg")
    abort(404)


# ---------------------------
# Routes / Views
# ---------------------------
@app.route("/")
def index():
    emisoras = Emisora.query.order_by(Emisora.nombre).all()
    ultimas = Cancion.query.order_by(Cancion.fecha_reproduccion.desc()).limit(50).all()

    # Decide si usar CancionMaster sólo si existe y tiene filas
    use_master = False
    if HAS_MASTER and CancionMaster is not None:
        try:
            master_count = db.session.query(func.count(CancionMaster.id)).scalar() or 0
            if master_count > 0:
                use_master = True
        except Exception:
            use_master = False

    # Top global: prefer CancionMaster if available and populated, otherwise compute from Cancion
    if use_master:
        top_songs = (
            CancionMaster.query.order_by(CancionMaster.total_plays.desc()).limit(20).all()
        )
    else:
        # compute top songs from Cancion table by grouping (titulo + artista)
        top_q = (
            db.session.query(
                Cancion.titulo.label("titulo"),
                Cancion.artista.label("artista"),
                func.count(Cancion.id).label("plays"),
                func.min(Cancion.fecha_reproduccion).label("first_play"),
                func.max(Cancion.fecha_reproduccion).label("last_play"),
            )
            .group_by(Cancion.titulo, Cancion.artista)
            .order_by(desc("plays"))
            .limit(20)
            .all()
        )
        # Convert to simple objects for template compatibility
        class _Tmp:
            pass

        top_songs = []
        for r in top_q:
            t = _Tmp()
            t.titulo = r.titulo
            t.artista = r.artista
            t.total_plays = int(r.plays)
            t.first_play = r.first_play
            t.last_play = r.last_play
            # create master_key for front to request details
            t.master_key = make_master_key(r.artista or "", r.titulo or "")
            t.id = None
            top_songs.append(t)

    # Top artists: aggregate plays per artist
    if use_master and CancionMaster is not None:
        top_artists = (
            db.session.query(
                CancionMaster.artista,
                func.sum(CancionMaster.total_plays).label("plays"),
            )
            .group_by(CancionMaster.artista)
            .order_by(desc("plays"))
            .limit(20)
            .all()
        )
        # convert to (artist, plays) pairs for template compatibility
        top_artists = [(r.artista, int(r.plays or 0)) for r in top_artists]
    else:
        top_artists = (
            db.session.query(
                Cancion.artista,
                func.count(Cancion.id).label("plays"),
            )
            .group_by(Cancion.artista)
            .order_by(desc("plays"))
            .limit(20)
            .all()
        )
        top_artists = [(r.artista, int(r.plays or 0)) for r in top_artists]

    # Plays per station (totales) - try to use CancionPorEmisora if exists for performance
    if use_master and CancionPorEmisora is not None:
        plays_per_station = (
            db.session.query(
                Emisora.id,
                Emisora.nombre,
                func.coalesce(func.sum(CancionPorEmisora.plays), 0).label("plays"),
            )
            .outerjoin(CancionPorEmisora, CancionPorEmisora.emisora_id == Emisora.id)
            .group_by(Emisora.id, Emisora.nombre)
            .order_by(desc("plays"))
            .all()
        )
    else:
        plays_per_station = (
            db.session.query(
                Emisora.id,
                Emisora.nombre,
                func.coalesce(func.count(Cancion.id), 0).label("plays"),
            )
            .outerjoin(Cancion, Cancion.emisora_id == Emisora.id)
            .group_by(Emisora.id, Emisora.nombre)
            .order_by(desc("plays"))
            .all()
        )

    return render_template(
        "index.html",
        emisoras=emisoras,
        ultimas=ultimas,
        top_songs=top_songs,
        top_artists=top_artists,
        plays_per_station=plays_per_station,
        config=app.config,
    )


# ---------------------------
# API: top global (JSON)
# ---------------------------
@app.route("/api/stats/top_songs")
def api_top_songs():
    limit = int(request.args.get("limit", 20))

    use_master = False
    if HAS_MASTER and CancionMaster is not None:
        try:
            master_count = db.session.query(func.count(CancionMaster.id)).scalar() or 0
            if master_count > 0:
                use_master = True
        except Exception:
            use_master = False

    out = []

    if use_master:
        rows = CancionMaster.query.order_by(CancionMaster.total_plays.desc()).limit(limit).all()
        for r in rows:
            if CancionPorEmisora is not None:
                break_down = (
                    db.session.query(Emisora.id, Emisora.nombre, CancionPorEmisora.plays)
                    .join(CancionPorEmisora, CancionPorEmisora.emisora_id == Emisora.id)
                    .filter(CancionPorEmisora.master_id == r.id)
                    .order_by(desc(CancionPorEmisora.plays))
                    .limit(10)
                    .all()
                )
                breakdown_list = [
                    {"emisora_id": b.id, "emisora_nombre": b.nombre, "plays": int(b.plays)}
                    for b in break_down
                ]
                total_emisoras = int(count_distinct_emisoras_master(r.id))
            else:
                bd = (
                    db.session.query(Emisora.id, Emisora.nombre, func.count(Cancion.id).label("plays"))
                    .join(Cancion, Cancion.emisora_id == Emisora.id)
                    .filter(Cancion.titulo == r.titulo, Cancion.artista == r.artista)
                    .group_by(Emisora.id, Emisora.nombre)
                    .order_by(desc("plays"))
                    .limit(10)
                    .all()
                )
                breakdown_list = [
                    {"emisora_id": b.id, "emisora_nombre": b.nombre, "plays": int(b.plays)} for b in bd
                ]
                total_emisoras = int(count_distinct_emisoras(r.titulo, r.artista))

            out.append(
                {
                    "id": r.id,
                    "titulo": r.titulo,
                    "artista": r.artista,
                    "total_plays": int(r.total_plays or 0),
                    "total_emisoras": total_emisoras,
                    "first_play": r.first_play.isoformat() if r.first_play else None,
                    "last_play": r.last_play.isoformat() if r.last_play else None,
                    "breakdown": breakdown_list,
                    "master_key": str(r.id),
                }
            )
    else:
        rows = (
            db.session.query(
                Cancion.titulo.label("titulo"),
                Cancion.artista.label("artista"),
                func.count(Cancion.id).label("plays"),
                func.min(Cancion.fecha_reproduccion).label("first_play"),
                func.max(Cancion.fecha_reproduccion).label("last_play"),
            )
            .group_by(Cancion.titulo, Cancion.artista)
            .order_by(desc("plays"))
            .limit(limit)
            .all()
        )
        for r in rows:
            bd = (
                db.session.query(Emisora.id, Emisora.nombre, func.count(Cancion.id).label("plays"))
                .join(Cancion, Cancion.emisora_id == Emisora.id)
                .filter(Cancion.titulo == r.titulo, Cancion.artista == r.artista)
                .group_by(Emisora.id, Emisora.nombre)
                .order_by(desc("plays"))
                .limit(10)
                .all()
            )
            breakdown_list = [{"emisora_id": b.id, "emisora_nombre": b.nombre, "plays": int(b.plays)} for b in bd]
            total_emisoras = int(count_distinct_emisoras(r.titulo, r.artista))
            master_key = make_master_key(r.artista or "", r.titulo or "")
            out.append(
                {
                    "id": None,
                    "titulo": r.titulo,
                    "artista": r.artista,
                    "total_plays": int(r.plays),
                    "total_emisoras": total_emisoras,
                    "first_play": r.first_play.isoformat() if r.first_play else None,
                    "last_play": r.last_play.isoformat() if r.last_play else None,
                    "breakdown": breakdown_list,
                    "master_key": master_key,
                }
            )

    return jsonify(out)


# ---------------------------
# API: top por emisora (soporta period=all|weekly|monthly)
# ---------------------------
@app.route("/api/stats/top_by_station/<int:emisora_id>")
def api_top_by_station(emisora_id):
    limit = int(request.args.get("limit", 20))
    period = request.args.get("period", "all")  # all, weekly, monthly

    # Check emisora exists
    emisora = Emisora.query.get(emisora_id)
    if not emisora:
        return jsonify({"error": "Emisora no encontrada"}), 404

    # if master/per-station summary exists and period==all, prefer it
    use_master = False
    if period == "all" and HAS_MASTER and CancionPorEmisora is not None:
        try:
            cp_count = db.session.query(func.count(CancionPorEmisora.emisora_id)).scalar() or 0
            if cp_count > 0:
                use_master = True
        except Exception:
            use_master = False

    if use_master:
        rows = (
            db.session.query(
                CancionMaster.id.label("mid"),
                CancionMaster.titulo,
                CancionMaster.artista,
                CancionPorEmisora.plays,
            )
            .join(CancionPorEmisora, CancionPorEmisora.master_id == CancionMaster.id)
            .filter(CancionPorEmisora.emisora_id == emisora_id)
            .order_by(desc(CancionPorEmisora.plays))
            .limit(limit)
            .all()
        )
        return jsonify([{"master_id": r.mid, "titulo": r.titulo, "artista": r.artista, "plays": int(r.plays)} for r in rows])
    else:
        since = None
        if period == "weekly":
            since = datetime.now() - timedelta(days=7)
        elif period == "monthly":
            since = datetime.now() - timedelta(days=30)

        rows = (
            db.session.query(
                Cancion.titulo.label("titulo"),
                Cancion.artista.label("artista"),
                func.count(Cancion.id).label("plays"),
            )
            .filter(Cancion.emisora_id == emisora_id)
            .filter(Cancion.fecha_reproduccion >= since) if since else db.session.query(
                Cancion.titulo.label("titulo"),
                Cancion.artista.label("artista"),
                func.count(Cancion.id).label("plays"),
            ).filter(Cancion.emisora_id == emisora_id)
        )

        # If we built a partial query earlier, ensure grouping and ordering
        rows = rows.group_by(Cancion.titulo, Cancion.artista).order_by(desc("plays")).limit(limit).all()
        out = [{"master_key": make_master_key(r.artista or "", r.titulo or ""), "titulo": r.titulo, "artista": r.artista, "plays": int(r.plays)} for r in rows]
        return jsonify(out)


# ---------------------------
# API: top por País
# ---------------------------
@app.route("/api/stats/top_by_country/<string:country>")
def api_top_by_country(country):
    limit = int(request.args.get("limit", 20))
    period = request.args.get("period", "all")  # all, weekly, monthly

    since = None
    if period == "weekly":
        since = datetime.now() - timedelta(days=7)
    elif period == "monthly":
        since = datetime.now() - timedelta(days=30)

    # Use Cancion table, join Emisora, filter by Emisora.pais
    q = db.session.query(
        Cancion.titulo.label("titulo"),
        Cancion.artista.label("artista"),
        func.count(Cancion.id).label("plays"),
        func.min(Cancion.fecha_reproduccion).label("first_play"),
        func.max(Cancion.fecha_reproduccion).label("last_play"),
    ).join(Emisora, Emisora.id == Cancion.emisora_id).filter(func.lower(Emisora.pais) == country.lower())

    if since:
        q = q.filter(Cancion.fecha_reproduccion >= since)

    q = q.group_by(Cancion.titulo, Cancion.artista).order_by(desc("plays")).limit(limit)
    rows = q.all()
    return jsonify(_assemble_top_from_rows(rows, use_master=False))


# ---------------------------
# API: Top semanal (global) + diff contra semana anterior
# ---------------------------
@app.route("/api/stats/top_weekly")
def api_top_weekly():
    limit = int(request.args.get("limit", 20))
    # Top actual (últimos 7 días)
    current = get_top_from_cancion(limit=limit, since=datetime.now() - timedelta(days=7))
    # Top de la semana previa (días 8-14)
    start_prev = datetime.now() - timedelta(days=14)
    end_prev = datetime.now() - timedelta(days=7)
    prev_rows = (
        db.session.query(
            Cancion.titulo.label("titulo"),
            Cancion.artista.label("artista"),
            func.count(Cancion.id).label("plays"),
        )
        .filter(Cancion.fecha_reproduccion >= start_prev)
        .filter(Cancion.fecha_reproduccion < end_prev)
        .group_by(Cancion.titulo, Cancion.artista)
        .order_by(desc("plays"))
        .limit(limit)
        .all()
    )
    prev = _assemble_top_from_rows(prev_rows, use_master=False)
    # compute diff
    result = compute_rank_diff(current, prev)
    return jsonify(result)


# ---------------------------
# API: Top mensual (global)
# ---------------------------
@app.route("/api/stats/top_monthly")
def api_top_monthly():
    limit = int(request.args.get("limit", 20))
    current = get_top_from_cancion(limit=limit, since=datetime.now() - timedelta(days=30))
    # Previous month window for diff calculation (optional)
    start_prev = datetime.now() - timedelta(days=60)
    end_prev = datetime.now() - timedelta(days=30)
    prev_rows = (
        db.session.query(
            Cancion.titulo.label("titulo"),
            Cancion.artista.label("artista"),
            func.count(Cancion.id).label("plays"),
        )
        .filter(Cancion.fecha_reproduccion >= start_prev)
        .filter(Cancion.fecha_reproduccion < end_prev)
        .group_by(Cancion.titulo, Cancion.artista)
        .order_by(desc("plays"))
        .limit(limit)
        .all()
    )
    prev = _assemble_top_from_rows(prev_rows, use_master=False)
    result = compute_rank_diff(current, prev)
    return jsonify(result)


# ---------------------------
# API: reproducción actual por emisora (última canción)
# ---------------------------
@app.route("/api/stats/current_play/<int:emisora_id>")
def api_current_play(emisora_id):
    emisora = Emisora.query.get_or_404(emisora_id)
    last = (
        db.session.query(Cancion)
        .filter(Cancion.emisora_id == emisora_id)
        .order_by(Cancion.fecha_reproduccion.desc())
        .limit(1)
        .first()
    )
    if not last:
        return jsonify({"emisora_id": emisora_id, "emisora_nombre": emisora.nombre, "current": None})
    return jsonify({
        "emisora_id": emisora_id,
        "emisora_nombre": emisora.nombre,
        "current": {
            "titulo": last.titulo,
            "artista": last.artista,
            "fecha_reproduccion": last.fecha_reproduccion.isoformat() if last.fecha_reproduccion else None
        }
    })


# ---------------------------
# API: detalle canción + últimos plays
# (sin cambios - mantiene comportamiento actual)
# ---------------------------
@app.route("/api/stats/song/<path:master_key>")
def api_song_detail(master_key):
    # If numeric ID and master table exists -> use it
    if HAS_MASTER and master_key.isdigit():
        master_id = int(master_key)
        master = CancionMaster.query.get_or_404(master_id)
        title = master.titulo
        artist = master.artista
        total_plays = int(master.total_plays or 0)
        first_play = master.first_play
        last_play = master.last_play
        total_emisoras = int(count_distinct_emisoras_master(master_id))
    else:
        # parse artist|title key
        artist, title = parse_master_key(master_key)
        if title is None:
            return jsonify({"error": "master_key inválida"}), 400
        # compute summary from canciones
        total_plays = (
            db.session.query(func.count(Cancion.id))
            .filter(Cancion.titulo == title, Cancion.artista == artist)
            .scalar() or 0
        )
        first_play = (
            db.session.query(func.min(Cancion.fecha_reproduccion))
            .filter(Cancion.titulo == title, Cancion.artista == artist)
            .scalar()
        )
        last_play = (
            db.session.query(func.max(Cancion.fecha_reproduccion))
            .filter(Cancion.titulo == title, Cancion.artista == artist)
            .scalar()
        )
        total_emisoras = int(count_distinct_emisoras(title, artist))

    # recent plays (with emisora name)
    recent_q = (
        db.session.query(Cancion, Emisora.nombre.label("emisora_nombre"))
        .outerjoin(Emisora, Emisora.id == Cancion.emisora_id)
        .filter(Cancion.titulo == title, Cancion.artista == artist)
        .order_by(Cancion.fecha_reproduccion.desc())
        .limit(200)
        .all()
    )
    recent_plays = [
        {"emisora_id": c.Cancion.emisora_id, "emisora_nombre": c.emisora_nombre, "fecha": c.Cancion.fecha_reproduccion.isoformat()}
        for c in recent_q
    ]

    # per-station counts (top stations)
    per_station = (
        db.session.query(Emisora.id, Emisora.nombre, func.count(Cancion.id).label("plays"))
        .join(Cancion, Cancion.emisora_id == Emisora.id)
        .filter(Cancion.titulo == title, Cancion.artista == artist)
        .group_by(Emisora.id, Emisora.nombre)
        .order_by(desc("plays"))
        .limit(50)
        .all()
    )
    per_station_list = [{"emisora_id": r.id, "emisora_nombre": r.nombre, "plays": int(r.plays)} for r in per_station]

    return jsonify({
        "titulo": title,
        "artista": artist,
        "total_plays": int(total_plays),
        "total_emisoras": total_emisoras,
        "first_play": first_play.isoformat() if first_play else None,
        "last_play": last_play.isoformat() if last_play else None,
        "per_station": per_station_list,
        "recent_plays": recent_plays,
    })


# ---------------------------
# API: timeseries global (agrupado por hora)
# ---------------------------
@app.route("/api/stats/timeseries")
def api_timeseries():
    hours = int(request.args.get("hours", 24))
    since = datetime.now() - timedelta(hours=hours)
    rows = (
        db.session.query(
            func.date_trunc("hour", Cancion.fecha_reproduccion).label("hour"),
            func.count(Cancion.id).label("plays"),
        )
        .filter(Cancion.fecha_reproduccion >= since)
        .group_by("hour")
        .order_by("hour")
        .all()
    )
    return jsonify([{"hour": r.hour.isoformat(), "plays": int(r.plays)} for r in rows])


# ---------------------------
# Página de emisora: Top semanal, mensual, reproducción actual, top artistas
# ---------------------------
@app.route("/emisora/<int:emisora_id>")
def emisora_page(emisora_id):
    emisora = Emisora.query.get_or_404(emisora_id)

    # Current play
    current = None
    last = (
        db.session.query(Cancion)
        .filter(Cancion.emisora_id == emisora_id)
        .order_by(Cancion.fecha_reproduccion.desc())
        .limit(1)
        .first()
    )
    if last:
        current = {
            "titulo": last.titulo,
            "artista": last.artista,
            "fecha_reproduccion": last.fecha_reproduccion
        }

    # Top weekly & monthly (use Cancion table filtered by emisora_id)
    top_weekly = get_top_from_cancion(limit=50, since=datetime.now() - timedelta(days=7), emisora_id=emisora_id)
    top_monthly = get_top_from_cancion(limit=50, since=datetime.now() - timedelta(days=30), emisora_id=emisora_id)

    # top artists for this emisora (aggregated)
    artists_q = (
        db.session.query(Cancion.artista, func.count(Cancion.id).label("plays"))
        .filter(Cancion.emisora_id == emisora_id)
        .group_by(Cancion.artista)
        .order_by(desc("plays"))
        .limit(50)
        .all()
    )
    top_artists = [{"artista": r.artista, "plays": int(r.plays)} for r in artists_q]

    # For ranking diffs: compute previous week for emisora
    prev_rows = (
        db.session.query(
            Cancion.titulo.label("titulo"),
            Cancion.artista.label("artista"),
            func.count(Cancion.id).label("plays"),
        )
        .filter(Cancion.emisora_id == emisora_id)
        .filter(Cancion.fecha_reproduccion >= datetime.now() - timedelta(days=14))
        .filter(Cancion.fecha_reproduccion < datetime.now() - timedelta(days=7))
        .group_by(Cancion.titulo, Cancion.artista)
        .order_by(desc("plays"))
        .limit(50)
        .all()
    )
    prev_week = _assemble_top_from_rows(prev_rows, use_master=False)
    top_weekly_with_diff = compute_rank_diff(top_weekly, prev_week)

    return render_template(
        "emisora.html",
        emisora=emisora,
        current=current,
        top_weekly=top_weekly_with_diff,
        top_monthly=top_monthly,
        top_artists=top_artists,
    )


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        start_monitor_thread()
    # dev server
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ---------------------------
# Lanzar el monitor también cuando se ejecute con Gunicorn
# ---------------------------
try:
    # Si la app se importa (por Gunicorn), arrancar el monitor
    with app.app_context():
        start_monitor_thread()
except Exception as e:
    app.logger.error(f"No se pudo iniciar el monitor automáticamente: {e}")

# archivo: app.py - Versión con filtrado por países MEJORADO y normalizado
import time
import threading
from datetime import datetime, timedelta
from urllib.parse import quote_plus, unquote_plus
import os
import mimetypes
import re
import logging

from flask import Flask, render_template, jsonify, request, abort, send_file
from flask.cli import with_appcontext
import click
from sqlalchemy import func, desc, or_

from config import Config
from utils import stream_reader
from utils.db import db
from models.emisoras import Emisora, Cancion

# Importar modelos opcionales
try:
    from models.emisoras import CancionMaster, CancionPorEmisora
    HAS_MASTER = True
except Exception:
    CancionMaster = None
    CancionPorEmisora = None
    HAS_MASTER = False

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(Config)
db.init_app(app)

# Registrar rutas de API
from routes.emisoras_api import emisoras_api
app.register_blueprint(emisoras_api)

# Importar validador de streams (después de crear app)
try:
    from utils.stream_validator import validator
    HAS_VALIDATOR = True
except Exception as e:
    app.logger.warning(f"⚠️  Stream validator no disponible: {e}")
    HAS_VALIDATOR = False
    validator = None

# Sistema de imágenes (opcional)
try:
    from utils.image_fetcher import (
        get_song_image_path,
        get_artist_image_path,
        get_station_image_path,
    )
    _IMAGE_FETCHER_AVAILABLE = True
except Exception:
    _IMAGE_FETCHER_AVAILABLE = False
    
    def get_song_image_path(*args, **kwargs):
        return None
    
    def get_artist_image_path(*args, **kwargs):
        return None
    
    def get_station_image_path(*args, **kwargs):
        return None


# ============================================================================
# NORMALIZACIÓN DE PAÍSES - Funciones helper
# ============================================================================

def normalize_country_name(country_str):
    """
    Normaliza nombres de países eliminando ciudades, códigos y caracteres extraños.
    Retorna el nombre limpio del país o None si no es válido.
    """
    if not country_str or not isinstance(country_str, str):
        return None
    
    # Convertir a string y limpiar espacios
    country = str(country_str).strip()
    
    # Si está vacío después de limpiar
    if not country or country.lower() in ['', 'null', 'none', 'n/a', 'unknown']:
        return None
    
    # Remover códigos de área/ciudad entre paréntesis o después de guiones
    country = re.sub(r'\s*[-–—]\s*.*$', '', country)  # Todo después de guión
    country = re.sub(r'\s*\(.*?\)\s*', '', country)   # Paréntesis
    country = re.sub(r'\s*\[.*?\]\s*', '', country)   # Corchetes
    
    # Separar por comas y tomar solo la primera parte (país principal)
    if ',' in country:
        country = country.split(',')[0].strip()
    
    # Diccionario de normalizaciones comunes
    normalizations = {
        'republica dominicana': 'República Dominicana',
        'república dominicana': 'República Dominicana',
        'rep dom': 'República Dominicana',
        'rep. dom': 'República Dominicana',
        'rep.dom': 'República Dominicana',
        'rd': 'República Dominicana',
        'dominican republic': 'República Dominicana',
        
        'colombia': 'Colombia',
        'co': 'Colombia',
        
        'venezuela': 'Venezuela',
        've': 'Venezuela',
        
        'méxico': 'México',
        'mexico': 'México',
        'mx': 'México',
        
        'argentina': 'Argentina',
        'ar': 'Argentina',
        
        'chile': 'Chile',
        'cl': 'Chile',
        
        'perú': 'Perú',
        'peru': 'Perú',
        'pe': 'Perú',
        
        'bolivia': 'Bolivia',
        'bo': 'Bolivia',
        
        'ecuador': 'Ecuador',
        'ec': 'Ecuador',
        
        'españa': 'España',
        'spain': 'España',
        'es': 'España',
        
        'estados unidos': 'Estados Unidos',
        'usa': 'Estados Unidos',
        'us': 'Estados Unidos',
        'united states': 'Estados Unidos',
    }
    
    # Buscar normalización (case-insensitive)
    country_lower = country.lower()
    for key, normalized in normalizations.items():
        if country_lower.startswith(key):
            return normalized
    
    # Si no se encontró normalización, capitalizar correctamente
    # Remover caracteres especiales al inicio/final
    country = re.sub(r'^[^a-zA-ZáéíóúÁÉÍÓÚñÑ]+', '', country)
    country = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', '', country)
    
    # Capitalizar primera letra de cada palabra
    if country:
        return ' '.join(word.capitalize() for word in country.split())
    
    return None


def get_valid_countries():
    """
    Obtiene lista de países válidos con sus estadísticas REALES.
    Solo incluye países con nombres normalizados y cuenta correcta.
    """
    try:
        # Obtener todos los países únicos de emisoras
        raw_countries = db.session.query(Emisora.pais).distinct().all()
        
        country_stats = {}
        
        for (raw_country,) in raw_countries:
            normalized = normalize_country_name(raw_country)
            
            # Saltar países inválidos
            if not normalized:
                continue
            
            # Contar emisoras y canciones para este país NORMALIZADO
            # Buscar todas las variantes que normalizan a este país
            emisoras_ids = []
            for (variant,) in raw_countries:
                if normalize_country_name(variant) == normalized:
                    # Obtener IDs de emisoras para esta variante
                    ids = db.session.query(Emisora.id).filter(
                        Emisora.pais == variant
                    ).all()
                    emisoras_ids.extend([id[0] for id in ids])
            
            # Remover duplicados
            emisoras_ids = list(set(emisoras_ids))
            
            # Contar canciones para estas emisoras
            total_canciones = db.session.query(func.count(Cancion.id)).filter(
                Cancion.emisora_id.in_(emisoras_ids)
            ).scalar() or 0
            
            # Solo incluir si tiene datos reales
            if emisoras_ids and total_canciones > 0:
                if normalized not in country_stats:
                    country_stats[normalized] = {
                        'pais': normalized,
                        'emisoras': 0,
                        'canciones': 0
                    }
                
                country_stats[normalized]['emisoras'] = len(emisoras_ids)
                country_stats[normalized]['canciones'] = total_canciones
        
        # Convertir a lista y ordenar por número de canciones
        result = list(country_stats.values())
        result.sort(key=lambda x: x['canciones'], reverse=True)
        
        return result
        
    except Exception as e:
        app.logger.error(f"Error obteniendo países válidos: {e}")
        return []


# ============================================================================
# MONITOR THREAD - Sistema de actualización automática
# ============================================================================

def monitor_loop():
    """Loop principal del monitor de emisoras."""
    with app.app_context():
        db.create_all()
        app.logger.info("🛰️  Monitor de emisoras iniciado correctamente")
        
        while True:
            try:
                stream_reader.actualizar_emisoras(
                    fallback_to_audd=bool(app.config.get("AUDD_API_TOKEN", "")),
                    dedupe_seconds=int(app.config.get("DEDUPE_SECONDS", 300))
                )
            except Exception as exc:
                app.logger.error(f"❌ Error en ciclo de actualización: {exc}")
                try:
                    db.session.rollback()
                except Exception as rollback_exc:
                    app.logger.error(f"Error en rollback: {rollback_exc}")
            
            interval = int(app.config.get("MONITOR_INTERVAL", 60))
            time.sleep(interval)


def start_monitor_thread():
    """Inicia el hilo del monitor si no está corriendo."""
    for t in threading.enumerate():
        if t.name == "radio_monitor_thread":
            app.logger.info("🔁 Monitor ya en ejecución")
            return
    
    t = threading.Thread(
        target=monitor_loop,
        name="radio_monitor_thread",
        daemon=True
    )
    t.start()
    app.logger.info("🚀 Monitor iniciado exitosamente")


# ============================================================================
# UTILIDADES - Funciones helper
# ============================================================================

def make_master_key(artist, title):
    """Genera clave única para una canción."""
    artist = artist or ""
    title = title or ""
    return quote_plus(f"{artist}|||{title}")


def parse_master_key(key):
    """Extrae artista y título de una clave."""
    try:
        s = unquote_plus(key)
        if "|||" in s:
            artist, title = s.split("|||", 1)
            return artist or None, title or None
    except Exception:
        pass
    return None, None


def count_distinct_emisoras(titulo, artista):
    """Cuenta emisoras distintas que tocan una canción."""
    return (
        db.session.query(func.count(Cancion.emisora_id.distinct()))
        .filter(Cancion.titulo == titulo, Cancion.artista == artista)
        .scalar() or 0
    )


def _assemble_top_from_rows(rows, use_master=False, include_dates=True):
    """
    Convierte filas SQL a formato JSON consistente.
    """
    out = []
    
    if use_master:
        for r in rows:
            item = {
                "id": r.id,
                "titulo": r.titulo,
                "artista": r.artista,
                "total_plays": int(getattr(r, "plays", r.total_plays or 0)),
                "master_key": str(r.id),
            }
            if include_dates:
                item["first_play"] = (r.first_play.isoformat() 
                                     if hasattr(r, 'first_play') and r.first_play 
                                     else None)
                item["last_play"] = (r.last_play.isoformat() 
                                    if hasattr(r, 'last_play') and r.last_play 
                                    else None)
            out.append(item)
    else:
        for r in rows:
            item = {
                "id": None,
                "titulo": r.titulo,
                "artista": r.artista,
                "total_plays": int(r.plays),
                "master_key": make_master_key(r.artista or "", r.titulo or ""),
            }
            if include_dates and hasattr(r, 'first_play'):
                item["first_play"] = r.first_play.isoformat() if r.first_play else None
                item["last_play"] = r.last_play.isoformat() if r.last_play else None
            out.append(item)
    
    return out


def get_top_from_cancion(limit=20, since=None, emisora_id=None, country=None):
    """
    Obtiene top de canciones con filtros opcionales.
    MEJORADO: Normaliza nombres de países antes de filtrar.
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
        # MEJORADO: Buscar todas las variantes que normalizan a este país
        normalized_country = normalize_country_name(country)
        if normalized_country:
            # Obtener todas las variantes de países que normalizan al mismo valor
            all_variants = db.session.query(Emisora.pais).distinct().all()
            matching_variants = [
                v[0] for v in all_variants 
                if normalize_country_name(v[0]) == normalized_country
            ]
            
            if matching_variants:
                q = q.join(Emisora, Emisora.id == Cancion.emisora_id)
                q = q.filter(Emisora.pais.in_(matching_variants))
            else:
                # Si no hay variantes, buscar exacto (fallback)
                q = q.join(Emisora, Emisora.id == Cancion.emisora_id)
                q = q.filter(func.lower(Emisora.pais) == country.lower())
    
    # Filtrar basura
    q = q.filter(
        Cancion.artista != "Desconocido",
        func.length(Cancion.titulo) >= 3
    )
    
    q = q.group_by(Cancion.titulo, Cancion.artista)
    q = q.order_by(desc("plays"))
    q = q.limit(limit)
    
    return _assemble_top_from_rows(q.all(), use_master=False, include_dates=True)


def compute_rank_diff(current_list, previous_list):
    """
    Calcula diferencias de ranking entre dos listas.
    """
    prev_map = {}
    for idx, s in enumerate(previous_list, start=1):
        key = (
            (s.get("titulo") or "").strip().lower(),
            (s.get("artista") or "").strip().lower()
        )
        prev_map[key] = idx
    
    out = []
    for idx, s in enumerate(current_list, start=1):
        key = (
            (s.get("titulo") or "").strip().lower(),
            (s.get("artista") or "").strip().lower()
        )
        prev_rank = prev_map.get(key)
        
        item = dict(s)
        item["rank"] = idx
        item["prev_rank"] = prev_rank
        item["diff"] = (prev_rank - idx) if prev_rank else None
        item["is_new"] = prev_rank is None
        
        out.append(item)
    
    return out


# ============================================================================
# RUTAS DE IMÁGENES - Sistema de fallback sin 404
# ============================================================================

def _send_image_or_fallback(path, fallback_name):
    """Envía imagen o fallback si no existe."""
    if path and os.path.exists(path):
        mime = mimetypes.guess_type(path)[0] or "image/png"
        return send_file(path, mimetype=mime)
    
    for ext in ['png', 'jpg', 'jpeg']:
        fallback = os.path.join(app.static_folder, "img", f"{fallback_name}.{ext}")
        if os.path.exists(fallback):
            mime = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
            return send_file(fallback, mimetype=mime)
    
    generic = os.path.join(app.static_folder, "img", "default.png")
    if os.path.exists(generic):
        return send_file(generic, mimetype="image/png")
    
    abort(404)


@app.route("/image/song/<path:master_key>")
def image_song(master_key):
    """Imagen de canción con fallback automático."""
    artist = None
    title = None
    
    if HAS_MASTER and master_key.isdigit():
        try:
            master = CancionMaster.query.get(int(master_key))
            if master:
                artist = master.artista or ""
                title = master.titulo or ""
        except Exception:
            pass
    
    if not title:
        artist, title = parse_master_key(master_key)
    
    if not title:
        return _send_image_or_fallback(None, "default_song")
    
    try:
        path = get_song_image_path(
            artist=artist or "",
            title=title or "",
            app_config=app.config
        )
    except Exception:
        path = None
    
    return _send_image_or_fallback(path, "default_song")


@app.route("/image/artist/<path:artist_name>")
def image_artist(artist_name):
    """Imagen de artista con fallback automático."""
    try:
        artist = unquote_plus(artist_name)
    except Exception:
        artist = artist_name
    
    try:
        path = get_artist_image_path(artist=artist or "", app_config=app.config)
    except Exception:
        path = None
    
    return _send_image_or_fallback(path, "default_artist")


@app.route("/image/station/<int:emisora_id>")
def image_station(emisora_id):
    """Imagen de emisora con fallback automático."""
    emisora = Emisora.query.get_or_404(emisora_id)
    
    try:
        path = get_station_image_path(
            name=emisora.nombre or "",
            site=getattr(emisora, "sitio_web", None) or emisora.url_stream,
            emisora_obj=emisora,
            app_config=app.config
        )
    except Exception:
        path = None
    
    return _send_image_or_fallback(path, "default_station")


# ============================================================================
# RUTA PRINCIPAL - Dashboard
# ============================================================================

@app.route("/")
def index():
    """Página principal del dashboard."""
    emisoras = Emisora.query.order_by(Emisora.nombre).all()
    
    ultimas = (
        Cancion.query
        .filter(
            Cancion.artista != "Desconocido",
            func.length(Cancion.titulo) >= 3
        )
        .order_by(Cancion.fecha_reproduccion.desc())
        .limit(50)
        .all()
    )
    
    use_master = False
    if HAS_MASTER and CancionMaster:
        try:
            count = db.session.query(func.count(CancionMaster.id)).scalar() or 0
            use_master = count > 0
        except Exception:
            pass
    
    if use_master:
        top_songs = (
            CancionMaster.query
            .order_by(CancionMaster.total_plays.desc())
            .limit(20)
            .all()
        )
    else:
        top_q = (
            db.session.query(
                Cancion.titulo,
                Cancion.artista,
                func.count(Cancion.id).label("plays"),
                func.min(Cancion.fecha_reproduccion).label("first_play"),
                func.max(Cancion.fecha_reproduccion).label("last_play"),
            )
            .filter(
                Cancion.artista != "Desconocido",
                func.length(Cancion.titulo) >= 3
            )
            .group_by(Cancion.titulo, Cancion.artista)
            .order_by(desc("plays"))
            .limit(20)
            .all()
        )
        
        class _Song:
            pass
        
        top_songs = []
        for r in top_q:
            s = _Song()
            s.titulo = r.titulo
            s.artista = r.artista
            s.total_plays = int(r.plays)
            s.first_play = r.first_play
            s.last_play = r.last_play
            s.master_key = make_master_key(r.artista or "", r.titulo or "")
            s.id = None
            top_songs.append(s)
    
    if use_master and CancionMaster:
        top_artists = (
            db.session.query(
                CancionMaster.artista,
                func.sum(CancionMaster.total_plays).label("plays"),
            )
            .filter(CancionMaster.artista != "Desconocido")
            .group_by(CancionMaster.artista)
            .order_by(desc("plays"))
            .limit(20)
            .all()
        )
        top_artists = [(r.artista, int(r.plays or 0)) for r in top_artists]
    else:
        top_artists = (
            db.session.query(
                Cancion.artista,
                func.count(Cancion.id).label("plays"),
            )
            .filter(
                Cancion.artista != "Desconocido",
                func.length(Cancion.titulo) >= 3
            )
            .group_by(Cancion.artista)
            .order_by(desc("plays"))
            .limit(20)
            .all()
        )
        top_artists = [(r.artista, int(r.plays or 0)) for r in top_artists]
    
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


# ============================================================================
# API - Estadísticas Globales MEJORADAS
# ============================================================================

@app.route("/api/stats/top_songs")
def api_top_songs():
    """Top canciones global con breakdown por emisora."""
    limit = int(request.args.get("limit", 20))
    
    rows = (
        db.session.query(
            Cancion.titulo,
            Cancion.artista,
            func.count(Cancion.id).label("plays"),
            func.min(Cancion.fecha_reproduccion).label("first_play"),
            func.max(Cancion.fecha_reproduccion).label("last_play"),
        )
        .filter(
            Cancion.artista != "Desconocido",
            func.length(Cancion.titulo) >= 3
        )
        .group_by(Cancion.titulo, Cancion.artista)
        .order_by(desc("plays"))
        .limit(limit)
        .all()
    )
    
    out = []
    for r in rows:
        breakdown = (
            db.session.query(
                Emisora.id,
                Emisora.nombre,
                func.count(Cancion.id).label("plays")
            )
            .join(Cancion, Cancion.emisora_id == Emisora.id)
            .filter(
                Cancion.titulo == r.titulo,
                Cancion.artista == r.artista
            )
            .group_by(Emisora.id, Emisora.nombre)
            .order_by(desc("plays"))
            .limit(10)
            .all()
        )
        
        out.append({
            "id": None,
            "titulo": r.titulo,
            "artista": r.artista,
            "total_plays": int(r.plays),
            "total_emisoras": count_distinct_emisoras(r.titulo, r.artista),
            "first_play": r.first_play.isoformat() if r.first_play else None,
            "last_play": r.last_play.isoformat() if r.last_play else None,
            "breakdown": [
                {
                    "emisora_id": b.id,
                    "emisora_nombre": b.nombre,
                    "plays": int(b.plays)
                }
                for b in breakdown
            ],
            "master_key": make_master_key(r.artista or "", r.titulo or ""),
        })
    
    return jsonify(out)


@app.route("/api/stats/top_by_country/<string:country>")
def api_top_by_country(country):
    """
    Top canciones por país MEJORADO con normalización.
    """
    limit = int(request.args.get("limit", 50))
    period = request.args.get("period", "all")
    
    # Normalizar país recibido
    normalized = normalize_country_name(country)
    
    if not normalized:
        return jsonify({"error": "País inválido"}), 400
    
    since = None
    if period == "weekly":
        since = datetime.now() - timedelta(days=7)
    elif period == "monthly":
        since = datetime.now() - timedelta(days=30)
    
    try:
        data = get_top_from_cancion(
            limit=limit,
            since=since,
            country=normalized
        )
        
        return jsonify(data)
        
    except Exception as e:
        app.logger.error(f"Error en top_by_country: {e}")
        return jsonify({"error": "Error obteniendo datos"}), 500


@app.route("/api/stats/countries")
def api_countries():
    """
    Lista países con estadísticas MEJORADA.
    Retorna solo países válidos y normalizados.
    """
    try:
        countries = get_valid_countries()
        return jsonify(countries)
    except Exception as e:
        app.logger.error(f"Error en api_countries: {e}")
        return jsonify([]), 500


@app.route("/api/stats/top_weekly")
def api_top_weekly():
    """Top semanal con diferencias."""
    limit = int(request.args.get("limit", 20))
    
    current = get_top_from_cancion(
        limit=limit,
        since=datetime.now() - timedelta(days=7)
    )
    
    prev_rows = (
        db.session.query(
            Cancion.titulo,
            Cancion.artista,
            func.count(Cancion.id).label("plays"),
        )
        .filter(
            Cancion.fecha_reproduccion >= datetime.now() - timedelta(days=14),
            Cancion.fecha_reproduccion < datetime.now() - timedelta(days=7),
            Cancion.artista != "Desconocido"
        )
        .group_by(Cancion.titulo, Cancion.artista)
        .order_by(desc("plays"))
        .limit(limit)
        .all()
    )
    
    prev = _assemble_top_from_rows(prev_rows, use_master=False, include_dates=False)
    result = compute_rank_diff(current, prev)
    
    return jsonify(result)


@app.route("/api/stats/top_monthly")
def api_top_monthly():
    """Top mensual con diferencias."""
    limit = int(request.args.get("limit", 20))
    
    current = get_top_from_cancion(
        limit=limit,
        since=datetime.now() - timedelta(days=30)
    )
    
    prev_rows = (
        db.session.query(
            Cancion.titulo,
            Cancion.artista,
            func.count(Cancion.id).label("plays"),
        )
        .filter(
            Cancion.fecha_reproduccion >= datetime.now() - timedelta(days=60),
            Cancion.fecha_reproduccion < datetime.now() - timedelta(days=30),
            Cancion.artista != "Desconocido"
        )
        .group_by(Cancion.titulo, Cancion.artista)
        .order_by(desc("plays"))
        .limit(limit)
        .all()
    )
    
    prev = _assemble_top_from_rows(prev_rows, use_master=False, include_dates=False)
    result = compute_rank_diff(current, prev)
    
    return jsonify(result)


@app.route("/api/stats/timeseries")
def api_timeseries():
    """Serie temporal de reproducciones."""
    hours = int(request.args.get("hours", 24))
    since = datetime.now() - timedelta(hours=hours)
    
    rows = (
        db.session.query(
            func.date_trunc("hour", Cancion.fecha_reproduccion).label("hour"),
            func.count(Cancion.id).label("plays"),
        )
        .filter(
            Cancion.fecha_reproduccion >= since,
            Cancion.artista != "Desconocido"
        )
        .group_by("hour")
        .order_by("hour")
        .all()
    )
    
    return jsonify([
        {
            "hour": r.hour.isoformat(),
            "plays": int(r.plays)
        }
        for r in rows
    ])


@app.route("/api/stats/song/<path:master_key>")
def api_song_detail(master_key):
    """Detalle completo de una canción."""
    artist, title = parse_master_key(master_key)
    
    if not title:
        return jsonify({"error": "Clave inválida"}), 400
    
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
    
    recent = (
        db.session.query(Cancion, Emisora.nombre)
        .outerjoin(Emisora, Emisora.id == Cancion.emisora_id)
        .filter(Cancion.titulo == title, Cancion.artista == artist)
        .order_by(Cancion.fecha_reproduccion.desc())
        .limit(200)
        .all()
    )
    
    recent_plays = [
        {
            "emisora_id": c.Cancion.emisora_id,
            "emisora_nombre": c.nombre,
            "fecha": c.Cancion.fecha_reproduccion.isoformat()
        }
        for c in recent
    ]
    
    per_station = (
        db.session.query(
            Emisora.id,
            Emisora.nombre,
            func.count(Cancion.id).label("plays")
        )
        .join(Cancion, Cancion.emisora_id == Emisora.id)
        .filter(Cancion.titulo == title, Cancion.artista == artist)
        .group_by(Emisora.id, Emisora.nombre)
        .order_by(desc("plays"))
        .limit(50)
        .all()
    )
    
    return jsonify({
        "titulo": title,
        "artista": artist,
        "total_plays": int(total_plays),
        "total_emisoras": count_distinct_emisoras(title, artist),
        "first_play": first_play.isoformat() if first_play else None,
        "last_play": last_play.isoformat() if last_play else None,
        "per_station": [
            {
                "emisora_id": r.id,
                "emisora_nombre": r.nombre,
                "plays": int(r.plays)
            }
            for r in per_station
        ],
        "recent_plays": recent_plays,
    })


@app.route("/api/stats/current_play/<int:emisora_id>")
def api_current_play(emisora_id):
    """Reproducción actual de una emisora."""
    emisora = Emisora.query.get_or_404(emisora_id)
    
    last = (
        Cancion.query
        .filter_by(emisora_id=emisora_id)
        .order_by(Cancion.fecha_reproduccion.desc())
        .first()
    )
    
    if not last:
        current = None
    else:
        current = {
            "titulo": last.titulo,
            "artista": last.artista,
            "fecha_reproduccion": last.fecha_reproduccion.isoformat()
        }
    
    return jsonify({
        "emisora_id": emisora_id,
        "emisora_nombre": emisora.nombre,
        "current": current
    })


# ============================================================================
# COMANDO DE NORMALIZACIÓN (NUEVO)
# ============================================================================

@app.cli.command("normalize-countries")
def normalize_countries_command():
    """
    Comando CLI para normalizar países en la base de datos.
    Uso: flask normalize-countries
    """
    print("🔧 Iniciando normalización de países...")
    
    try:
        emisoras = Emisora.query.all()
        updated = 0
        skipped = 0
        
        for emisora in emisoras:
            if emisora.pais:
                normalized = normalize_country_name(emisora.pais)
                
                if normalized and normalized != emisora.pais:
                    old_name = emisora.pais
                    emisora.pais = normalized
                    updated += 1
                    print(f"  ✓ {old_name} → {normalized}")
                elif not normalized:
                    print(f"  ⚠️  Omitido (inválido): {emisora.pais}")
                    skipped += 1
        
        db.session.commit()
        print(f"\n✅ Normalización completada:")
        print(f"   - {updated} países actualizados")
        print(f"   - {skipped} omitidos")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error: {e}")


# ============================================================================
# COMANDO DE DIAGNÓSTICO DE EMISORAS (NUEVO)
# ============================================================================

# ============================================================================
# COMANDO DE DIAGNÓSTICO DE EMISORAS (NUEVO)
# ============================================================================

@app.cli.command("validate-streams")
@click.option('--emisora-id', type=int, default=None, help='ID de emisora específica')
@click.option('--verbose', is_flag=True, help='Mostrar detalles')
def validate_streams_command(emisora_id=None, verbose=False):
    """
    Comando CLI para validar URLs de streaming de emisoras.
    
    Uso:
      flask validate-streams              # Valida todas
      flask validate-streams --emisora-id 5
      flask validate-streams --verbose    # Con detalles
    """
    if not HAS_VALIDATOR:
        print("[ERROR] El validador de streams no esta disponible")
        return
    
    print("[*] Iniciando validacion de URLs de streaming...\n")
    
    try:
        if emisora_id:
            emisoras = [Emisora.query.get_or_404(emisora_id)]
        else:
            emisoras = Emisora.query.order_by(Emisora.nombre).all()
        
        print(f"[RADIO] Validando {len(emisoras)} emisora(s)...\n")
        
        # Validar
        results = validator.validate_multiple(emisoras, verbose=verbose)
        
        # Actualizar base de datos
        for emisora_id, result in results.items():
            emisora = Emisora.query.get(emisora_id)
            if emisora:
                emisora.url_valida = result['valid']
                emisora.es_stream_activo = result['is_streaming_server']
                emisora.ultima_validacion = datetime.now()
                emisora.diagnostico = result['diagnosis']
        
        db.session.commit()
        
        # Generar reporte
        report = validator.generate_report(emisoras, results)
        print("\n" + report)
        
        # Guardar en archivo
        report_file = os.path.join(os.getcwd(), "tmp", f"diagnostico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📄 Reporte guardado: {report_file}")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


@app.cli.command("get-failing-stations")
def get_failing_stations_command():
    """
    Comando CLI para listar emisoras con pocas metricas/plays.
    Util para identificar emisoras problematicas.
    
    Uso: flask get-failing-stations
    """
    print("[*] Analizando emisoras con pocas metricas...\n")
    
    try:
        # Contar plays por emisora
        plays_per_station = (
            db.session.query(
                Emisora.id,
                Emisora.nombre,
                Emisora.url_stream,
                func.coalesce(func.count(Cancion.id), 0).label("plays"),
            )
            .outerjoin(Cancion, Cancion.emisora_id == Emisora.id)
            .group_by(Emisora.id, Emisora.nombre, Emisora.url_stream)
            .order_by(func.coalesce(func.count(Cancion.id), 0))
            .all()
        )
        
        print("[RADIO] EMISORAS CON POCAS METRICAS (0-2 plays)")
        print("=" * 80)
        
        problematic = [s for s in plays_per_station if s.plays <= 2]
        
        if not problematic:
            print("[OK] Todas las emisoras tienen metricas normales\n")
            return
        
        print(f"[!] Se encontraron {len(problematic)} emisoras problematicas:\n")
        
        for i, station in enumerate(problematic, 1):
            status = "[X]" if station.plays == 0 else "[!]"
            print(f"{i:2}. {status} {station.nombre} ({station.plays} plays)")
            print(f"    URL: {station.url_stream}")
            print()
        
        print("=" * 80)
        print(f"\nTotal problematicas: {len(problematic)}/{len(plays_per_station)}")
        print("\n[TIP] Recomendacion: Ejecute 'flask validate-streams' para diagnosticar URLs\n")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()





# ============================================================================
# NUEVOS ENDPOINTS - MEJORAS SOLICITADAS
# ============================================================================

@app.route("/api/stats/top_by_week")
def api_top_by_week():
    """
    Top canciones por semana específica.
    Query params: week (formato: YYYY-Www, ej: 2025-W45), limit (default: 30)
    """
    week_str = request.args.get("week", "")
    limit = int(request.args.get("limit", 30))
    
    if not week_str:
        return jsonify({"error": "Parámetro 'week' requerido (formato: YYYY-Www)"}), 400
    
    try:
        # Parsear semana: "2025-W45" -> año 2025, semana 45
        import re
        match = re.match(r'(\d{4})-W(\d{2})', week_str)
        if not match:
            return jsonify({"error": "Formato de semana inválido. Usar: YYYY-Www"}), 400
        
        year = int(match.group(1))
        week = int(match.group(2))
        
        # Calcular rango de fechas de esa semana
        from datetime import datetime, timedelta
        # Primer día del año
        jan_1 = datetime(year, 1, 1)
        # Lunes de la semana solicitada
        days_to_monday = (week - 1) * 7 - jan_1.weekday()
        week_start = jan_1 + timedelta(days=days_to_monday)
        week_end = week_start + timedelta(days=7)
        
        # Consultar canciones de esa semana
        rows = (
            db.session.query(
                Cancion.titulo,
                Cancion.artista,
                func.count(Cancion.id).label("plays"),
                func.min(Cancion.fecha_reproduccion).label("first_play"),
                func.max(Cancion.fecha_reproduccion).label("last_play"),
            )
            .filter(
                Cancion.fecha_reproduccion >= week_start,
                Cancion.fecha_reproduccion < week_end,
                Cancion.artista != "Desconocido",
                func.length(Cancion.titulo) >= 3
            )
            .group_by(Cancion.titulo, Cancion.artista)
            .order_by(desc("plays"))
            .limit(limit)
            .all()
        )
        
        data = _assemble_top_from_rows(rows, use_master=False, include_dates=True)
        return jsonify(data)
        
    except Exception as e:
        app.logger.error(f"Error en top_by_week: {e}")
        return jsonify({"error": "Error procesando semana"}), 500


@app.route("/api/manual_song", methods=["POST"])
def api_manual_song():
    """
    Endpoint para registrar canción manualmente.
    TEMPORAL: Se eliminará en el próximo ciclo de actualización.
    
    Body JSON:
    {
        "titulo": "Nombre de la canción",
        "artista": "Nombre del artista",
        "emisora_id": 123
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        # Validar datos
        titulo = data.get("titulo", "").strip()
        artista = data.get("artista", "").strip()
        emisora_id = data.get("emisora_id")
        
        if not titulo:
            return jsonify({"error": "El título es obligatorio"}), 400
        if not artista:
            return jsonify({"error": "El artista es obligatorio"}), 400
        if not emisora_id:
            return jsonify({"error": "La emisora es obligatoria"}), 400
        
        # Convertir emisora_id a entero
        try:
            emisora_id = int(emisora_id)
        except (ValueError, TypeError):
            return jsonify({"error": "ID de emisora inválido"}), 400
        
        # Verificar que la emisora existe
        emisora = Emisora.query.get(emisora_id)
        if not emisora:
            return jsonify({"error": f"Emisora con ID {emisora_id} no encontrada"}), 404
        
        # Crear registro de canción (CORREGIDO: datetime importado al inicio del archivo)
        nueva_cancion = Cancion(
            titulo=titulo,
            artista=artista,
            genero="Manual",  # Marcador especial para identificar registros manuales
            emisora_id=emisora_id,
            fecha_reproduccion=datetime.now()
        )
        
        db.session.add(nueva_cancion)
        
        # Actualizar última canción de la emisora
        emisora.ultima_cancion = f"{artista} - {titulo}"
        emisora.ultima_actualizacion = datetime.now()
        
        db.session.commit()
        
        app.logger.info(f"✅ Canción manual registrada: {artista} - {titulo} en {emisora.nombre}")
        
        return jsonify({
            "success": True,
            "message": "Canción registrada correctamente (temporal)",
            "cancion": {
                "id": nueva_cancion.id,
                "titulo": nueva_cancion.titulo,
                "artista": nueva_cancion.artista,
                "emisora": emisora.nombre,
                "fecha": nueva_cancion.fecha_reproduccion.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"❌ Error registrando canción manual: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


# ============================================================================
# ENDPOINTS DE VALIDACIÓN DE STREAMS (NUEVO)
# ============================================================================

@app.route("/api/validate/stream/<int:emisora_id>")
def api_validate_stream(emisora_id):
    """
    Valida la URL de streaming de una emisora específica.
    
    Returns:
        {
            'emisora_id': int,
            'emisora_nombre': str,
            'url': str,
            'valid': bool,
            'diagnosis': str,
            'details': {...}
        }
    """
    if not HAS_VALIDATOR:
        return jsonify({"error": "Validador no disponible"}), 503
    
    try:
        emisora = Emisora.query.get_or_404(emisora_id)
        
        # Validar URL
        result = validator.validate_url(emisora.url_stream, verbose=False)
        
        # Actualizar emisora con resultado
        emisora.url_valida = result['valid']
        emisora.es_stream_activo = result['is_streaming_server']
        emisora.ultima_validacion = datetime.now()
        emisora.diagnostico = result['diagnosis']
        db.session.commit()
        
        return jsonify({
            'emisora_id': emisora_id,
            'emisora_nombre': emisora.nombre,
            'url': result['url'],
            'valid': result['valid'],
            'diagnosis': result['diagnosis'],
            'details': {
                'status_code': result['status_code'],
                'is_reachable': result['is_reachable'],
                'is_streaming_server': result['is_streaming_server'],
                'response_time_ms': result['response_time_ms'],
                'content_type': result['content_type'],
                'error': result['error'],
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error validando stream: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/validate/all-streams")
def api_validate_all_streams():
    """
    Valida TODAS las URLs de streaming.
    Retorna resumen y lista de problemas.
    """
    if not HAS_VALIDATOR:
        return jsonify({"error": "Validador no disponible"}), 503
    
    try:
        emit_query = request.args.get('filter', 'all')  # 'all', 'problematic'
        
        if emit_query == 'problematic':
            # Solo las que tienen pocas métricas
            emisoras = (
                db.session.query(Emisora)
                .outerjoin(Cancion, Cancion.emisora_id == Emisora.id)
                .group_by(Emisora.id)
                .having(func.coalesce(func.count(Cancion.id), 0) <= 2)
                .all()
            )
        else:
            emisoras = Emisora.query.all()
        
        if not emisoras:
            return jsonify({
                'total': 0,
                'validated': 0,
                'problematic': [],
                'summary': 'No hay emisoras para validar'
            })
        
        # Validar
        results = validator.validate_multiple(emisoras, verbose=False)
        
        # Actualizar base de datos
        for emisora_id, result in results.items():
            emisora = Emisora.query.get(emisora_id)
            if emisora:
                emisora.url_valida = result['valid']
                emisora.es_stream_activo = result['is_streaming_server']
                emisora.ultima_validacion = datetime.now()
                emisora.diagnostico = result['diagnosis']
        
        db.session.commit()
        
        # Compilar respuesta
        problematic_results = [
            {
                'emisora_id': eid,
                'emisora_nombre': next((e.nombre for e in emisoras if e.id == eid), 'Unknown'),
                'url': r['url'],
                'diagnosis': r['diagnosis'],
                'valid': r['valid'],
                'error': r['error']
            }
            for eid, r in results.items()
            if not r['valid']
        ]
        
        return jsonify({
            'total': len(emisoras),
            'validated': len(results),
            'valid': sum(1 for r in results.values() if r['valid']),
            'invalid': sum(1 for r in results.values() if not r['valid']),
            'problematic': problematic_results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error validando todos los streams: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/stations/with-metrics")
def api_stations_with_metrics():
    """
    Retorna todas las emisoras con sus métricas y estado de validación.
    """
    try:
        plays_per_station = (
            db.session.query(
                Emisora.id,
                Emisora.nombre,
                Emisora.url_stream,
                Emisora.pais,
                Emisora.url_valida,
                Emisora.es_stream_activo,
                Emisora.diagnostico,
                func.coalesce(func.count(Cancion.id), 0).label("plays"),
            )
            .outerjoin(Cancion, Cancion.emisora_id == Emisora.id)
            .group_by(
                Emisora.id, Emisora.nombre, Emisora.url_stream,
                Emisora.pais, Emisora.url_valida, Emisora.es_stream_activo,
                Emisora.diagnostico
            )
            .order_by(func.coalesce(func.count(Cancion.id), 0))
            .all()
        )
        
        data = []
        for station in plays_per_station:
            data.append({
                'id': station.id,
                'nombre': station.nombre,
                'url_stream': station.url_stream,
                'pais': station.pais,
                'plays': int(station.plays) if station.plays else 0,
                'url_valida': station.url_valida if station.url_valida is not None else True,
                'es_stream_activo': station.es_stream_activo if station.es_stream_activo is not None else True,
                'diagnostico': station.diagnostico,
                'status': 'critical' if station.plays == 0 else ('warning' if station.plays <= 2 else 'ok'),
            })
        
        return jsonify({
            'total': len(data),
            'critical': sum(1 for s in data if s['plays'] == 0),
            'warning': sum(1 for s in data if 0 < s['plays'] <= 2),
            'ok': sum(1 for s in data if s['plays'] > 2),
            'stations': data
        })
        
    except Exception as e:
        app.logger.error(f"Error obteniendo métricas: {e}")
        return jsonify({"error": str(e)}), 500
"""
=====================================================
📄 RESUMEN DE LOS CAMBIOS IMPLEMENTADOS
=====================================================

Este módulo documenta las actualizaciones recientes en el sistema de monitoreo musical,
incluyendo mejoras en los filtros de estadísticas, el manejo de semanas específicas,
y la funcionalidad para el registro manual de canciones.

Autor: Nicolás Ramírez Villamizar
Fecha: Noviembre 2025
=====================================================
"""


# =====================================================
# 1️⃣ TOP 15, 30, 75
# =====================================================
"""
✔ Se actualizó el selector <select id="top-limit"> para ofrecer tres opciones:
    - 15
    - 30 (valor por defecto)
    - 75

✔ Este selector ahora se aplica a todos los filtros disponibles:
    - Global
    - Por país
    - Por semana

👉 Endpoint afectado: `/api/stats/top_*`
"""


# =====================================================
# 2️⃣ FILTRO SEMANAL
# =====================================================
"""
✔ Nueva opción agregada en el filtro de período:
    - "📅 Semana específica" dentro de <select id="period-filter">

✔ Al seleccionarla, aparece dinámicamente un campo <input type="week">.

✔ Nuevo endpoint implementado:
    GET /api/stats/top_by_week?week=2025-W45&limit=30

✔ El backend interpreta el valor `week=YYYY-Www` para calcular automáticamente:
    - Fecha de inicio (lunes)
    - Fecha de fin (domingo)

✔ Ejemplo:
    week = "2025-W45"
    → Intervalo calculado: lunes 4 nov 2025 – domingo 10 nov 2025

✔ Soporte completo con exportación CSV (funcionalidad ya integrada).
"""


# =====================================================
# 3️⃣ REGISTRO MANUAL DE CANCIONES
# =====================================================
"""
✔ Nuevo botón en el encabezado:
    "➕ Ingresar canción"

✔ Al presionar el botón, se muestra un modal con el siguiente formulario:
    - Nombre de la canción  (obligatorio)
    - Artista              (obligatorio)
    - Emisora              (lista dinámica con todas las emisoras registradas)

✔ Nuevo endpoint:
    POST /api/manual_song

✔ Lógica de registro:
    - Se crea un registro temporal en la tabla `canciones`
    - Campo adicional: genero = "Manual"
    - fecha_reproduccion = NOW()
    - Se actualiza emisora.ultima_cancion

✔ Mecanismo de limpieza:
    - El registro manual se elimina automáticamente en el siguiente ciclo del sistema
      (controlado por un trigger ya existente).

✔ Interfaz:
    - El modal muestra un mensaje de advertencia visible para el usuario
    - Al guardar: notificación tipo “✅ Canción registrada (temporal)”
"""


# =====================================================
# 🎯 CÓMO FUNCIONA (FLUJO DE USUARIO)
# =====================================================

def flujo_filtro_semanal():
    """
    Ejemplo del flujo de uso para el filtro semanal:

        Usuario selecciona: "📅 Semana específica"
        ↓
        Aparece selector: <input type="week">
        ↓
        Usuario elige: 2025-W45
        ↓
        JavaScript llama:
            /api/stats/top_by_week?week=2025-W45&limit=30
        ↓
        Backend calcula:
            Lunes 4 Nov - Domingo 10 Nov 2025
        ↓
        Retorna:
            Top de esa semana específica
    """
    pass


def flujo_registro_manual():
    """
    Ejemplo del flujo de uso para el registro manual:

        Usuario hace clic en: "➕ Ingresar canción"
        ↓
        Se abre el modal con formulario:
            - Canción: "Waka Waka"
            - Artista: "Shakira"
            - Emisora: [Dropdown con 52 emisoras]
        ↓
        Usuario presiona: "💾 Guardar canción"
        ↓
        Envío:
            POST /api/manual_song con JSON
        ↓
        Backend:
            - Inserta registro en `canciones`
            - genero="Manual"
            - fecha_reproduccion=NOW()
            - Actualiza emisora.ultima_cancion
        ↓
        Notificación:
            "✅ Canción registrada (temporal)"
        ↓
        En el próximo ciclo (≈60s):
            Se reemplaza por detección automática.
    """
    pass

# ============================================================================
# INICIALIZACIÓN
# ============================================================================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        app.logger.info("Iniciando monitor de emisoras...")
        start_monitor_thread()
    
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )

# Iniciar monitor también con Gunicorn
try:
    with app.app_context():
        start_monitor_thread()
except Exception as e:
    app.logger.error(f"Error iniciando monitor: {e}")
#!/usr/bin/env python
"""
===================================================================================
RADIO MONITOR - REBUILD MASTER DATA (versión corregida)
===================================================================================
Reconstruye las tablas:
  - canciones_master
  - canciones_por_emisora
a partir de la tabla base `canciones`.

Compatible con SQLAlchemy 2.x (usa text() para queries directas).
===================================================================================
"""

import re
import sys
from datetime import datetime
from collections import defaultdict

from flask import Flask
from sqlalchemy import func, text

# Importar tu configuración y modelos
from config import Config
from utils.db import db
from models.emisoras import Emisora, Cancion, CancionMaster, CancionPorEmisora


# -----------------------------------------------------------------------------------
# Funciones de normalización
# -----------------------------------------------------------------------------------
def normalize_text(s):
    """Normaliza un string para comparar canciones/artistas."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\s*\(.*?\)|\[.*?\]", "", s)  # elimina paréntesis / corchetes
    s = re.sub(r"(feat\.?|ft\.?|featuring)\s+.*$", "", s)  # elimina 'feat'
    s = re.sub(r"[^a-z0-9áéíóúüñ\s]", "", s)  # elimina símbolos
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def build_key(artist, title):
    """Crea una clave única normalizada."""
    return f"{normalize_text(artist)}|||{normalize_text(title)}"


# -----------------------------------------------------------------------------------
# Inicializar app y db
# -----------------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


# -----------------------------------------------------------------------------------
# Lógica principal
# -----------------------------------------------------------------------------------
def rebuild_master():
    app = create_app()
    with app.app_context():
        print("🔄 Reconstruyendo tablas canciones_master y canciones_por_emisora...")

        # Crear tablas si no existen
        db.create_all()

        # Truncar tablas de resumen
        print("🧹 Limpiando datos previos...")
        db.session.execute(text("TRUNCATE TABLE canciones_por_emisora RESTART IDENTITY CASCADE;"))
        db.session.execute(text("TRUNCATE TABLE canciones_master RESTART IDENTITY CASCADE;"))
        db.session.commit()

        # Obtener todas las canciones base
        songs = (
            db.session.query(
                Cancion.titulo,
                Cancion.artista,
                Cancion.emisora_id,
                func.min(Cancion.fecha_reproduccion).label("first_play"),
                func.max(Cancion.fecha_reproduccion).label("last_play"),
                func.count(Cancion.id).label("plays"),
            )
            .group_by(Cancion.titulo, Cancion.artista, Cancion.emisora_id)
            .all()
        )

        if not songs:
            print("⚠️ No se encontraron canciones en la tabla base.")
            return

        print(f"🎶 Procesando {len(songs)} combinaciones canción/emisora...")

        master_map = {}
        per_station = defaultdict(lambda: defaultdict(int))

        # Primera pasada: construir datos agregados
        for s in songs:
            key = build_key(s.artista, s.titulo)
            if key not in master_map:
                master_map[key] = {
                    "titulo": s.titulo,
                    "artista": s.artista,
                    "total_plays": 0,
                    "first_play": s.first_play,
                    "last_play": s.last_play,
                }

            m = master_map[key]
            m["total_plays"] += s.plays
            if not m["first_play"] or s.first_play < m["first_play"]:
                m["first_play"] = s.first_play
            if not m["last_play"] or s.last_play > m["last_play"]:
                m["last_play"] = s.last_play

            per_station[key][s.emisora_id] += s.plays

        # Segunda pasada: insertar en canciones_master
        print("💾 Insertando canciones_master...")
        master_objs = []
        for key, m in master_map.items():
            master = CancionMaster(
                titulo=m["titulo"],
                artista=m["artista"],
                normalized_key=key,
                total_plays=m["total_plays"],
                first_play=m["first_play"],
                last_play=m["last_play"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            master_objs.append(master)

        db.session.bulk_save_objects(master_objs)
        db.session.commit()

        # Crear un índice temporal para buscar ids
        key_to_id = {m.normalized_key: m.id for m in CancionMaster.query.all()}

        # Tercera pasada: insertar canciones_por_emisora
        print("💾 Insertando canciones_por_emisora...")
        rel_objs = []
        for key, emisoras in per_station.items():
            master_id = key_to_id.get(key)
            if not master_id:
                continue
            for emisora_id, plays in emisoras.items():
                rel_objs.append(
                    CancionPorEmisora(
                        master_id=master_id,
                        emisora_id=emisora_id,
                        plays=plays,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

        db.session.bulk_save_objects(rel_objs)
        db.session.commit()

        print(f"✅ {len(master_objs)} registros en canciones_master creados.")
        print(f"✅ {len(rel_objs)} registros en canciones_por_emisora creados.")
        print("🎯 Reconstrucción completada correctamente.")


# -----------------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        rebuild_master()
    except Exception as e:
        print("❌ Error en la reconstrucción:", e)
        sys.exit(1)

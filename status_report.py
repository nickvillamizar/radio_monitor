#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
REPORTE DE ESTADO - POST FIXES
"""
import os
from datetime import datetime, timedelta

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion

print("\n" + "="*120)
print("[REPORTE] ESTADO DEL SISTEMA - POST FIXES")
print("="*120 + "\n")

with app.app_context():
    # Total de emisoras
    total_emisoras = db.session.query(Emisora).count()
    total_canciones = db.session.query(Cancion).count()
    
    print(f"[ESTADÍSTICAS GENERALES]")
    print(f"  Total emisoras en BD: {total_emisoras}")
    print(f"  Total canciones registradas: {total_canciones}")
    
    # Emisoras sin canciones
    zero_song_stations = db.session.query(Emisora).outerjoin(Cancion).group_by(Emisora.id).having(
        db.func.count(Cancion.id) == 0
    ).all()
    print(f"  Emisoras con CERO canciones: {len(zero_song_stations)}")
    
    # Emisoras que actualizaron recientemente
    now = datetime.now()
    recently_updated = db.session.query(Emisora).filter(
        Emisora.ultima_actualizacion > (now - timedelta(days=1))
    ).count()
    print(f"  Emisoras actualizadas en últimas 24h: {recently_updated}")
    
    # Canciones genéricas
    generic_songs = db.session.query(Cancion).filter(
        Cancion.artista == "Artista Desconocido"
    ).count()
    print(f"  Canciones genéricas (\"Desconocido\"): {generic_songs}/{total_canciones}")
    if total_canciones > 0:
        generic_pct = (generic_songs / total_canciones) * 100
        print(f"  Porcentaje de genéricas: {generic_pct:.1f}%")
    
    print("\n" + "-"*120 + "\n")
    
    # Detalle de las 9 emisoras problemáticas
    print("[DETALLE] EMISORAS PROBLEMÁTICAS (9):\n")
    
    problematic_names = [
        "La Excitante",
        "Radio Amboy",
        "Cañar Stereo 97.3 FM",
        "La Mega Star 95.1 FM",
        "Expreso 89.1 FM",
        "La Kalle Sajoma 96.3 FM SJM",
        "La Kalle de Santiago 96.3 Fm",
        "Sabrosa 91.1 Fm",
        "Radio CTC Monción 89.5 FM",
    ]
    
    for nombre in problematic_names:
        station = db.session.query(Emisora).filter(Emisora.nombre.ilike(f"%{nombre}%")).first()
        if station:
            canciones = db.session.query(Cancion).filter_by(emisora_id=station.id).count()
            ultima_act = station.ultima_actualizacion
            dias_sin_act = (now - ultima_act).days if ultima_act else None
            
            print(f"  {nombre}")
            print(f"    - Canciones: {canciones}")
            if ultima_act:
                print(f"    - Última actualización: {ultima_act.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"    - Antigüedad: {dias_sin_act} días")
            if station.ultima_cancion:
                print(f"    - Última canción: {station.ultima_cancion}")
            print()
    
    print("-"*120 + "\n")
    
    # Top 10 emisoras por cantidad de canciones
    print("[TOP 10] EMISORAS MÁS ACTIVAS:\n")
    
    top_stations = db.session.query(Emisora, db.func.count(Cancion.id).label('count')).outerjoin(
        Cancion
    ).group_by(Emisora.id).order_by(db.desc('count')).limit(10).all()
    
    for idx, (station, count) in enumerate(top_stations, 1):
        print(f"  {idx:2d}. {station.nombre:40s} - {count:4d} canciones")
    
    print("\n" + "="*120)
    print("[FIN DEL REPORTE]")
    print("="*120 + "\n")

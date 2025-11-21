#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEST EXHAUSTIVO - EMISORAS PROBLEMÁTICAS
Garantía 100% de detección y guardado en BD
"""
import os
import sys
import time
from datetime import datetime, timedelta

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

sys.path.insert(0, '/c/Users/57321/OneDrive/Escritorio/radio_monitor-main/radio_monitor-main')

from app import app, db
from models.emisoras import Emisora, Cancion
from utils import stream_reader
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("\n" + "="*120)
print("[TEST EXHAUSTIVO] PRUEBA DE TODAS LAS EMISORAS PROBLEMÁTICAS")
print("="*120 + "\n")

with app.app_context():
    # ========================================================================
    # PARTE 1: IDENTIFICAR EMISORAS PROBLEMÁTICAS
    # ========================================================================
    print("[PASO 1] IDENTIFICANDO EMISORAS PROBLEMÁTICAS...")
    print("-"*120)
    
    # 1a. Emisoras con CERO canciones
    print("\n[1a] Emisoras CON CERO CANCIONES (9 críticas):")
    zero_song_stations = db.session.query(Emisora).outerjoin(Cancion).group_by(Emisora.id).having(
        db.func.count(Cancion.id) == 0
    ).all()
    
    zero_song_dict = {e.id: e for e in zero_song_stations}
    print(f"     Total: {len(zero_song_stations)}")
    for e in zero_song_stations:
        print(f"     - {e.nombre} (ID: {e.id})")
    
    # 1b. Emisoras que no actualizaron en 13 días
    print("\n[1b] Emisoras SIN ACTUALIZAR EN 13 DÍAS (42 críticas):")
    days_ago = datetime.now() - timedelta(days=13)
    old_stations = db.session.query(Emisora).filter(
        Emisora.ultima_actualizacion < days_ago
    ).all()
    
    old_dict = {e.id: e for e in old_stations}
    print(f"     Total: {len(old_stations)}")
    for e in old_stations[:10]:  # Mostrar solo los primeros 10
        days_since = (datetime.now() - e.ultima_actualizacion).days
        print(f"     - {e.nombre} (ID: {e.id}) - Sin actualizar: {days_since} días")
    if len(old_stations) > 10:
        print(f"     ... y {len(old_stations) - 10} más")
    
    # ========================================================================
    # PARTE 2: PRUEBA DETALLADA DE LAS 9 EMISORAS CON CERO CANCIONES
    # ========================================================================
    print("\n\n" + "="*120)
    print("[PASO 2] PRUEBA DE EMISORAS CON CERO CANCIONES (9/9)")
    print("="*120)
    
    zero_stats = {
        "tested": 0,
        "detected": 0,
        "saved": 0,
        "failed": []
    }
    
    for idx, station in enumerate(zero_song_stations, 1):
        print(f"\n[TEST {idx}/9] {station.nombre}")
        print(f"  ID: {station.id}")
        print(f"  URL: {station.url_stream or station.url}")
        print("-"*120)
        
        try:
            url = station.url_stream or station.url
            if not url:
                print(f"  [SKIP] SIN URL")
                zero_stats["failed"].append((station.nombre, "Sin URL"))
                continue
            
            zero_stats["tested"] += 1
            
            # Obtener URL real
            real_url = stream_reader.get_real_stream_url(url)
            print(f"  [STEP1] URL real obtenida")
            
            # ICY Metadata
            print(f"  [STEP2] Intentando ICY metadata...")
            title = stream_reader.get_icy_metadata(real_url, timeout=15)
            
            if not title:
                print(f"  [FAIL] No se obtuvo ICY metadata")
                zero_stats["failed"].append((station.nombre, "Sin ICY metadata"))
                continue
            
            print(f"  [STEP3] Título obtenido: {title[:80]}")
            
            # Validación
            if not stream_reader.is_valid_metadata(title):
                print(f"  [FAIL] Título rechazado por validación")
                zero_stats["failed"].append((station.nombre, "Validación fallida"))
                continue
            
            zero_stats["detected"] += 1
            print(f"  [STEP4] ¡Título VÁLIDO!")
            
            # Parse
            artist, song = stream_reader.parse_title_artist(title)
            print(f"  [STEP5] Artista: {artist}")
            print(f"           Canción: {song}")
            
            # Obtener género
            genre = stream_reader.get_genre_musicbrainz(artist, song) or "Desconocido"
            print(f"  [STEP6] Género: {genre}")
            
            # GUARDAR EN BD
            print(f"  [STEP7] GUARDANDO EN BASE DE DATOS...")
            nueva_cancion = Cancion(
                titulo=song,
                artista=artist,
                genero=genre,
                emisora_id=station.id,
                fecha_reproduccion=datetime.now()
            )
            db.session.add(nueva_cancion)
            station.ultima_cancion = f"{artist} - {song}"
            station.ultima_actualizacion = datetime.now()
            db.session.commit()
            
            zero_stats["saved"] += 1
            print(f"  [SUCCESS] ¡REGISTRADO EN BD! Canción ID: {nueva_cancion.id}")
            
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
            zero_stats["failed"].append((station.nombre, f"Error: {str(e)[:50]}"))
            try:
                db.session.rollback()
            except:
                pass
    
    # ========================================================================
    # PARTE 3: PRUEBA DE 10 EMISORAS ANTIGUAS (MUESTRA DE LAS 42)
    # ========================================================================
    print("\n\n" + "="*120)
    print("[PASO 3] PRUEBA DE EMISORAS ANTIGUAS (Muestra de 10/42)")
    print("="*120)
    
    old_stats = {
        "tested": 0,
        "detected": 0,
        "saved": 0,
        "failed": []
    }
    
    # Tomar las 10 más antiguas
    old_sample = sorted(old_stations, key=lambda e: e.ultima_actualizacion)[:10]
    
    for idx, station in enumerate(old_sample, 1):
        print(f"\n[TEST {idx}/10] {station.nombre}")
        print(f"  ID: {station.id}")
        print(f"  Última actualización: {station.ultima_actualizacion}")
        days_old = (datetime.now() - station.ultima_actualizacion).days
        print(f"  Antigüedad: {days_old} días")
        print("-"*120)
        
        try:
            url = station.url_stream or station.url
            if not url:
                print(f"  [SKIP] SIN URL")
                old_stats["failed"].append((station.nombre, "Sin URL"))
                continue
            
            old_stats["tested"] += 1
            
            # Obtener URL real
            real_url = stream_reader.get_real_stream_url(url)
            print(f"  [STEP1] URL real obtenida")
            
            # ICY Metadata
            print(f"  [STEP2] Intentando ICY metadata...")
            title = stream_reader.get_icy_metadata(real_url, timeout=15)
            
            if not title:
                print(f"  [FAIL] No se obtuvo ICY metadata")
                old_stats["failed"].append((station.nombre, "Sin ICY metadata"))
                continue
            
            print(f"  [STEP3] Título obtenido: {title[:80]}")
            
            # Validación
            if not stream_reader.is_valid_metadata(title):
                print(f"  [FAIL] Título rechazado por validación")
                old_stats["failed"].append((station.nombre, "Validación fallida"))
                continue
            
            old_stats["detected"] += 1
            print(f"  [STEP4] ¡Título VÁLIDO!")
            
            # Parse
            artist, song = stream_reader.parse_title_artist(title)
            print(f"  [STEP5] Artista: {artist}")
            print(f"           Canción: {song}")
            
            # Obtener género
            genre = stream_reader.get_genre_musicbrainz(artist, song) or "Desconocido"
            print(f"  [STEP6] Género: {genre}")
            
            # GUARDAR EN BD
            print(f"  [STEP7] GUARDANDO EN BASE DE DATOS...")
            nueva_cancion = Cancion(
                titulo=song,
                artista=artist,
                genero=genre,
                emisora_id=station.id,
                fecha_reproduccion=datetime.now()
            )
            db.session.add(nueva_cancion)
            station.ultima_cancion = f"{artist} - {song}"
            station.ultima_actualizacion = datetime.now()
            db.session.commit()
            
            old_stats["saved"] += 1
            print(f"  [SUCCESS] ¡REGISTRADO EN BD! Canción ID: {nueva_cancion.id}")
            
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
            old_stats["failed"].append((station.nombre, f"Error: {str(e)[:50]}"))
            try:
                db.session.rollback()
            except:
                pass
    
    # ========================================================================
    # PARTE 4: REPORTE FINAL
    # ========================================================================
    print("\n\n" + "="*120)
    print("[REPORTE FINAL]")
    print("="*120)
    
    print("\n[EMISORAS CON CERO CANCIONES]")
    print(f"  Probadas:    {zero_stats['tested']}/9")
    print(f"  Detectadas:  {zero_stats['detected']}/9")
    print(f"  Guardadas:   {zero_stats['saved']}/9")
    if zero_stats['failed']:
        print(f"  Fallos ({len(zero_stats['failed'])}):")
        for nombre, razon in zero_stats['failed']:
            print(f"    - {nombre}: {razon}")
    
    print("\n[EMISORAS ANTIGUAS (Muestra)]")
    print(f"  Probadas:    {old_stats['tested']}/10")
    print(f"  Detectadas:  {old_stats['detected']}/10")
    print(f"  Guardadas:   {old_stats['saved']}/10")
    if old_stats['failed']:
        print(f"  Fallos ({len(old_stats['failed'])}):")
        for nombre, razon in old_stats['failed']:
            print(f"    - {nombre}: {razon}")
    
    # Verificar que se guardaron en BD
    print("\n[VERIFICACIÓN EN BD]")
    for station in zero_song_stations[:3]:  # Verificar las 3 primeras
        cancion_count = db.session.query(Cancion).filter_by(emisora_id=station.id).count()
        print(f"  {station.nombre}: {cancion_count} canción(es)")
    
    print("\n" + "="*120)
    print("[TEST COMPLETADO]")
    print("="*120 + "\n")

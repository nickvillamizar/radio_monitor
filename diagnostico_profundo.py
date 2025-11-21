import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta
import sys

with app.app_context():
    print("\n" + "="*80)
    print("DIAGNOSTICO PROFUNDO DEL SISTEMA DE DETECCION")
    print("="*80 + "\n")
    
    # 1. VERIFICAR ESTADO DE LA BD
    print("[1] ESTADO DE BASE DE DATOS")
    print("-" * 80)
    total = db.session.query(Emisora).count()
    print(f"Total de emisoras registradas: {total}")
    
    # 2. VERIFICAR QUE ACTUALIZO EN ULTIMAS 24 HORAS
    print("\n[2] EMISORAS ACTUALIZADAS EN ÚLTIMAS 24 HORAS")
    print("-" * 80)
    recent = datetime.now() - timedelta(hours=24)
    updated_24h = db.session.query(Emisora).filter(Emisora.ultima_actualizacion >= recent).count()
    print(f"Actualizadas hace 24h: {updated_24h}/{total}")
    
    # 3. VERIFICAR QUE ACTUALIZO EN ULTIMAS 48 HORAS
    print("\n[3] EMISORAS ACTUALIZADAS EN ÚLTIMAS 48 HORAS")
    print("-" * 80)
    recent_48 = datetime.now() - timedelta(hours=48)
    updated_48h = db.session.query(Emisora).filter(Emisora.ultima_actualizacion >= recent_48).count()
    print(f"Actualizadas hace 48h: {updated_48h}/{total}")
    
    # 4. CUALES SON LAS MAS ANTIGUAS
    print("\n[4] TOP 15 EMISORAS CON ACTUALIZACION MAS ANTIGUA")
    print("-" * 80)
    oldest = db.session.query(Emisora).order_by(Emisora.ultima_actualizacion).limit(15).all()
    for idx, e in enumerate(oldest, 1):
        dias = (datetime.now() - e.ultima_actualizacion).days if e.ultima_actualizacion else None
        ultima_cancion = (e.ultima_cancion[:50] + "...") if e.ultima_cancion and len(e.ultima_cancion) > 50 else e.ultima_cancion
        print(f"{idx:2d}. {e.nombre:40s} | {dias:3d} días | {ultima_cancion}")
    
    # 5. VERIFICAR REPRODUCCIONES
    print("\n[5] ESTADÍSTICAS DE REPRODUCCIONES")
    print("-" * 80)
    total_canciones = db.session.query(Cancion).count()
    print(f"Total de canciones registradas: {total_canciones}")
    
    # 6. VERIFICAR CANCIONES VACIAS O GENÉRICAS
    print("\n[6] CANCIONES GENÉRICAS (PROBLEMA)")
    print("-" * 80)
    genericas = db.session.query(Cancion).filter(
        (Cancion.artista.like('%Desconocido%')) | 
        (Cancion.titulo.like('%Transmisión%')) |
        (Cancion.artista == 'Artista Desconocido')
    ).count()
    print(f"Canciones con 'Desconocido' o genéricas: {genericas}/{total_canciones}")
    
    # 7. BUSCAR EMISION SIN CANCIONES
    print("\n[7] EMISORAS SIN CANCIONES (CRÍTICO)")
    print("-" * 80)
    sin_canciones = []
    for e in db.session.query(Emisora).all():
        cancion_count = db.session.query(Cancion).filter(Cancion.emisora_id == e.id).count()
        if cancion_count == 0:
            sin_canciones.append(e)
    
    print(f"Emisoras sin NINGUNA canción: {len(sin_canciones)}/{total}")
    for e in sin_canciones[:10]:
        print(f"  - {e.nombre} | URL: {e.url_stream[:60]}...")
    
    # 8. VERIFICAR URLs VALIDAS
    print("\n[8] ANÁLISIS DE URLs")
    print("-" * 80)
    sin_url = db.session.query(Emisora).filter((Emisora.url_stream == None) | (Emisora.url_stream == '')).count()
    print(f"Emisoras sin URL: {sin_url}/{total}")
    
    # 9. ESTADO ACTUAL
    print("\n[9] RESUMEN DE ESTADO")
    print("-" * 80)
    print(f"[OK] Total emisoras: {total}")
    print(f"[OK] Actualizadas 24h: {updated_24h}")
    print(f"[OK] Actualizadas 48h: {updated_48h}")
    print(f"[OK] Total canciones: {total_canciones}")
    print(f"[OK] Canciones genéricas: {genericas}")
    print(f"[OK] Emisoras sin canciones: {len(sin_canciones)}")
    print(f"[OK] Emisoras sin URL: {sin_url}")
    
    print("\n" + "="*80)
    print("FIN DEL DIAGNÓSTICO")
    print("="*80 + "\n")

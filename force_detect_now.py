#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FORZAR DETECCIÓN INMEDIATA - Ejecuta un ciclo de detección manual
Uso: python force_detect_now.py
"""
import os
import sys
from datetime import datetime

# Configurar DATABASE_URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from utils import stream_reader

print("\n" + "="*100)
print("🚀 FORZANDO CICLO DE DETECCIÓN MANUAL - Radio Monitor")
print("="*100)
print(f"Fecha/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("\nEsto escaneará TODAS las emisoras y detectará canciones en tiempo real.")
print("Tiempo estimado: 5-10 minutos para 71 emisoras\n")

with app.app_context():
    # Estadísticas ANTES
    print("[PASO 1] Estadísticas ANTES de la detección")
    print("-" * 100)
    
    total_canciones_antes = db.session.query(Cancion).count()
    emisoras_activas = db.session.query(Emisora).filter(
        Emisora.ultima_actualizacion.isnot(None)
    ).count()
    
    print(f"  Canciones totales: {total_canciones_antes}")
    print(f"  Emisoras con datos: {emisoras_activas}/71")
    print()
    
    # EJECUTAR DETECCIÓN
    print("[PASO 2] Ejecutando detección en TODAS las emisoras...")
    print("-" * 100)
    print("🔍 Escaneando streams de radio...\n")
    
    try:
        # Ejecutar actualización con fallback a AudD
        stream_reader.actualizar_emisoras(
            fallback_to_audd=True,
            dedupe_seconds=300
        )
        print("\n✅ [OK] Ciclo de detección completado exitosamente!")
    except Exception as e:
        print(f"\n❌ [ERROR] Falló la detección: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Estadísticas DESPUÉS
    print("\n[PASO 3] Estadísticas DESPUÉS de la detección")
    print("-" * 100)
    
    total_canciones_despues = db.session.query(Cancion).count()
    emisoras_activas_despues = db.session.query(Emisora).filter(
        Emisora.ultima_actualizacion.isnot(None)
    ).count()
    
    nuevas_canciones = total_canciones_despues - total_canciones_antes
    
    print(f"  Canciones totales: {total_canciones_despues}")
    print(f"  Emisoras con datos: {emisoras_activas_despues}/71")
    print(f"  Nuevas canciones detectadas: +{nuevas_canciones}")
    
    # Mostrar últimas 10 canciones detectadas
    if nuevas_canciones > 0:
        print("\n[🎵 ÚLTIMAS 10 CANCIONES DETECTADAS]")
        print("-" * 100)
        
        ultimas = db.session.query(Cancion, Emisora).join(
            Emisora, Emisora.id == Cancion.emisora_id
        ).order_by(
            Cancion.fecha_reproduccion.desc()
        ).limit(10).all()
        
        for idx, (cancion, emisora) in enumerate(ultimas, 1):
            print(f"{idx:2d}. {cancion.artista} - {cancion.titulo}")
            print(f"    Emisora: {emisora.nombre}")
            print(f"    Fecha: {cancion.fecha_reproduccion.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    
    print("="*100)
    print("✅ DETECCIÓN COMPLETA - Puedes ver los resultados en: https://app.rastreadormusical.com/")
    print("="*100 + "\n")

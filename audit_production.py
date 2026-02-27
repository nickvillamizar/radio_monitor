#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AUDITORÍA EXHAUSTIVA DEL SISTEMA DE DETECCIÓN DE EMISORAS
=========================================================
Verifica que el sistema esté listo para producción.
"""

import os
import sys
from datetime import datetime, timedelta

# Setup environment
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL', 
    'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'))

from app import app
from utils.db import db
from models.emisoras import Emisora, Cancion
from sqlalchemy import func

print("\n" + "="*100)
print(" "*30 + "AUDITORÍA DE PRODUCCIÓN - RADIO MONITOR")
print("="*100 + "\n")

with app.app_context():
    # ==================== PASO 1: ESTADÍSTICAS GENERALES ====================
    print("[1/7] ESTADÍSTICAS GENERALES")
    print("-" * 100)
    
    total_emisoras = db.session.query(func.count(Emisora.id)).scalar() or 0
    total_canciones = db.session.query(func.count(Cancion.id)).scalar() or 0
    total_artistas_distintos = db.session.query(func.count(Cancion.artista.distinct())).filter(
        Cancion.artista != "Desconocido"
    ).scalar() or 0
    
    print(f"  Total de emisoras en BD:      {total_emisoras}")
    print(f"  Total de canciones registradas: {total_canciones}")
    print(f"  Total de artistas distintos:  {total_artistas_distintos}")
    print()
    
    # ==================== PASO 2: VERIFICAR EMISORAS PROBLEMÁTICAS ====================
    print("[2/7] VERIFICAR EMISORAS PROBLEMÁTICAS")
    print("-" * 100)
    
    problem_ids = [228, 46, 43, 39, 37, 35, 34, 30, 27]
    problem_names = {
        228: 'Montonestv 88.3 Fm',
        46: 'Radio CTC Moncion',
        43: 'Lider 92.7 Fm',
        39: 'La Kalle 96.3 FM Bani',
        37: 'Turbo 98 FM',
        35: 'La Kalle 96.3 Santiago de los caballero',
        34: 'La Kalle Sajoma 96.3 FM',
        30: 'La Kalle Sabana Grande',
        27: 'La Kalle Santiago Rodríguez'
    }
    
    problem_status = {}
    for eid in problem_ids:
        e = Emisora.query.get(eid)
        if e:
            plays = db.session.query(func.count(Cancion.id)).filter(
                Cancion.emisora_id == eid
            ).scalar() or 0
            
            # Últimas 3 canciones
            last_songs = db.session.query(Cancion.artista, Cancion.titulo).filter(
                Cancion.emisora_id == eid
            ).order_by(Cancion.fecha_reproduccion.desc()).limit(3).all()
            
            status = "✅ BIEN" if plays > 0 else "❌ SIN CANCIONES"
            problem_status[eid] = {'nombre': e.nombre, 'plays': plays, 'status': status}
            
            print(f"  [{eid:3}] {e.nombre[:50]:50} | {plays:4} plays | {status}")
            if last_songs:
                for i, (artist, title) in enumerate(last_songs, 1):
                    print(f"         {i}. {artist} - {title}")
        else:
            print(f"  [{eid:3}] ❌ NO ENCONTRADA EN BD")
    
    print()
    
    # ==================== PASO 3: EMISORAS CON POCAS MÉTRICAS ====================
    print("[3/7] DIAGNOSTICO DE EMISORAS CON POCAS MÉTRICAS (0-5 plays)")
    print("-" * 100)
    
    low_metrics = (
        db.session.query(
            Emisora.id,
            Emisora.nombre,
            func.count(Cancion.id).label("plays")
        )
        .outerjoin(Cancion, Cancion.emisora_id == Emisora.id)
        .group_by(Emisora.id, Emisora.nombre)
        .having(func.count(Cancion.id) <= 5)
        .order_by(func.count(Cancion.id))
        .all()
    )
    
    if low_metrics:
        print(f"  Se encontraron {len(low_metrics)} emisoras con ≤5 plays:")
        for e_id, nombre, plays in low_metrics[:10]:  # Mostrar primeras 10
            print(f"    [{e_id:3}] {nombre:50} | {plays} plays")
        if len(low_metrics) > 10:
            print(f"    ... y {len(low_metrics) - 10} más")
    else:
        print("  ✅ EXCELENTE: Todas las emisoras tienen buen registro")
    
    print()
    
    # ==================== PASO 4: TOP CANCIONES GLOBAL ====================
    print("[4/7] TOP 10 CANCIONES GLOBALES")
    print("-" * 100)
    
    top_songs = (
        db.session.query(
            Cancion.artista,
            Cancion.titulo,
            func.count(Cancion.id).label("plays")
        )
        .filter(
            Cancion.artista != "Desconocido",
            func.length(Cancion.titulo) >= 3
        )
        .group_by(Cancion.artista, Cancion.titulo)
        .order_by(func.count(Cancion.id).desc())
        .limit(10)
        .all()
    )
    
    if top_songs:
        for i, (artist, title, plays) in enumerate(top_songs, 1):
            print(f"  {i:2}. [{plays:3} plays] {artist} - {title}")
    else:
        print("  ⚠️ Sin canciones registradas aún")
    
    print()
    
    # ==================== PASO 5: CALIDAD DE DATOS ====================
    print("[5/7] AUDITORÍA DE CALIDAD DE DATOS")
    print("-" * 100)
    
    # Contar registros con artista "Desconocido"
    unknown_count = db.session.query(func.count(Cancion.id)).filter(
        Cancion.artista.in_(["Desconocido", "Artista Desconocido"])
    ).scalar() or 0
    
    # Contar registros con fuente marcada
    with_source = db.session.query(func.count(Cancion.id)).filter(
        Cancion.fuente.isnot(None),
        Cancion.fuente != ""
    ).scalar() or 0
    
    # Contar canciones únicas por emisora
    avg_songs_per_station = db.session.query(
        func.avg(db.session.query(func.count(Cancion.id)).filter(
            Cancion.emisora_id == Emisora.id
        ).correlate(Emisora).scalar() or 0)
    ).select_from(Emisora).scalar() or 0
    
    total_data = total_canciones
    unknown_pct = (unknown_count / total_data * 100) if total_data > 0 else 0
    source_pct = (with_source / total_data * 100) if total_data > 0 else 0
    
    print(f"  Total registros con 'Desconocido':  {unknown_count:5} ({unknown_pct:.1f}%)")
    print(f"  Registros con fuente identificada: {with_source:5} ({source_pct:.1f}%)")
    print(f"  Promedio canciones por emisora:    {avg_songs_per_station:.1f}")
    print()
    
    # Evaluación
    if unknown_pct < 20 and source_pct > 70:
        print("  ✅ EXCELENTE: Calidad de datos muy buena")
    elif unknown_pct < 30 and source_pct > 60:
        print("  ⚠️ ACEPTABLE: Calidad buena, pero margen de mejora")
    else:
        print("  ⚠️ REVISAR: Calidad de datos podría mejorar")
    
    print()
    
    # ==================== PASO 6: TENDENCIAS RECIENTES ====================
    print("[6/7] TENDENCIAS ÚLTIMAS 24 HORAS")
    print("-" * 100)
    
    last_24h = datetime.now() - timedelta(hours=24)
    recent_count = db.session.query(func.count(Cancion.id)).filter(
        Cancion.fecha_reproduccion >= last_24h
    ).scalar() or 0
    
    last_7d = datetime.now() - timedelta(days=7)
    week_count = db.session.query(func.count(Cancion.id)).filter(
        Cancion.fecha_reproduccion >= last_7d
    ).scalar() or 0
    
    print(f"  Canciones últimas 24h:  {recent_count}")
    print(f"  Canciones últimos 7 días: {week_count}")
    
    # Calcular velocidad de ingreso
    if recent_count > 0 and total_canciones > 0:
        rate = recent_count / 24  # por hora
        print(f"  Velocidad de ingreso:   {rate:.1f} canciones/hora")
        if rate > 1:
            print("  ✅ EXCELENTE: Sistema registrando activamente")
        elif rate > 0.5:
            print("  ⚠️ MODERADO: Ingreso lento")
        else:
            print("  ⚠️ LENTO: Verificar problemas de detección")
    
    print()
    
    # ==================== PASO 7: EMISORAS CRÍTICAS ====================
    print("[7/7] RESUMEN FINAL Y RECOMENDACIONES")
    print("-" * 100)
    
    # Contar emisoras sin canciones
    no_songs = db.session.query(func.count(Emisora.id)).filter(
        ~Emisora.id.in_(
            db.session.query(Cancion.emisora_id.distinct()).select_from(Cancion)
        )
    ).scalar() or 0
    
    print(f"\n  📊 RESUMEN EJECUTIVO:")
    print(f"     - Total emisoras activas:     {total_emisoras - no_songs}/{total_emisoras}")
    print(f"     - Canciones registradas:     {total_canciones}")
    print(f"     - Artistas únicos:           {total_artistas_distintos}")
    print(f"     - Calidad de datos:          {100 - unknown_pct:.1f}% (objetivo: >80%)")
    
    # Estado de emisoras problemáticas
    problematic_detected = sum(1 for s in problem_status.values() if s['plays'] > 0)
    print(f"\n  🔍 EMISORAS MONITOREADAS:")
    print(f"     - Total monitoreo específico: {len(problem_ids)}")
    print(f"     - Detectando correctamente:  {problematic_detected}/{len(problem_ids)}")
    
    if problematic_detected == len(problem_ids):
        print(f"     ✅ PERFECTO: Todas las emisoras críticas funcionando")
    elif problematic_detected >= len(problem_ids) - 2:
        print(f"     ⚠️ BIEN: La mayoría funcionando")
    else:
        print(f"     ⚠️ REVISAR: Detectar más emisoras")
    
    # Recomendaciones
    print(f"\n  📋 RECOMENDACIONES:")
    if no_songs > 5:
        print(f"     - Revisar {no_songs} emisoras sin detecciones")
    if unknown_pct > 15:
        print(f"     - Mejorar limpieza de metadata (actualmente {unknown_pct:.1f}% desconocido)")
    if recent_count < 5:
        print(f"     - Sistema actualmente lento; esperar ciclos adicionales")
    
    if no_songs <= 3 and unknown_pct < 20 and problematic_detected >= len(problem_ids) - 1:
        print(f"     ✅ SISTEMA LISTO PARA PRODUCCIÓN")

print("\n" + "="*100)
print(" "*40 + "FIN DE AUDITORÍA")
print("="*100 + "\n")

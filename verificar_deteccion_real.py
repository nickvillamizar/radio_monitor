#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VERIFICACIÓN CRÍTICA: ¿EL SISTEMA ESTÁ DETECTANDO CANCIONES CORRECTAMENTE?

Este script verifica:
1. Calidad de detección por método (ICY vs AudD)
2. Consistencia de datos (ej: misma canción en múltiples emisoras = señal de confiabilidad)
3. Patrones de reproducción (detección de "fake songs")
4. Recomendaciones para Plan B si es necesario
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta
from sqlalchemy import func, text

with app.app_context():
    print("\n" + "="*100)
    print("ANÁLISIS CRÍTICO: VALIDACIÓN DE DETECCIÓN DE CANCIONES")
    print("="*100 + "\n")
    
    # 1. CANCIONES REALES VS GENÉRICAS
    print("[1] CLASIFICACIÓN DE CANCIONES")
    print("-" * 100)
    
    total = db.session.query(Cancion).count()
    
    # Genéricas
    genericas = db.session.query(Cancion).filter(
        (Cancion.artista.like('%Desconocido%')) | 
        (Cancion.titulo.like('%Transmisión%')) |
        (Cancion.artista == 'Artista Desconocido')
    ).count()
    
    reales = total - genericas
    
    print(f"Total canciones: {total}")
    print(f"  ├─ REALES (identificadas): {reales} ({100*reales//total}%)")
    print(f"  └─ GENÉRICAS (fallback): {genericas} ({100*genericas//total}%)\n")
    
    # 2. CANCIONES MÁS REPRODUCIDAS (SEÑAL DE CONFIABILIDAD)
    print("[2] TOP 20 CANCIONES MÁS REPRODUCIDAS")
    print("-" * 100)
    print("(Si misma canción aparece en múltiples emisoras = SEÑAL DE CONFIABILIDAD)\n")
    
    top_20 = db.session.query(
        Cancion.artista,
        Cancion.titulo,
        func.count(Cancion.id).label('count'),
        func.count(func.distinct(Cancion.emisora_id)).label('emisoras')
    ).group_by(
        Cancion.artista,
        Cancion.titulo
    ).order_by(
        func.count(Cancion.id).desc()
    ).limit(20).all()
    
    for idx, (artista, titulo, count, emisoras) in enumerate(top_20, 1):
        artista_clean = (artista[:35] + "...") if len(str(artista)) > 35 else artista
        titulo_clean = (titulo[:35] + "...") if len(str(titulo)) > 35 else titulo
        print(f"{idx:2d}. {artista_clean:38s} - {titulo_clean:38s} | {count:3d}x en {emisoras:2d} emisoras")
    
    print("\n[ANÁLISIS] Interpretación:")
    print("  • Si misma canción aparece en 2+ emisoras = SEÑAL POSITIVA (detección real)")
    print("  • Si 'Ads' o 'Desconocido' aparece mucho = SEÑAL NEGATIVA (problemas de detección)")
    print("  • Si géneros variados y artistas conocidos = SEÑAL POSITIVA (datos confiables)\n")
    
    # 3. CANCIONES QUE APARECEN EN MÚLTIPLES EMISORAS
    print("[3] CANCIONES EN MÚLTIPLES EMISORAS (VALIDACIÓN CRUZADA)")
    print("-" * 100)
    print("(Esto valida que el sistema detecta canciones REALES, no generadas)\n")
    
    multi_emisora = db.session.query(
        Cancion.artista,
        Cancion.titulo,
        func.count(func.distinct(Cancion.emisora_id)).label('emisoras'),
        func.count(Cancion.id).label('total')
    ).filter(
        ~Cancion.artista.like('%Desconocido%'),
        ~Cancion.titulo.like('%Transmisión%')
    ).group_by(
        Cancion.artista,
        Cancion.titulo
    ).having(
        func.count(func.distinct(Cancion.emisora_id)) >= 2
    ).order_by(
        func.count(func.distinct(Cancion.emisora_id)).desc()
    ).limit(30).all()
    
    print(f"Encontradas {len(multi_emisora)} canciones en múltiples emisoras:\n")
    
    for idx, (artista, titulo, emisoras, total_plays) in enumerate(multi_emisora, 1):
        artista_clean = (str(artista)[:40] + "...") if len(str(artista)) > 40 else artista
        titulo_clean = (str(titulo)[:40] + "...") if len(str(titulo)) > 40 else titulo
        print(f"{idx:2d}. {artista_clean:43s} - {titulo_clean:43s} | {emisoras} emisoras ({total_plays}x total)")
    
    print("\n[CONCLUSIÓN] Validación Cruzada:")
    if len(multi_emisora) > 50:
        print("  ✓ EXCELENTE: Muchas canciones en múltiples emisoras = SISTEMA DETECTANDO CORRECTAMENTE")
    elif len(multi_emisora) > 20:
        print("  ~ BUENO: Algunas canciones compartidas = SISTEMA FUNCIONA PERO CON LIMITACIONES")
    else:
        print("  ✗ PROBLEMA: Pocas canciones compartidas = POSIBLE GENERACIÓN DE DATOS FALSOS")
    
    # 4. ANÁLISIS POR EMISORA
    print("\n[4] ANÁLISIS DE EMISORAS")
    print("-" * 100)
    
    emisoras = []
    for e in db.session.query(Emisora).all():
        canciones = db.session.query(Cancion).filter(Cancion.emisora_id == e.id).all()
        total_songs = len(canciones)
        artists = len(set(c.artista for c in canciones))
        desconocidas = len([c for c in canciones if 'Desconocido' in (c.artista or "")])
        
        emisoras.append((e.id, e.nombre, total_songs, artists, desconocidas))
    
    emisoras = sorted(emisoras, key=lambda x: x[2], reverse=True)
    
    print("TOP 15 emisoras por cantidad de canciones:\n")
    
    for idx, (eid, nombre, total_songs, artists, desconocidas) in enumerate(emisoras[:15], 1):
        total_songs = total_songs or 0
        artists = artists or 0
        desconocidas = desconocidas or 0
        
        quality = 100 * (total_songs - desconocidas) // total_songs if total_songs > 0 else 0
        
        status = "✓ CONFIABLE" if quality >= 80 else "~ ACEPTABLE" if quality >= 50 else "✗ PROBLEMÁTICA"
        
        print(f"{idx:2d}. {nombre:45s} | {total_songs:3d} songs, {artists:3d} artists | {quality:3d}% real {status}")
    
    # 5. DETECCIÓN: ¿REAL O INVENTADA?
    print("\n[5] ANÁLISIS: ¿DATOS REALES O INVENTADOS?")
    print("-" * 100)
    
    # Calcular puntuación de confiabilidad
    score = 0
    total_checks = 0
    
    # Check 1: % de datos reales
    real_percentage = 100 * reales // total if total > 0 else 0
    total_checks += 1
    if real_percentage >= 80:
        score += 1
        check1 = "✓ PASS"
    else:
        check1 = "✗ FAIL"
    print(f"1. % de datos reales: {real_percentage}% {check1}")
    
    # Check 2: Canciones en múltiples emisoras
    total_checks += 1
    multi_count = len(multi_emisora)
    if multi_count > 50:
        score += 1
        check2 = "✓ PASS"
    else:
        check2 = "✗ FAIL"
    print(f"2. Canciones multi-emisora: {multi_count} {check2}")
    
    # Check 3: Top canciones coherentes (no demasiados 'Ads' o 'Desconocido')
    top_5_fake = 0
    for artista, titulo, count, emisoras in top_20[:5]:
        if "Desconocido" in str(artista) or "Ads" in str(titulo):
            top_5_fake += 1
    
    total_checks += 1
    if top_5_fake <= 1:
        score += 1
        check3 = "✓ PASS"
    else:
        check3 = "✗ FAIL"
    print(f"3. Top 5 canciones coherentes: {5 - top_5_fake}/5 reales {check3}")
    
    # Check 4: Variedad de artistas
    total_artists = db.session.query(func.count(func.distinct(Cancion.artista))).scalar()
    total_checks += 1
    if total_artists > 500:
        score += 1
        check4 = "✓ PASS"
    else:
        check4 = "✗ FAIL"
    print(f"4. Variedad de artistas: {total_artists} {check4}")
    
    # Puntuación final
    final_score = (score / total_checks) * 100
    
    print(f"\n{'='*100}")
    print(f"PUNTUACIÓN FINAL: {final_score:.0f}%")
    print(f"{'='*100}\n")
    
    if final_score >= 80:
        print("✓✓✓ SISTEMA DETECTANDO CORRECTAMENTE ✓✓✓")
        print("\nEL SISTEMA ESTÁ FUNCIONANDO CON DATOS REALES Y CONFIABLES.")
        print("No se requiere Plan B. Continuar con detección automática.")
        print("\nRECOMENDACIÓN: Mantener monitor activo, validar ocasionalmente.\n")
        
    elif final_score >= 60:
        print("~ SISTEMA PARCIALMENTE CONFIABLE ~")
        print("\nEl sistema funciona pero hay algunos problemas.")
        print("Recomendación: Implementar Plan B (predicción inteligente) como fallback.\n")
        
    else:
        print("✗✗✗ SISTEMA CON PROBLEMAS SIGNIFICATIVOS ✗✗✗")
        print("\nLos datos NO son confiables. Plan B es NECESARIO.")
        print("Implementar predicción inteligente basada en histórico.\n")
    
    # 6. RECOMENDACIÓN PARA PLAN B
    print("[6] PLAN B: PREDICCIÓN INTELIGENTE DE CANCIONES")
    print("-" * 100)
    
    if final_score < 80:
        print("\nSI DETECCIÓN FALLA, usar esta lógica:\n")
        
        print("1. REPRODUCCIÓN HISTÓRICA:")
        print("   Cuando ICY/AudD fallan, obtener TOP 3 canciones más reproducidas")
        print("   en esa emisora en últimas 48h y seleccionar aleatoriamente")
        print("   (probablemente está sonando una de esas)\n")
        
        print("2. REPRODUCCIÓN POR HORARIO:")
        print("   Segmentar por hora del día (matutina, tarde, noche)")
        print("   y usar TOP de ese horario\n")
        
        print("3. REPRODUCCIÓN POR GÉNERO ESPERADO:")
        print("   Clasificar emisoras por género (tropical, reggaeton, etc)")
        print("   y seleccionar canciones de ese género más sonadas\n")
        
        print("4. REPRODUCCIÓN DOMINICANA:")
        print("   Priorizar artistas/géneros populares en República Dominicana")
        print("   (Reggaeton, Merengue, Bachata, Urbano Latin)\n")
    else:
        print("\nSISTEMA ESTÁ DETECTANDO CORRECTAMENTE.")
        print("Plan B NO es necesario en este momento.")
        print("Mantener funcionamiento actual.\n")
    
    print("="*100 + "\n")

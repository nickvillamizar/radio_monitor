#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Análisis de las 19 emisoras que AÚN NO tienen canciones detectadas.
Esto es CRÍTICO para identificar si es URL, ICY metadata, o AudD.
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime
import requests
import sys

with app.app_context():
    print("\n" + "="*120)
    print("ANÁLISIS CRÍTICO: 19 EMISORAS SIN CANCIONES DESPUÉS DE AUDD")
    print("="*120 + "\n")
    
    # Obtener todas las emisoras
    all_emisoras = db.session.query(Emisora).all()
    
    # Identificar cuáles no tienen canciones
    sin_canciones = []
    for e in all_emisoras:
        cancion_count = db.session.query(Cancion).filter(Cancion.emisora_id == e.id).count()
        if cancion_count == 0:
            sin_canciones.append(e)
    
    print(f"[CRÍTICO] Encontradas {len(sin_canciones)} emisoras sin canciones\n")
    
    # Analizar cada una
    for idx, emisora in enumerate(sin_canciones, 1):
        print(f"\n{idx:2d}. {emisora.nombre}")
        print(f"    ID: {emisora.id}")
        print(f"    URL: {emisora.url_stream[:100]}")
        print(f"    Última actualización: {emisora.ultima_actualizacion}")
        print(f"    Última canción: {emisora.ultima_cancion or 'NINGUNA'}")
        
        # Test 1: ¿La URL responde?
        print(f"    [TEST] Conectando a URL...")
        try:
            resp = requests.head(
                emisora.url_stream,
                timeout=5,
                allow_redirects=True,
                verify=False,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            print(f"      [OK] Status HTTP: {resp.status_code}")
            
            # Verificar ICY headers
            has_icy = any('icy' in k.lower() for k in resp.headers.keys())
            print(f"      [INFO] Headers ICY presentes: {'SI' if has_icy else 'NO'}")
            
            if has_icy:
                icy_headers = {k: v for k, v in resp.headers.items() if 'icy' in k.lower()}
                for k, v in icy_headers.items():
                    print(f"        - {k}: {v}")
            
        except requests.exceptions.Timeout:
            print(f"      [FAIL] Timeout (>5s) - URL LENTA O INACCESSIBLE")
        except requests.exceptions.ConnectionError as ce:
            print(f"      [FAIL] Connection Error - SERVIDOR CAÍDO")
        except Exception as ex:
            print(f"      [FAIL] {type(ex).__name__}: {ex}")
        
        # Test 2: ¿Tipo de plataforma?
        url_lower = emisora.url_stream.lower()
        if 'zeno.fm' in url_lower:
            print(f"      [PLATFORM] Zeno.FM - requiere headers especiales")
        elif 'radio.net' in url_lower:
            print(f"      [PLATFORM] Radio.net - requiere extracción de stream")
        elif 'tunein.com' in url_lower:
            print(f"      [PLATFORM] TuneIn - redirect a stream real")
        elif '.mp3' in url_lower or '.nsv' in url_lower:
            print(f"      [PLATFORM] Direct stream - debería funcionar")
        else:
            print(f"      [PLATFORM] Desconocida")
    
    # Resumen y recomendaciones
    print("\n" + "="*120)
    print("RESUMEN Y RECOMENDACIONES")
    print("="*120 + "\n")
    
    # Categorizar por problema
    print("[ANÁLISIS] Problemas más probables:\n")
    
    timeout_count = 0
    connection_count = 0
    icy_missing = 0
    
    for emisora in sin_canciones:
        try:
            resp = requests.head(
                emisora.url_stream,
                timeout=5,
                allow_redirects=True,
                verify=False
            )
            if resp.status_code == 200:
                has_icy = any('icy' in k.lower() for k in resp.headers.keys())
                if not has_icy:
                    icy_missing += 1
        except requests.exceptions.Timeout:
            timeout_count += 1
        except requests.exceptions.ConnectionError:
            connection_count += 1
    
    print(f"1. URLs inaccessibles (timeout):     {timeout_count} emisoras")
    print(f"2. URLs con error de conexión:        {connection_count} emisoras")
    print(f"3. URLs OK pero sin ICY metadata:     {icy_missing} emisoras")
    print(f"\nTotal explicado:                     {timeout_count + connection_count + icy_missing}")
    print(f"Faltantes por investigar:             {len(sin_canciones) - (timeout_count + connection_count + icy_missing)}")
    
    print("\n[RECOMENDACIONES]\n")
    
    if timeout_count > 0:
        print(f"1. {timeout_count} emisoras con timeout:")
        print(f"   - Aumentar ICY_TIMEOUT en stream_reader.py")
        print(f"   - O: Buscar URLs alternativas (TuneIn, RadioJar)")
        print(f"   - O: Estas emisoras están offline o son proxy/redirects\n")
    
    if connection_count > 0:
        print(f"2. {connection_count} emisoras con error de conexión:")
        print(f"   - URLs completamente inválidas")
        print(f"   - Servidores caídos permanentemente")
        print(f"   - Recomendación: Eliminar o reemplazar URL\n")
    
    if icy_missing > 0:
        print(f"3. {icy_missing} emisoras sin ICY metadata:")
        print(f"   - Streams sin metadata (DJ sin anunciar canciones)")
        print(f"   - AudD debería detectar... pero no funcionó")
        print(f"   - Posible: AudD quota excedida o audio demasiado silencioso")
        print(f"   - Recomendación: Esperar 24h + reintentar, o contactar DJ\n")
    
    print("="*120 + "\n")

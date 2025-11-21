#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEST ESPECÍFICO DE LAS 8 EMISORAS SIN CANCIONES
Para identificar por qué fallan y encontrar soluciones
"""
import os
import sys

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

sys.path.insert(0, '/c/Users/57321/OneDrive/Escritorio/radio_monitor-main/radio_monitor-main')

from app import app, db
from models.emisoras import Emisora, Cancion
from utils import stream_reader
import requests

print("\n" + "="*120)
print("[TEST] INVESTIGACIÓN DETALLADA DE LAS 8 EMISORAS SIN CANCIONES")
print("="*120 + "\n")

problematic_names = [
    "La Excitante",
    "Radio Amboy",
    "Cañar Stereo 97.3 FM",
    "La Mega Star 95.1 FM",
    "La Kalle Sajoma 96.3 FM SJM",
    "La Kalle de Santiago 96.3 Fm",
    "La Kalle San Cristobal 96.3 Fm",
    "Radio CTC Monción 89.5 FM",
]

with app.app_context():
    for idx, nombre in enumerate(problematic_names, 1):
        print(f"\n[{idx}/8] Investigando: {nombre}")
        print("-"*120)
        
        station = db.session.query(Emisora).filter(Emisora.nombre.ilike(f"%{nombre}%")).first()
        
        if not station:
            print(f"  [ERROR] Emisora NO encontrada en BD")
            continue
        
        print(f"  ID: {station.id}")
        url = station.url_stream or station.url
        print(f"  URL: {url}")
        
        if not url:
            print(f"  [SKIP] SIN URL")
            continue
        
        # Test 1: Conectar a URL
        print(f"\n  [STEP 1] Conectar a URL...")
        try:
            resp = requests.head(url, timeout=10, verify=False, allow_redirects=True)
            print(f"    Status: {resp.status_code}")
            print(f"    Headers claves:")
            for k in ['Content-Type', 'icy-name', 'icy-metaint', 'icy-br']:
                if k.lower() in {h.lower(): h for h in resp.headers.keys()}:
                    actual_key = {h.lower(): h for h in resp.headers.keys()}[k.lower()]
                    print(f"      {k}: {resp.headers.get(actual_key, 'N/A')}")
        except Exception as e:
            print(f"    [FAIL] {e}")
            continue
        
        # Test 2: Obtener stream real
        print(f"\n  [STEP 2] Obtener stream real...")
        try:
            real_url = stream_reader.get_real_stream_url(url)
            print(f"    URL Real: {real_url[:100]}...")
        except Exception as e:
            print(f"    [FAIL] {e}")
            real_url = url
        
        # Test 3: ICY Metadata
        print(f"\n  [STEP 3] Intentar obtener ICY metadata...")
        try:
            title = stream_reader.get_icy_metadata(real_url, timeout=15)
            if title:
                print(f"    Título: {title[:100]}")
                print(f"    ¿Válido?: {stream_reader.is_valid_metadata(title)}")
            else:
                print(f"    [FAIL] No se obtuvo metadata ICY")
        except Exception as e:
            print(f"    [FAIL] {e}")
        
        # Test 4: ffmpeg + audio fingerprint
        print(f"\n  [STEP 4] Intentar audio fingerprinting (AudD)...")
        try:
            audd_token = app.config.get('AUDD_API_TOKEN', '')
            if not audd_token:
                print(f"    [SKIP] AudD token no configurado")
            else:
                result = stream_reader.capture_and_recognize_audd(real_url, audd_token)
                if result:
                    print(f"    Artist: {result.get('artist')}")
                    print(f"    Title: {result.get('title')}")
                else:
                    print(f"    [FAIL] AudD no pudo identificar")
        except Exception as e:
            print(f"    [FAIL] {e}")

print("\n" + "="*120)
print("[FIN DEL TEST]")
print("="*120 + "\n")

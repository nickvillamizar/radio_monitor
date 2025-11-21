#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

sys.path.insert(0, '/c/Users/57321/OneDrive/Escritorio/radio_monitor-main/radio_monitor-main')

from flask import Flask
from utils import stream_reader
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Create app context
app = Flask(__name__)
app.config['AUDD_API_TOKEN'] = ''  # Se cargará de env
app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL')

print("\n" + "="*100)
print("[TEST] PRUEBA DE DETECCIÓN - LA EXCITANTE")
print("="*100 + "\n")

# Test URL
url = "https://sonicpanel.zonaradio.net/8280/stream.nsv;stream.mp3"
print(f"[1] Probando URL: {url}")
print(f"[2] Limpiando URL...")

real_url = stream_reader.get_real_stream_url(url)
print(f"[3] URL real: {real_url}\n")

print(f"[4] Obteniendo metadata ICY...")
title = stream_reader.get_icy_metadata(real_url, timeout=15)

if title:
    print(f"[5] Título obtenido: {title}")
    print(f"[6] Validando...")
    is_valid = stream_reader.is_valid_metadata(title)
    print(f"    ¿Válido?: {is_valid}")
    
    if is_valid:
        artist, song = stream_reader.parse_title_artist(title)
        print(f"[7] Artista: {artist}")
        print(f"    Canción: {song}")
        print(f"\n[SUCCESS] DETECCIÓN EXITOSA!")
    else:
        print(f"[FAIL] Título rechazado por validación")
else:
    print(f"[FAIL] No se obtuvo metadata ICY")

print("\n" + "="*100)
print("[TEST] FIN")
print("="*100 + "\n")

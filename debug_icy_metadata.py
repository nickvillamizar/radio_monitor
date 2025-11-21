#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import time
import os

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

print("\n" + "="*100)
print("[DEBUG] ANÁLISIS DETALLADO DE LECTURA ICY")
print("="*100 + "\n")

# URL que sabemos que funciona (La Excitante)
url = "https://sonicpanel.zonaradio.net/8280/stream.nsv;stream.mp3"

print(f"[TEST] URL: {url}\n")

# Test 1: GET sin ICY-Metadata
print("[1] Intentando GET SIN Icy-MetaData header...")
headers = {"User-Agent": "Mozilla/5.0"}
try:
    resp = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
    print(f"    Status: {resp.status_code}")
    print(f"    Headers recibidos:")
    for k, v in resp.headers.items():
        if 'icy' in k.lower() or 'metaint' in k.lower() or 'title' in k.lower():
            print(f"      {k}: {v}")
    
    # Leer primeros 5000 bytes del stream
    raw_data = resp.raw.read(5000)
    print(f"    Primeros 5000 bytes del stream: {raw_data[:500]}")
    print(f"    Tamaño total leído: {len(raw_data)} bytes")
    resp.close()
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "-"*100 + "\n")

# Test 2: GET CON Icy-MetaData header
print("[2] Intentando GET CON Icy-MetaData: 1 header...")
headers = {"Icy-MetaData": "1", "User-Agent": "Mozilla/5.0"}
try:
    resp = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
    print(f"    Status: {resp.status_code}")
    print(f"    Headers recibidos:")
    
    metaint = None
    for k, v in resp.headers.items():
        if 'icy' in k.lower() or 'metaint' in k.lower() or 'title' in k.lower():
            print(f"      {k}: {v}")
            if 'metaint' in k.lower():
                metaint = int(v)
    
    if metaint:
        print(f"\n    [INFO] metaint = {metaint}")
        print(f"    Leyendo {metaint} bytes de datos de audio...")
        
        raw = resp.raw
        
        # Leer block de audio
        data_block = raw.read(metaint)
        print(f"    Datos de audio: {len(data_block)} bytes")
        
        # Leer byte de longitud de metadata
        meta_len_byte = raw.read(1)
        if meta_len_byte:
            meta_len = meta_len_byte[0] * 16
            print(f"    Byte de longitud: 0x{meta_len_byte[0]:02x} = {meta_len_byte[0]} -> {meta_len} bytes de metadata")
            
            if meta_len > 0:
                # Leer metadata
                meta = raw.read(meta_len)
                print(f"    Metadata raw ({len(meta)} bytes):")
                print(f"      {meta}")
                print(f"    Metadata decodificada:")
                print(f"      {meta.decode('utf-8', errors='ignore')}")
                
                # Buscar StreamTitle
                if b"StreamTitle=" in meta:
                    title_part = meta.split(b"StreamTitle=", 1)[1]
                    print(f"\n    [FOUND] StreamTitle! Extrayendo...")
                    print(f"      Raw: {title_part[:200]}")
                    
                    # Buscar comillas
                    if b"'" in title_part:
                        title = title_part.split(b"'")[1]
                        print(f"      Contenido entre comillas: {title}")
                        print(f"      Decodificado: {title.decode('utf-8', errors='ignore')}")
            else:
                print(f"    No hay metadata en este punto (meta_len=0)")
        else:
            print(f"    ERROR: No se pudo leer byte de longitud")
    else:
        print(f"    [WARN] No se recibió metaint header - stream sin metadata ICY")
    
    resp.close()
except Exception as e:
    print(f"    ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "-"*100 + "\n")

# Test 3: Usando ffprobe para ver metadata
print("[3] Usando ffprobe para ver metadata disponible...")
import subprocess
try:
    cmd = ["ffprobe", "-v", "debug", "-show_format", url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    print("    ffprobe output:")
    lines = result.stderr.split('\n')
    for line in lines:
        if 'icy' in line.lower() or 'metadata' in line.lower() or 'title' in line.lower():
            print(f"      {line}")
except FileNotFoundError:
    print("    ffprobe no disponible")
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "="*100)
print("[DEBUG] FIN DEL ANÁLISIS")
print("="*100 + "\n")

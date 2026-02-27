#!/usr/bin/env python3
"""Test del extractor mejorado con ID 11"""

import sys
sys.path.insert(0, '.')
from app import app
from models.emisoras import Emisora
from utils.stream_reader import get_real_stream_url, extract_generic_stream, get_icy_metadata
import requests

with app.app_context():
    e = Emisora.query.get(11)
    if not e:
        print("❌ ID 11 no existe")
        sys.exit(1)
    
    url = e.url_stream or e.url
    
    print("\n" + "="*80)
    print(f"[TEST EXTRACTOR MEJORADO] Emisora ID 11: {e.nombre}")
    print("="*80 + "\n")
    
    print(f"URL original: {url}\n")
    
    print("[PASO 1] Intentar extractor genérico directamente")
    print("-"*80)
    generic = extract_generic_stream(url)
    if generic:
        print(f"✅ ENCONTRADO: {generic}\n")
    else:
        print("❌ No encontrado con extractor genérico\n")
    
    print("[PASO 2] Usar get_real_stream_url()")
    print("-"*80)
    resolved = get_real_stream_url(url)
    print(f"URL resuelta: {resolved}\n")
    
    print("[PASO 3] Intentar ICY metadata en URL resuelta")
    print("-"*80)
    icy = get_icy_metadata(resolved, timeout=8)
    if icy:
        print(f"✅ ICY METADATA: {icy}\n")
    else:
        print("⚠️  Sin ICY metadata\n")
    
    print("[PASO 4] Validación HEAD")
    print("-"*80)
    try:
        r = requests.head(resolved, timeout=6, allow_redirects=True)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}\n")
    except Exception as ex:
        print(f"Error: {ex}\n")
    
    print("="*80)
    print("[RESUMEN]")
    print(f"  Original: {url}")
    print(f"  Resuelto: {resolved}")
    if icy:
        print(f"  Metadata: ✅ {icy}")
    else:
        print(f"  Metadata: ❌ No disponible")
    print("="*80 + "\n")

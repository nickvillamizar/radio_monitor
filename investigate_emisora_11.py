#!/usr/bin/env python3
"""Investigar por qué emisora ID 11 no detecta"""

import sys
sys.path.insert(0, '.')
from app import app
from models.emisoras import Emisora, Cancion
from utils.stream_reader import get_real_stream_url, get_icy_metadata
import requests

with app.app_context():
    # Buscar emisora ID 11
    e = Emisora.query.get(11)
    if not e:
        print("❌ ID 11 no existe")
        sys.exit(1)
    
    print("\n" + "="*80)
    print(f"[INVESTIGACIÓN] Emisora ID 11")
    print("="*80 + "\n")
    
    print(f"Nombre: {e.nombre}")
    print(f"URL configurada: {e.url_stream or e.url}")
    print(f"País: {e.pais}")
    print(f"Sitio web: {getattr(e, 'sitio_web', 'N/A')}")
    print(f"Plays registrados: {Cancion.query.filter_by(emisora_id=11).count()}")
    
    url = e.url_stream or e.url
    if not url:
        print("\n❌ SIN URL CONFIGURADA")
        sys.exit(1)
    
    print(f"\n[PASO 1] Resolver URL")
    print("-"*80)
    print(f"URL original: {url}")
    
    try:
        real_url = get_real_stream_url(url)
        print(f"URL resuelta: {real_url}")
        
        if not real_url:
            print("❌ No se pudo resolver la URL")
            sys.exit(1)
    except Exception as ex:
        print(f"❌ Error resolviendo: {ex}")
        sys.exit(1)
    
    print(f"\n[PASO 2] HEAD request (verificar accesibilidad)")
    print("-"*80)
    
    try:
        r = requests.head(real_url, timeout=6, allow_redirects=True)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type', 'N/A')}")
        print(f"Server: {r.headers.get('server', 'N/A')}")
        
        if r.status_code >= 400:
            print(f"⚠️  Código {r.status_code} - Posible problema con el stream")
    except Exception as ex:
        print(f"❌ Error HEAD: {ex}")
    
    print(f"\n[PASO 3] Obtener ICY metadata")
    print("-"*80)
    
    try:
        icy = get_icy_metadata(real_url, timeout=8)
        if icy:
            print(f"✅ ICY metadata obtenido: {icy}")
        else:
            print("⚠️  No hay ICY metadata disponible")
    except Exception as ex:
        print(f"❌ Error ICY: {ex}")
    
    print(f"\n[PASO 4] Intentar GET request para ver respuesta")
    print("-"*80)
    
    try:
        r = requests.get(real_url, timeout=8, stream=True, allow_redirects=True)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type', 'N/A')}")
        
        # Leer primeros bytes
        chunk = r.raw.read(1024)
        if chunk:
            print(f"Primeros bytes: {chunk[:200]}")
    except Exception as ex:
        print(f"❌ Error GET: {ex}")
    
    print("\n" + "="*80)
    print("[CONCLUSIÓN] El problema de la emisora ID 11 puede ser:")
    print("  1. URL inválida o muerta")
    print("  2. Stream sin ICY metadata")
    print("  3. URL requiere headers específicos")
    print("  4. Stream con DRM o bloqueo")
    print("="*80 + "\n")

import requests
import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora

# URLs problemáticas (emisoras sin canciones)
problematic_urls = [
    ('La Excitante', 'https://sonicpanel.zonaradio.net/8280/stream.nsv;stream.mp3'),
    ('Radio Amboy', 'https://sp.sintonizapp.com:7023/stream'),
    ('Cañar Stereo 97.3 FM', 'https://ecuamedios.net:10937/stream'),
    ('La Mega Star 95.1 FM', 'https://ecuamedios.net:10955/stream;stream.nsv;'),
    ('Expreso 89.1 FM', 'https://streaming.grupomediosdelnorte.com:8008/stream'),
]

print("\n" + "="*100)
print("TEST DE URLS PROBLEMÁTICAS - ANÁLISIS DETALLADO")
print("="*100 + "\n")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

for nombre, url in problematic_urls:
    print(f"\n[{nombre}]")
    print(f"URL: {url}")
    print("-" * 100)
    
    try:
        # Test 1: HEAD request
        print("  1. Probando HEAD request...")
        resp = requests.head(url, timeout=10, headers=headers, verify=False, allow_redirects=True)
        print(f"     [OK] Status: {resp.status_code}")
        print(f"     [OK] Headers: {dict(resp.headers)}")
        
    except requests.exceptions.Timeout:
        print("  [FAIL] TIMEOUT - Servidor no responde en 10 segundos")
    except requests.exceptions.ConnectionError as e:
        print(f"  [FAIL] CONNECTION ERROR - {e}")
    except requests.exceptions.SSLError as e:
        print(f"  [FAIL] SSL ERROR - {e}")
        # Intentar sin SSL
        try:
            print("    Reintentando sin verificacion SSL...")
            resp = requests.head(url.replace('https://', 'http://'), timeout=10, headers=headers, verify=False, allow_redirects=True)
            print(f"    [OK] Status HTTP: {resp.status_code}")
        except Exception as e2:
            print(f"    [FAIL] Tambien falla con HTTP: {e2}")
    except Exception as e:
        print(f"  [FAIL] ERROR: {type(e).__name__} - {e}")
    
    try:
        # Test 2: GET request (pequeño)
        print("  2. Probando GET request (primeros 1KB)...")
        resp = requests.get(url, timeout=5, headers=headers, verify=False, stream=True)
        print(f"     [OK] Status: {resp.status_code}")
        print(f"     [OK] Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        
        # Leer primeros bytes
        chunk = resp.raw.read(1024)
        print(f"     [OK] Primeros bytes: {chunk[:100]}")
        
    except Exception as e:
        print(f"  [FAIL] GET request fallo: {type(e).__name__} - {e}")

print("\n" + "="*100)
print("FIN DEL TEST")
print("="*100 + "\n")

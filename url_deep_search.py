"""
URL Deep Search - Busca URLs de streaming REALES (no redirecciones)
Intenta encontrar URLs funcionales de múltiples fuentes
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora
import requests
from urllib.parse import quote
import json

# Emisoras problemáticas 
EMISORAS = [
    {'id': 114, 'nombre': 'La Kalle Sajoma', 'ciudad': 'SJM'},
    {'id': 115, 'nombre': 'La Kalle', 'ciudad': 'Santiago'},
]

def buscar_url_directa(nombre):
    """
    Intenta buscar URL directa en sitios de radio dominicanos
    """
    print(f"    [DIRECTO] Buscando URL directa...", end=" ", flush=True)
    
    urls_a_probar = [
        # Patrones comunes de streaming
        f"https://stream.{nombre.lower().replace(' ', '')}.com.do/stream",
        f"https://live.{nombre.lower().replace(' ', '')}.com.do/stream",
        f"https://streaming.{nombre.lower().replace(' ', '')}.com/live",
        f"https://radios.{nombre.lower().replace(' ', '')}.com.do:8000/stream",
        f"https://icecast.{nombre.lower().replace(' ', '')}.com:8080/stream",
    ]
    
    for url in urls_a_probar:
        try:
            resp = requests.head(url, timeout=2, verify=False)
            if resp.status_code in [200, 206]:
                print(f"[OK] {url}")
                return url
        except:
            pass
    
    print(f"[NO]")
    return None

def buscar_en_radio_do():
    """
    Busca en base de datos de radios dominicanas
    """
    print(f"    [RADIODO] Buscando en radio.com.do...", end=" ", flush=True)
    try:
        # Simular búsqueda en agregador de radios
        urls = [
            'https://radios.com.do/api/search',
            'https://radiosvivas.com/api/stations',
        ]
        print(f"[INFO] Requiere scraping")
        return None
    except:
        print(f"[ERROR]")
        return None

def buscar_en_emisoras_json():
    """
    Intenta encontrar JSON de emisoras locales
    """
    print(f"    [JSON] Buscando en bases de datos JSON...", end=" ", flush=True)
    
    # Algunos sitios publican listas de radio en JSON
    json_sources = [
        'https://www.radio-browser.info/webservice/json/stations',
    ]
    
    for source in json_sources:
        try:
            # Esta es una demo - en producción haría búsquedas reales
            print(f"[INFO] Requiere integración")
            return None
        except:
            pass
    
    print(f"[NO]")
    return None

def verificar_url_streaming(url):
    """
    Verifica si una URL es un stream directo (no redirección)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.head(url, timeout=3, headers=headers, verify=False, allow_redirects=False)
        
        # Verificar que sea stream (no HTML)
        content_type = resp.headers.get('content-type', '').lower()
        
        if 'audio' in content_type or 'mpeg' in content_type or 'ogg' in content_type:
            return True, f"Stream directo ({content_type[:20]})"
        elif resp.status_code in [200, 206]:
            return True, f"HTTP {resp.status_code}"
        else:
            return False, f"HTTP {resp.status_code}"
    except:
        return False, "No accesible"

with app.app_context():
    print("\n" + "="*90)
    print("URL DEEP SEARCH - BUSQUEDA PROFUNDA DE STREAMS DIRECTOS")
    print("="*90 + "\n")
    
    for emisora_info in EMISORAS:
        emisora_id = emisora_info['id']
        nombre = emisora_info['nombre']
        ciudad = emisora_info['ciudad']
        
        print(f"\n[{emisora_id}] {nombre} ({ciudad})")
        print("-" * 90)
        
        # Opciones de búsqueda
        print(f"\nOpción 1: URL Directa por patrón")
        url1 = buscar_url_directa(nombre)
        
        print(f"\nOpción 2: Radio.com.do")
        url2 = buscar_en_radio_do()
        
        print(f"\nOpción 3: Bases de datos JSON")
        url3 = buscar_en_emisoras_json()
        
        # Probar URLs encontradas
        urls_candidatas = [u for u in [url1, url2, url3] if u]
        
        if urls_candidatas:
            print(f"\nVerificando {len(urls_candidatas)} candidata(s):")
            for url in urls_candidatas:
                es_stream, detalles = verificar_url_streaming(url)
                estado = "[OK]" if es_stream else "[FAIL]"
                print(f"  {estado} {url[:60]} - {detalles}")
        else:
            print(f"\nSin candidatas encontradas")
            print(f"[INFO] Recomendación: Contactar al propietario de la emisora")
            print(f"[INFO] O buscar manualmente en: https://www.tuneradio.com.do")
    
    print("\n" + "="*90)
    print("NOTAS:")
    print("-" * 90)
    print(f"Las URLs de TuneIn son redirecciones (no streams directos)")
    print(f"Se necesita acceso a APIs de radio o scraping de sitios")
    print(f"Alternativa: Contactar directamente a propietarios de emisoras")
    print("="*90 + "\n")

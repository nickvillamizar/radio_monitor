"""
URL Rescuer - Busca URLs alternativas para emisoras de radio
Busca en múltiples fuentes: TuneIn, RadioJar, Radio Garden
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora
import requests
import json
from urllib.parse import quote
import time

# URLs problemáticas que necesitan alternativas
EMISORAS_A_RESCATAR = [
    {'id': 114, 'nombre': 'La Kalle Sajoma 96.3 FM SJM', 'url_actual': 'https://radio.telemicro.com.do/lakallesjm'},
    {'id': 115, 'nombre': 'La Kalle de Santiago 96.3 Fm (SANTIAGO)', 'url_actual': 'https://radio.telemicro.com.do/lakallesantiago'},
]

def buscar_en_tunein(nombre_emisora):
    """
    Busca en TuneIn (aunque limitado sin API key)
    """
    try:
        # TuneIn public search (limitado)
        url = f"https://opml.radiotime.com/Search.ashx?query={quote(nombre_emisora)}&render=json"
        print(f"    [TUNEIN] {nombre_emisora}...", end=" ", flush=True)
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if 'body' in data and data['body']:
                for item in data['body']:
                    if 'URL' in item:
                        print(f"[OK] Encontrada")
                        return item['URL']
        print("[NO]")
        return None
    except Exception as e:
        print(f"[ERROR] {str(e)[:20]}")
        return None

def buscar_en_radiojar(nombre_emisora):
    """
    Busca en RadioJar API (más accesible)
    """
    try:
        print(f"    [RADIOJAR] {nombre_emisora}...", end=" ", flush=True)
        
        # RadioJar search
        url = f"https://www.radiojar.com/api/radio/search?query={quote(nombre_emisora)}&limit=5"
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and data['results']:
                for radio in data['results']:
                    if radio.get('title'):
                        # Obtener stream URL
                        stream_url = radio.get('stream_url') or radio.get('url')
                        if stream_url:
                            print(f"[OK] Encontrada")
                            return stream_url
        print("[NO]")
        return None
    except Exception as e:
        print(f"[ERROR] {str(e)[:20]}")
        return None

def buscar_en_radio_garden(nombre_emisora):
    """
    Busca en Radio Garden (requiere parsing HTML)
    """
    try:
        print(f"    [GARDEN] {nombre_emisora}...", end=" ", flush=True)
        # Radio Garden es más complejo, requeriría Selenium
        print("[WARN] Requiere navegador")
        return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

def buscar_en_dominios_alternativos(nombre_emisora):
    """
    Intenta URLs comunes para radios dominicanas
    """
    print(f"    [DOMINIOS] Alternativas: ", end=" ", flush=True)
    
    # Patrones comunes para radios dominicanas
    patrones = [
        f"https://{nombre_emisora.lower().replace(' ', '')}.stream.com.do/live",
        f"https://{nombre_emisora.lower().replace(' ', '')}.streaming.com.do/stream",
        f"https://radio-{nombre_emisora.lower().replace(' ', '-')}.com.do/live",
        f"https://streaming.{nombre_emisora.lower().replace(' ', '')}.com.do/stream",
    ]
    
    for url in patrones:
        try:
            resp = requests.head(url, timeout=2, verify=False)
            if resp.status_code in [200, 206]:
                print(f"[OK] {url}")
                return url
        except:
            pass
    
    print("[NO]")
    return None

def intentar_url_sin_credenciales(url_original):
    """
    Si la URL tiene credenciales, intenta sin ellas
    """
    print(f"    [ALTBASE] URL sin ruta: ", end=" ", flush=True)
    
    # Tomar solo base
    base = url_original.rsplit('/', 1)[0]
    try:
        resp = requests.head(base, timeout=2, verify=False)
        if resp.status_code in [200, 206, 301, 302]:
            print(f"[OK] {base}")
            return base
    except:
        pass
    
    print("[NO]")
    return None

with app.app_context():
    print("\n" + "="*90)
    print("URL RESCUER - BÚSQUEDA DE ALTERNATIVAS PARA EMISORAS INACCESIBLES")
    print("="*90 + "\n")
    
    for emisora_info in EMISORAS_A_RESCATAR:
        emisora_id = emisora_info['id']
        nombre = emisora_info['nombre']
        url_actual = emisora_info['url_actual']
        
        print(f"\n[{emisora_id}] {nombre}")
        print("-" * 90)
        print(f"URL actual (falla): {url_actual}\n")
        
        print("Buscando alternativas...")
        
        urls_encontradas = []
        
        # 1. TuneIn
        url = buscar_en_tunein(nombre)
        if url:
            urls_encontradas.append(('TuneIn', url))
        time.sleep(0.5)
        
        # 2. RadioJar
        url = buscar_en_radiojar(nombre)
        if url:
            urls_encontradas.append(('RadioJar', url))
        time.sleep(0.5)
        
        # 3. Radio Garden
        url = buscar_en_radio_garden(nombre)
        if url:
            urls_encontradas.append(('Radio Garden', url))
        time.sleep(0.5)
        
        # 4. Dominios alternativos
        url = buscar_en_dominios_alternativos(nombre)
        if url:
            urls_encontradas.append(('Dominios alternativos', url))
        time.sleep(0.5)
        
        # 5. URL sin ruta
        url = intentar_url_sin_credenciales(url_actual)
        if url:
            urls_encontradas.append(('URL sin ruta', url))
        
        # RESULTADOS
        print(f"\nResultados:")
        if urls_encontradas:
            print(f"  [OK] Encontradas {len(urls_encontradas)} alternativa(s):")
            for source, url in urls_encontradas:
                print(f"    [{source}] {url}")
            
            # Verificar cada una
            print(f"\n  Validando alternativas:")
            mejor_url = None
            for source, url in urls_encontradas:
                try:
                    resp = requests.head(url, timeout=3, verify=False)
                    if resp.status_code in [200, 206]:
                        print(f"    [OK] {source} - HTTP {resp.status_code}")
                        if not mejor_url:
                            mejor_url = url
                    else:
                        print(f"    [FAIL] {source} - HTTP {resp.status_code}")
                except:
                    print(f"    [FAIL] {source} - No responde")
            
            if mejor_url:
                print(f"\n  MEJOR ALTERNATIVA: {mejor_url}")
                print(f"  [INFO] Actualizar en BD? (Decision manual)")
        else:
            print(f"  [FAIL] No se encontraron alternativas")
            print(f"  [INFO] La emisora puede estar completamente fuera de servicio")
            print(f"  [INFO] O usar un nombre diferente en las bases de datos de streaming")
    
    print("\n" + "="*90)
    print("BÚSQUEDA COMPLETADA")
    print("="*90 + "\n")

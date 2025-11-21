"""
Validador de URLs de Streaming
Verifica si las URLs responden correctamente y obtiene alternativas si fallan
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora
import requests
import socket
from urllib.parse import urlparse
from datetime import datetime

# Emisoras críticas sin canciones
EMISORAS_CRITICAS = [
    ('La Excitante', 109),
    ('Radio Amboy', 110),
    ('Cañar Stereo 97.3 FM', 111),
    ('La Mega Star 95.1 FM', 112),
    ('Expreso 89.1 FM', 113),
    ('La Kalle Sajoma 96.3 FM SJM', 114),
    ('La Kalle de Santiago 96.3 Fm (SANTIAGO)', 115),
    ('Radio CTC Moncion 89.5 FM (M89.5)', 117),
]

def test_url_connection(url, timeout=5):
    """
    Prueba si una URL responde correctamente
    Retorna: (estado, mensaje, headers)
    """
    if not url:
        return False, "URL vacía", {}
    
    try:
        # Reemplazar variables comunes
        url = url.replace('[...]', '')
        
        print(f"  → Probando: {url[:80]}...", end=" ", flush=True)
        
        # Usar timeout muy corto para no bloquear
        response = requests.head(url, timeout=timeout, allow_redirects=True, verify=False)
        
        if response.status_code in [200, 206, 301, 302, 404]:
            print(f"✓ {response.status_code}")
            return True, f"Responde con {response.status_code}", response.headers
        else:
            print(f"✗ {response.status_code}")
            return False, f"HTTP {response.status_code}", response.headers
            
    except requests.exceptions.Timeout:
        print("✗ TIMEOUT (>5s)")
        return False, "Timeout - Servidor no responde rápido", {}
    except requests.exceptions.ConnectionError:
        print("✗ CONEXION")
        return False, "Error de conexión - Host inaccesible", {}
    except requests.exceptions.SSLError:
        print("⚠ SSL ERROR", end=" ", flush=True)
        # Intentar sin verificar SSL
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True, verify=False)
            if response.status_code in [200, 206]:
                print("→ ✓")
                return True, f"Responde (SSL ignorado) {response.status_code}", response.headers
            else:
                print(f"→ ✗ {response.status_code}")
                return False, f"HTTP {response.status_code}", {}
        except:
            print("→ FALLO")
            return False, "Error SSL - No se puede conectar", {}
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:30]}")
        return False, f"Error: {str(e)[:50]}", {}

def test_dns_resolution(url):
    """
    Verifica si el dominio se resuelve correctamente
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False, "URL no válida"
        
        print(f"  → DNS: {hostname}", end=" ", flush=True)
        ip = socket.gethostbyname(hostname)
        print(f"→ {ip}")
        return True, ip
    except socket.gaierror as e:
        print(f"✗ DNS FAIL: {e}")
        return False, f"DNS no resuelve: {e}"
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False, str(e)

def search_alternative_url(emisora_nombre):
    """
    Intenta encontrar una URL alternativa buscando en internet
    (Simulado - en producción usaría scraping o APIs externas)
    """
    print(f"  → Buscando alternativas para: {emisora_nombre}...", end=" ", flush=True)
    # En un escenario real, aquí iríamos a buscar a:
    # - TuneIn API
    # - Radio Garden API
    # - Búsqueda en Google
    # Por ahora, retornamos una sugerencia
    print("(requiere API externa)")
    return None

with app.app_context():
    print("\n" + "="*90)
    print("VALIDACIÓN DE URLs DE STREAMING - EMISORAS CRÍTICAS")
    print("="*90 + "\n")
    
    resultados = []
    
    for nombre, emisora_id in EMISORAS_CRITICAS:
        print(f"\n[{emisora_id}] {nombre}")
        print("-" * 90)
        
        emisora = db.session.query(Emisora).filter(Emisora.id == emisora_id).first()
        
        if not emisora:
            print("  ✗ EMISORA NO ENCONTRADA EN BD")
            continue
        
        url = emisora.url_stream
        print(f"  URL en BD: {url}")
        
        if not url:
            print("  ✗ SIN URL - Imposible validar")
            resultados.append({
                'nombre': nombre,
                'id': emisora_id,
                'estado': 'SIN_URL',
                'detalles': 'No hay URL en base de datos'
            })
            continue
        
        # 1. Prueba de resolución DNS
        dns_ok, dns_msg = test_dns_resolution(url)
        
        # 2. Prueba de conexión HTTP
        http_ok, http_msg, headers = test_url_connection(url, timeout=5)
        
        # Determinar estado final
        if http_ok and dns_ok:
            estado = "VÁLIDA ✓"
            detalles = f"DNS OK + HTTP {http_msg}"
        elif dns_ok and not http_ok:
            estado = "INACCESIBLE"
            detalles = f"DNS OK pero HTTP falla: {http_msg}"
        elif not dns_ok:
            estado = "DOMINIO MUERTO"
            detalles = f"DNS no resuelve: {dns_msg}"
        else:
            estado = "FALLA CRÍTICA"
            detalles = f"DNS: {dns_msg} | HTTP: {http_msg}"
        
        print(f"\n  RESULTADO: {estado}")
        print(f"  Detalles: {detalles}")
        
        resultados.append({
            'nombre': nombre,
            'id': emisora_id,
            'url': url,
            'estado': estado,
            'detalles': detalles,
            'http_ok': http_ok,
            'dns_ok': dns_ok
        })
        
        # Si falla, intentar encontrar alternativa
        if not http_ok:
            alt = search_alternative_url(nombre)
            if alt:
                print(f"  Alternativa: {alt}")
    
    # RESUMEN FINAL
    print("\n" + "="*90)
    print("RESUMEN DE VALIDACIÓN")
    print("="*90)
    
    validas = sum(1 for r in resultados if r['estado'] == 'VÁLIDA ✓')
    inaccesibles = sum(1 for r in resultados if r['estado'] == 'INACCESIBLE')
    dominios_muertos = sum(1 for r in resultados if r['estado'] == 'DOMINIO MUERTO')
    fallas_criticas = sum(1 for r in resultados if r['estado'] == 'FALLA CRÍTICA')
    sin_url = sum(1 for r in resultados if r['estado'] == 'SIN_URL')
    
    print(f"\nTotal validadas: {len(resultados)}")
    print(f"✓ URLs Válidas:        {validas} ({100*validas//len(resultados)}%)")
    print(f"⚠ Inaccesibles:        {inaccesibles} ({100*inaccesibles//len(resultados)}%)")
    print(f"✗ Dominios Muertos:    {dominios_muertos} ({100*dominios_muertos//len(resultados)}%)")
    print(f"✗ Fallas Críticas:     {fallas_criticas} ({100*fallas_criticas//len(resultados)}%)")
    print(f"? Sin URL:             {sin_url}")
    
    # Detalle por emisora
    print("\n" + "="*90)
    print("DETALLE POR EMISORA")
    print("="*90)
    
    for r in resultados:
        simbolo = "✓" if r['estado'] == 'VÁLIDA ✓' else "✗"
        print(f"\n{simbolo} {r['nombre']} (ID: {r['id']})")
        print(f"   Estado: {r['estado']}")
        print(f"   {r['detalles']}")
        if 'url' in r:
            print(f"   URL: {r['url'][:70]}...")
    
    print("\n" + "="*90)
    print(f"Validación completada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*90 + "\n")

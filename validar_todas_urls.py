"""
Validador completo de URLs para TODAS las 71 emisoras
Identifica URLs problemáticas y busca alternativas
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora
import requests
from datetime import datetime
import json

def test_url_rapido(url, timeout=3):
    """
    Prueba rápida de URL (3 segundos max)
    Retorna: (estado, codigo_http)
    """
    if not url:
        return 'SIN_URL', 0
    
    try:
        # HEAD request para no descargar toda la respuesta
        resp = requests.head(url, timeout=timeout, allow_redirects=True, verify=False)
        
        if resp.status_code in [200, 206]:
            return 'OK', resp.status_code
        elif resp.status_code in [301, 302, 307, 308]:
            return 'REDIRECT', resp.status_code
        elif resp.status_code == 400:
            return 'BAD_REQUEST', 400
        elif resp.status_code == 403:
            return 'FORBIDDEN', 403
        elif resp.status_code == 404:
            return 'NOT_FOUND', 404
        elif resp.status_code == 500:
            return 'SERVER_ERROR', 500
        else:
            return 'HTTP_ERROR', resp.status_code
    except requests.exceptions.Timeout:
        return 'TIMEOUT', 0
    except requests.exceptions.ConnectionError:
        return 'CONEXION_ERROR', 0
    except requests.exceptions.SSLError:
        # Intentar sin SSL
        try:
            resp = requests.head(url, timeout=timeout, verify=False, allow_redirects=True)
            if resp.status_code in [200, 206]:
                return 'OK_NO_SSL', resp.status_code
            else:
                return 'SSL_ERROR', 0
        except:
            return 'SSL_ERROR', 0
    except Exception as e:
        return 'ERROR', 0

with app.app_context():
    print("\n" + "="*100)
    print("VALIDACION COMPLETA DE URLs - TODAS LAS 71 EMISORAS")
    print("="*100 + "\n")
    
    emisoras = db.session.query(Emisora).order_by(Emisora.id).all()
    
    resultados = {
        'OK': [],
        'OK_NO_SSL': [],
        'REDIRECT': [],
        'TIMEOUT': [],
        'CONEXION_ERROR': [],
        'BAD_REQUEST': [],
        'FORBIDDEN': [],
        'NOT_FOUND': [],
        'SERVER_ERROR': [],
        'HTTP_ERROR': [],
        'ERROR': [],
        'SIN_URL': [],
    }
    
    print(f"Validando {len(emisoras)} emisoras...")
    print("-" * 100)
    
    for idx, emisora in enumerate(emisoras, 1):
        url = emisora.url_stream
        estado, codigo = test_url_rapido(url)
        
        resultados[estado].append({
            'id': emisora.id,
            'nombre': emisora.nombre,
            'url': url,
            'codigo': codigo
        })
        
        # Mostrar cada 10
        if idx % 10 == 0:
            print(f"  [{idx:2d}/71] Procesadas...", end="\r", flush=True)
    
    print(f"  [71/71] Validacion completada" + " " * 30)
    
    # RESUMEN
    print("\n" + "="*100)
    print("RESUMEN DE VALIDACION")
    print("="*100 + "\n")
    
    total_ok = len(resultados['OK']) + len(resultados['OK_NO_SSL'])
    total_problemas = sum(len(v) for k, v in resultados.items() if k not in ['OK', 'OK_NO_SSL'])
    
    print(f"Total emisoras:      {len(emisoras)}")
    print(f"URLs funcionales:    {total_ok} ({100*total_ok//len(emisoras)}%)")
    print(f"URLs problemáticas:  {total_problemas} ({100*total_problemas//len(emisoras)}%)\n")
    
    # Detalle de problemas
    if len(resultados['TIMEOUT']) > 0:
        print(f"[TIMEOUT] {len(resultados['TIMEOUT'])} emisoras tardan más de 3s")
    if len(resultados['CONEXION_ERROR']) > 0:
        print(f"[CONEXION_ERROR] {len(resultados['CONEXION_ERROR'])} URLs completamente inaccesibles")
    if len(resultados['BAD_REQUEST']) > 0:
        print(f"[BAD_REQUEST] {len(resultados['BAD_REQUEST'])} URLs devuelven HTTP 400")
    if len(resultados['NOT_FOUND']) > 0:
        print(f"[NOT_FOUND] {len(resultados['NOT_FOUND'])} URLs devuelven HTTP 404")
    if len(resultados['SSL_ERROR']) > 0:
        print(f"[SSL_ERROR] {len(resultados['SSL_ERROR'])} errores de certificado SSL")
    if len(resultados['SIN_URL']) > 0:
        print(f"[SIN_URL] {len(resultados['SIN_URL'])} emisoras sin URL en BD")
    
    # URLs con problemas
    print("\n" + "="*100)
    print("EMISORAS CON URLs PROBLEMATICAS")
    print("="*100 + "\n")
    
    problematicas = []
    for estado, items in resultados.items():
        if estado not in ['OK', 'OK_NO_SSL'] and items:
            for item in items:
                problematicas.append({
                    'id': item['id'],
                    'nombre': item['nombre'],
                    'url': item['url'],
                    'estado': estado,
                    'codigo': item['codigo']
                })
    
    if problematicas:
        for item in sorted(problematicas, key=lambda x: x['id']):
            print(f"[{item['id']:3d}] {item['nombre']:40s}")
            print(f"     Estado: {item['estado']:20s} ({item['codigo']})")
            if item['url']:
                print(f"     URL: {item['url'][:80]}")
            print()
    else:
        print("[OK] Todas las URLs funcionan correctamente")
    
    # Guardar reporte
    reporte = {
        'timestamp': datetime.now().isoformat(),
        'total_emisoras': len(emisoras),
        'urls_ok': total_ok,
        'urls_problematicas': total_problemas,
        'detalle': resultados
    }
    
    with open('url_validation_report.json', 'w') as f:
        json.dump(reporte, f, indent=2, default=str)
    
    print("\n[SAVED] Reporte guardado en 'url_validation_report.json'")
    print("="*100 + "\n")

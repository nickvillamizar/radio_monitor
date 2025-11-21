import os
import sys
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from datetime import datetime, timedelta
from app import app, db
from models.emisoras import Emisora
import requests

with app.app_context():
    # Buscar emisoras que no han actualizado en más de 7 días
    threshold = datetime.now() - timedelta(days=7)
    old_emisoras = Emisora.query.filter(
        (Emisora.ultima_actualizacion < threshold) | 
        (Emisora.ultima_actualizacion == None)
    ).order_by(Emisora.ultima_actualizacion).all()
    
    print(f"\n[DIAGNOSTICO] Emisoras sin actualizar en 7+ días: {len(old_emisoras)}\n")
    
    for idx, e in enumerate(old_emisoras[:10], 1):  # Primeras 10
        print(f"\n{idx}. {e.nombre}")
        print(f"   ID: {e.id}")
        print(f"   URL: {e.url_stream[:80]}...")
        print(f"   Última actualización: {e.ultima_actualizacion}")
        print(f"   Última canción: {e.ultima_cancion}")
        
        # Intentar conectar a la URL
        try:
            print(f"   [TEST] Conectando a URL...")
            response = requests.head(e.url_stream, timeout=5, allow_redirects=True)
            print(f"   [OK] Status: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"   [ERROR] Timeout (15s+)")
        except requests.exceptions.ConnectionError:
            print(f"   [ERROR] No se pudo conectar (URL inválida o servidor caído)")
        except Exception as ex:
            print(f"   [ERROR] {type(ex).__name__}: {ex}")

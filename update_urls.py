"""
Actualizar URLs de streaming en la base de datos
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora

# URLs nuevas encontradas por el rescuer
NUEVAS_URLS = [
    {
        'id': 114,
        'nombre': 'La Kalle Sajoma 96.3 FM SJM',
        'url_vieja': 'https://radio.telemicro.com.do/lakallesjm',
        'url_nueva': 'http://opml.radiotime.com/Tune.ashx?c=pbrowse&id=p1879732'
    },
    {
        'id': 115,
        'nombre': 'La Kalle de Santiago 96.3 Fm (SANTIAGO)',
        'url_vieja': 'https://radio.telemicro.com.do/lakallesantiago',
        'url_nueva': 'http://opml.radiotime.com/Tune.ashx?id=s298509'
    }
]

with app.app_context():
    print("\n" + "="*90)
    print("ACTUALIZAR URLs DE STREAMING EN BASE DE DATOS")
    print("="*90 + "\n")
    
    for update in NUEVAS_URLS:
        emisora_id = update['id']
        nombre = update['nombre']
        url_vieja = update['url_vieja']
        url_nueva = update['url_nueva']
        
        print(f"\n[{emisora_id}] {nombre}")
        print("-" * 90)
        
        # Buscar emisora en BD
        emisora = db.session.query(Emisora).filter(Emisora.id == emisora_id).first()
        
        if not emisora:
            print(f"  [ERROR] Emisora NO encontrada en BD")
            continue
        
        print(f"  URL vieja: {url_vieja}")
        print(f"  URL nueva: {url_nueva}")
        
        # Actualizar URL
        emisora.url_stream = url_nueva
        
        # Commit cambios
        try:
            db.session.commit()
            print(f"  [OK] URL actualizada exitosamente en BD")
        except Exception as e:
            db.session.rollback()
            print(f"  [ERROR] No se pudo actualizar: {e}")
    
    print("\n" + "="*90)
    print("ACTUALIZACION COMPLETADA")
    print("="*90)
    
    # Verificar cambios
    print("\nVerificando cambios en BD:\n")
    for update in NUEVAS_URLS:
        emisora = db.session.query(Emisora).filter(Emisora.id == update['id']).first()
        if emisora:
            print(f"[{emisora.id}] {emisora.nombre}")
            print(f"     URL actual en BD: {emisora.url_stream}")
            print()
    
    print("="*90 + "\n")

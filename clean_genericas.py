"""
Limpieza de canciones genéricas/fallback
Elimina canciones que fueron guardadas como "Desconocido" porque la detección falló completamente
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Cancion
from datetime import datetime

# Patrones que indican canciones genéricas/fallback
GENERIC_PATTERNS = [
    ('Artista Desconocido', 'Transmisión en Vivo'),
    ('Desconocido', 'Transmisión en Vivo'),
    ('Unknown', 'Unknown'),
    ('Unknown', 'Stream'),
]

with app.app_context():
    print("\n" + "="*90)
    print("LIMPIEZA DE CANCIONES GENERICAS/FALLBACK")
    print("="*90 + "\n")
    
    total_antes = db.session.query(Cancion).count()
    print(f"Canciones totales ANTES: {total_antes}\n")
    
    # Contar genéricas por patrón
    print("Identificando patrones genericos:")
    print("-" * 90)
    
    total_a_eliminar = 0
    
    for artista_pattern, titulo_pattern in GENERIC_PATTERNS:
        count = db.session.query(Cancion).filter(
            Cancion.artista.ilike(artista_pattern),
            Cancion.titulo.ilike(titulo_pattern)
        ).count()
        
        if count > 0:
            print(f"  [PATTERN] {artista_pattern:30s} - {titulo_pattern:30s} : {count:5d} canciones")
            total_a_eliminar += count
    
    # También contar canciones con 'Desconocido' solamente
    desconocido_count = db.session.query(Cancion).filter(
        Cancion.artista.ilike('%Desconocido%')
    ).count()
    
    print(f"\n  [TOTAL] Canciones con 'Desconocido' en artista: {desconocido_count}")
    
    # CONFIRMAR ELIMINACIÓN
    print("\n" + "-" * 90)
    print(f"\n[INFO] Se encontraron {total_a_eliminar} canciones genericas para eliminar")
    print(f"Esto seria aproximadamente {100*total_a_eliminar//total_antes}% de las canciones\n")
    
    respuesta = input("Escribe SI para confirmar la limpieza: ").strip().upper()
    
    if respuesta != 'SI':
        print("\n[CANCELADO] No se eliminaron canciones")
        print("="*90 + "\n")
    else:
        print("\n[INICIANDO LIMPIEZA]")
        print("-" * 90)
        
        eliminadas = 0
        
        for artista_pattern, titulo_pattern in GENERIC_PATTERNS:
            canciones = db.session.query(Cancion).filter(
                Cancion.artista.ilike(artista_pattern),
                Cancion.titulo.ilike(titulo_pattern)
            ).all()
            
            for cancion in canciones:
                db.session.delete(cancion)
                eliminadas += 1
        
        # Commit
        try:
            db.session.commit()
            print(f"\n[OK] LIMPIEZA COMPLETADA")
            print(f"  Canciones eliminadas: {eliminadas}")
            
            total_despues = db.session.query(Cancion).count()
            print(f"  Canciones totales ANTES: {total_antes}")
            print(f"  Canciones totales DESPUES: {total_despues}")
            print(f"  Diferencia: {total_antes - total_despues}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n[ERROR] No se pudo completar la limpieza: {e}")
    
    print("\n" + "="*90 + "\n")

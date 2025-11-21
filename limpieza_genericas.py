"""
Limpieza AUTOMÁTICA de canciones genéricas/fallback sin confirmación
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Cancion

# Patrones que indican canciones genéricas/fallback
GENERIC_PATTERNS = [
    ('Artista Desconocido', 'Transmisión en Vivo'),
    ('Desconocido', 'Transmisión en Vivo'),
    ('Unknown', 'Unknown'),
    ('Unknown', 'Stream'),
]

with app.app_context():
    print("\n" + "="*90)
    print("LIMPIEZA AUTOMATICA DE CANCIONES GENERICAS")
    print("="*90 + "\n")
    
    total_antes = db.session.query(Cancion).count()
    print(f"[STATUS] Canciones totales ANTES: {total_antes}\n")
    
    # Contar genéricas por patrón
    print("Identificando canciones a eliminar:")
    print("-" * 90)
    
    total_a_eliminar = 0
    
    for artista_pattern, titulo_pattern in GENERIC_PATTERNS:
        count = db.session.query(Cancion).filter(
            Cancion.artista.ilike(artista_pattern),
            Cancion.titulo.ilike(titulo_pattern)
        ).count()
        
        if count > 0:
            print(f"  [{artista_pattern}] - [{titulo_pattern}] = {count} canciones")
            total_a_eliminar += count
    
    print(f"\n[TOTAL] Canciones a eliminar: {total_a_eliminar}")
    print(f"[PERCENT] Seria {100*total_a_eliminar//total_antes}% del total\n")
    
    print("-" * 90)
    print("[INICIANDO ELIMINACION...]\n")
    
    eliminadas = 0
    
    for artista_pattern, titulo_pattern in GENERIC_PATTERNS:
        print(f"  Eliminando: {artista_pattern} - {titulo_pattern}...", end=" ", flush=True)
        
        canciones = db.session.query(Cancion).filter(
            Cancion.artista.ilike(artista_pattern),
            Cancion.titulo.ilike(titulo_pattern)
        ).all()
        
        for cancion in canciones:
            db.session.delete(cancion)
            eliminadas += 1
        
        print(f"[OK] {len(canciones)} eliminadas")
    
    # Commit
    try:
        db.session.commit()
        
        total_despues = db.session.query(Cancion).count()
        
        print("\n" + "-" * 90)
        print("[OK] LIMPIEZA COMPLETADA EXITOSAMENTE\n")
        print(f"  Canciones ANTES:   {total_antes}")
        print(f"  Canciones DESPUES: {total_despues}")
        print(f"  Eliminadas:        {total_antes - total_despues}")
        print(f"  Preservadas:       {total_despues}\n")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n[ERROR] No se pudo completar la limpieza: {e}")
    
    print("="*90 + "\n")

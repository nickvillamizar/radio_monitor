"""
Limpieza SQL directa de canciones genéricas
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db

with app.app_context():
    print("\n" + "="*90)
    print("LIMPIEZA SQL DIRECTA DE CANCIONES GENERICAS")
    print("="*90 + "\n")
    
    # Primero, contar cuántas hay
    result = db.session.execute(db.text("""
        SELECT COUNT(*) FROM canciones 
        WHERE (artista ILIKE 'Artista Desconocido' AND titulo ILIKE 'Transmisi%n en Vivo')
           OR (artista ILIKE 'Desconocido' AND titulo ILIKE 'Transmisi%n en Vivo')
           OR (artista ILIKE 'Unknown' AND titulo ILIKE 'Unknown')
    """))
    
    count_antes = result.scalar()
    print(f"Canciones genéricas encontradas: {count_antes}\n")
    
    total_antes = db.session.execute(db.text("SELECT COUNT(*) FROM canciones")).scalar()
    print(f"Total canciones ANTES: {total_antes}")
    
    # Eliminar
    print("\n[ELIMINANDO...]")
    
    try:
        eliminadas = db.session.execute(db.text("""
            DELETE FROM canciones 
            WHERE (artista ILIKE 'Artista Desconocido' AND titulo ILIKE 'Transmisi%n en Vivo')
               OR (artista ILIKE 'Desconocido' AND titulo ILIKE 'Transmisi%n en Vivo')
               OR (artista ILIKE 'Unknown' AND titulo ILIKE 'Unknown')
        """))
        
        db.session.commit()
        
        total_despues = db.session.execute(db.text("SELECT COUNT(*) FROM canciones")).scalar()
        
        print(f"\n[OK] LIMPIEZA COMPLETADA")
        print(f"  Total canciones ANTES:   {total_antes}")
        print(f"  Total canciones DESPUES: {total_despues}")
        print(f"  Eliminadas:              {total_antes - total_despues}")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] {e}")
    
    print("\n" + "="*90 + "\n")

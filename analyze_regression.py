"""
Análisis de regresión - Por qué canciones genéricas aumentaron?
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from sqlalchemy import func

with app.app_context():
    print("\n" + "="*90)
    print("ANALISIS DE REGRESION - PORQUE SUBIERON LAS GENERICAS?")
    print("="*90 + "\n")
    
    # Total de canciones
    total = db.session.query(Cancion).count()
    
    # Canciones genéricas
    genericas = db.session.query(Cancion).filter(
        (Cancion.artista.like('%Desconocido%')) |
        (Cancion.titulo.like('%Transmisión%')) |
        (Cancion.titulo.like('%Transmision%')) |
        (Cancion.artista == 'Artista Desconocido')
    ).count()
    
    print(f"Estadísticas globales:")
    print(f"  Total canciones: {total}")
    print(f"  Genéricas: {genericas} ({100*genericas//total}%)")
    print(f"  Reales: {total - genericas} ({100*(total-genericas)//total}%)\n")
    
    # Detallar cuáles son genéricas exactas
    print(f"Tipos de canciones genéricas:\n")
    
    # Desconocido - Transmisión en Vivo (más común)
    tipo1 = db.session.query(Cancion).filter(
        Cancion.artista == 'Artista Desconocido',
        Cancion.titulo == 'Transmisión en Vivo'
    ).count()
    print(f"1. 'Artista Desconocido' - 'Transmisión en Vivo': {tipo1}")
    
    # Desconocido - algo
    tipo2 = db.session.query(Cancion).filter(
        Cancion.artista.like('%Desconocido%')
    ).count()
    print(f"2. Artista contiene 'Desconocido': {tipo2}")
    
    # Título contiene Transmisión
    tipo3 = db.session.query(Cancion).filter(
        Cancion.titulo.like('%Transmisión%')
    ).count()
    print(f"3. Título contiene 'Transmisión': {tipo3}")
    
    # Por emisora: cuáles tienen más genéricas?
    print(f"\nEmisoras con más canciones genéricas:\n")
    
    emission_stats = db.session.query(
        Emisora.nombre,
        func.count(Cancion.id).label('total'),
        func.sum(
            func.cast(
                (Cancion.artista.like('%Desconocido%')) | 
                (Cancion.titulo.like('%Transmisión%')) |
                (Cancion.artista == 'Artista Desconocido'),
                Integer
            )
        ).label('genericas')
    ).join(Cancion, Cancion.emisora_id == Emisora.id).group_by(
        Emisora.id, Emisora.nombre
    ).order_by(
        func.count(Cancion.id).desc()
    ).limit(10).all()
    
    from sqlalchemy import Integer, case
    
    for nombre, total_e, genericas_e in emission_stats:
        if total_e > 0:
            pct = 100 * (genericas_e or 0) // total_e
            print(f"  {nombre:40s} - {total_e:4d} total, {genericas_e or 0:4d} genéricas ({pct}%)")
    
    print(f"\n" + "="*90)
    print(f"CONCLUSION:")
    print(f"-" * 90)
    print(f"El aumento de genéricas sugiere que:")
    print(f"1. El monitor está detectando 'Desconocido' más seguido")
    print(f"2. Posiblemente los streams devuelven metadata vacia o inválida")
    print(f"3. El fallback a AudD no está funcionando")
    print(f"4. URLs devuelven HTTP 200 pero stream está vacío o corrupto")
    print(f"\nAcción recomendada:")
    print(f"- Revisar logs del monitor reciente")
    print(f"- Verificar si AudD está configurado (AUDD_TOKEN)")
    print(f"- Probar ICY metadata manualmente en streams problemáticos")
    print(f"="*90 + "\n")

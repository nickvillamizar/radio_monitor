"""
Configurar token AudD y forzar ciclo completo de detecci√≥n
"""

import os

# Configurar token AudD
AUDD_TOKEN = "270b4f1f1e3fbefe8e76febd4b29b42f"
os.environ['AUDD_API_TOKEN'] = AUDD_TOKEN

# Configurar variables necesarias
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from utils.stream_reader import actualizar_emisoras
from datetime import datetime

with app.app_context():
    print("\n" + "="*100)
    print("CONFIGURACION DE AudD Y CICLO COMPLETO DE DETECCION")
    print("="*100 + "\n")
    
    # Verificar configuración
    print("[STEP 1] Verificar configuración AudD")
    print("-" * 100)
    audd_token_config = app.config.get("AUDD_API_TOKEN")
    print(f"  Token configurado: {AUDD_TOKEN[:20]}... (primeros 20 caracteres)")
    print(f"  Token en app.config: {'OK - Configurado' if audd_token_config else 'FALTA - Sin configurar'}")
    print()
    
    # Contar estado ANTES
    print("[STEP 2] Estado ANTES del ciclo de detección")
    print("-" * 100)
    total_canciones_antes = db.session.query(Cancion).count()
    genericas_antes = db.session.query(Cancion).filter(
        Cancion.artista.ilike('%Desconocido%')
    ).count()
    
    print(f"  Canciones totales: {total_canciones_antes}")
    print(f"  Canciones genéricas: {genericas_antes}")
    print(f"  Canciones reales: {total_canciones_antes - genericas_antes}")
    print()
    
    # Ejecutar actualización
    print("[STEP 3] Ejecutando ciclo completo de detección CON AudD")
    print("-" * 100)
    print(f"  Procesando 71 emisoras con fallback AudD habilitado...")
    print(f"  Esto tomará ~5-10 minutos (15s por emisora en promedio)\n")
    
    try:
        actualizar_emisoras(fallback_to_audd=True, dedupe_seconds=300)
        print(f"\n  [OK] Ciclo de detección completado")
    except Exception as e:
        print(f"\n  [ERROR] {e}")
    
    # Contar estado DESPUÉS
    print()
    print("[STEP 4] Estado DESPUÉS del ciclo de detección")
    print("-" * 100)
    total_canciones_despues = db.session.query(Cancion).count()
    genericas_despues = db.session.query(Cancion).filter(
        Cancion.artista.ilike('%Desconocido%')
    ).count()
    
    print(f"  Canciones totales: {total_canciones_despues}")
    print(f"  Canciones genéricas: {genericas_despues}")
    print(f"  Canciones reales: {total_canciones_despues - genericas_despues}")
    print()
    
    # Resumen de cambios
    print("[STEP 5] Resumen de cambios")
    print("-" * 100)
    nuevas_canciones = total_canciones_despues - total_canciones_antes
    menos_genericas = genericas_antes - genericas_despues
    
    print(f"  Nuevas canciones detectadas: +{nuevas_canciones}")
    print(f"  Reducción de genéricas: -{menos_genericas}")
    print(f"  Aumento de calidad: {100*menos_genericas//genericas_antes}% menos polución")
    
    if nuevas_canciones > 0:
        print(f"\n  [SUCCESS] Se detectaron {nuevas_canciones} canciones nuevas")
        print(f"  [SUCCESS] Calidad mejorada significativamente")
    else:
        print(f"\n  [INFO] No se detectaron canciones nuevas")
        print(f"  [INFO] Los streams probablemente no tienen audio detectable")
    
    print()
    print("="*100)
    print(f"Ciclo completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100 + "\n")

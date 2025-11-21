import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from utils.stream_reader import actualizar_emisoras
from app import app
from models.emisoras import Emisora
from datetime import datetime

print("[TEST] Ejecutando actualizar_emisoras una sola vez...\n")
with app.app_context():
    actualizar_emisoras()

print("\n" + "="*80)
print("[TEST] Ciclo completado. Verificando BD...")
print("="*80 + "\n")

with app.app_context():
    today = datetime.now().date()
    updated_today = Emisora.query.filter(
        db.func.DATE(Emisora.ultima_actualizacion) == today
    ).all()
    
    print(f'RESUMEN:')
    print(f'  Actualizadas HOY: {len(updated_today)}/71')
    
    bad = Emisora.query.filter(Emisora.ultima_cancion.contains('Artista Desconocido')).count()
    print(f'  Con Artista Desconocido: {bad}/71')
    
    print(f'\nÚltimas 10 actualizadas:')
    recent = Emisora.query.order_by(Emisora.ultima_actualizacion.desc()).limit(10).all()
    for e in recent:
        minutos = (datetime.now() - e.ultima_actualizacion).total_seconds() / 60
        cancion = (e.ultima_cancion or 'N/A')[:70]
        print(f'  {minutos:6.1f}m | {e.nombre[:30]:30} | {cancion}')

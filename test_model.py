import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora

with app.app_context():
    try:
        # Test 1: Count total
        count = db.session.query(Emisora).count()
        print(f'1. Total emisoras en BD: {count}')
        
        # Test 2: Get all
        emisoras = Emisora.query.order_by(Emisora.nombre).all()
        print(f'2. Emisoras obtenidas por query: {len(emisoras)}')
        
        # Test 3: Show first 3
        if emisoras:
            print('3. Primeras 3:')
            for e in emisoras[:3]:
                print(f'   - {e.id}: {e.nombre}')
        else:
            print('3. ERROR: Query retorno lista vacia')
            
    except Exception as ex:
        print(f'ERROR: {ex}')
        import traceback
        traceback.print_exc()

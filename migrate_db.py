#!/usr/bin/env python
# archivo: migrate_db.py - Aplicar migración de validación de streams
"""
Script para aplicar automáticamente los cambios a la base de datos.
No requiere SQL manual.

Uso:
    python migrate_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import db
from config import Config
from models.emisoras import Emisora
from flask import Flask
from sqlalchemy import inspect, Column, Boolean, DateTime, String

def check_columns_exist(db_session):
    """Verifica si las columnas ya existen."""
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('emisoras')]
    
    required = ['url_valida', 'es_stream_activo', 'ultima_validacion', 'diagnostico']
    existing = [c for c in required if c in columns]
    missing = [c for c in required if c not in columns]
    
    return existing, missing

def apply_migration():
    """Aplica la migración."""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        print("🔄 Verificando base de datos...\n")
        
        try:
            existing, missing = check_columns_exist(db.session)
            
            print(f"✓ Columnas existentes: {len(existing)}")
            for col in existing:
                print(f"  ✓ {col}")
            
            if missing:
                print(f"\n⚠️  Columnas faltantes: {len(missing)}")
                for col in missing:
                    print(f"  ✗ {col}")
                
                print("\n🔧 Aplicando migración...\n")
                
                # SQLAlchemy lo hace automáticamente
                db.create_all()
                
                print("✅ Migración completada")
                
                # Verificar de nuevo
                existing, missing = check_columns_exist(db.session)
                
                if not missing:
                    print("✓ Todas las columnas fueron creadas correctamente")
                else:
                    print(f"⚠️  Advertencia: Columnas que aún faltan: {missing}")
                    return 1
            else:
                print("\n✅ La base de datos ya está actualizada")
                print("   No se requieren cambios")
                return 0
        
        except Exception as e:
            print(f"\n❌ Error durante la migración: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    print("\n" + "="*80)
    print("✅ Listo para ejecutar validación de streams")
    print("   Ejecute: flask validate-streams")
    print("="*80)
    
    return 0

if __name__ == '__main__':
    sys.exit(apply_migration())

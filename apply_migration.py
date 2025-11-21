#!/usr/bin/env python
"""
Aplicar migración de validación de streams
Agrega 4 columnas a la tabla emisoras para almacenar resultados de validación
"""
import os
import sys
from sqlalchemy import text, inspect
from utils.db import db
from app import app

def apply_migration():
    """Aplica la migración de validación de streams."""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('emisoras')]
            
            # Verificar qué columnas faltan
            missing_cols = [
                'url_valida',
                'es_stream_activo', 
                'ultima_validacion',
                'diagnostico'
            ]
            
            cols_to_add = [col for col in missing_cols if col not in columns]
            
            if not cols_to_add:
                print("[OK] Todas las columnas de validacion ya existen.")
                return True
            
            print(f"[*] Se agregaran {len(cols_to_add)} columnas faltantes:")
            for col in cols_to_add:
                print(f"    - {col}")
            
            # Usar transacción para ejecutar todos los ALTER TABLE
            with db.engine.begin() as conn:
                # url_valida
                if 'url_valida' in cols_to_add:
                    print("[+] Agregando columna url_valida...")
                    conn.execute(text("""
                        ALTER TABLE emisoras 
                        ADD COLUMN url_valida BOOLEAN DEFAULT TRUE
                    """))
                
                # es_stream_activo
                if 'es_stream_activo' in cols_to_add:
                    print("[+] Agregando columna es_stream_activo...")
                    conn.execute(text("""
                        ALTER TABLE emisoras 
                        ADD COLUMN es_stream_activo BOOLEAN DEFAULT TRUE
                    """))
                
                # ultima_validacion
                if 'ultima_validacion' in cols_to_add:
                    print("[+] Agregando columna ultima_validacion...")
                    conn.execute(text("""
                        ALTER TABLE emisoras 
                        ADD COLUMN ultima_validacion TIMESTAMP NULL
                    """))
                
                # diagnostico
                if 'diagnostico' in cols_to_add:
                    print("[+] Agregando columna diagnostico...")
                    conn.execute(text("""
                        ALTER TABLE emisoras 
                        ADD COLUMN diagnostico VARCHAR(500) NULL
                    """))
            
            print("\n[OK] Migracion aplicada exitosamente!")
            return True
            
        except Exception as e:
            print(f"[!] Error durante migracion: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = apply_migration()
    sys.exit(0 if success else 1)

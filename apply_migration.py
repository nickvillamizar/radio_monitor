#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Aplicar migraciones a la base de datos
"""
import os
import sys
from sqlalchemy import text, inspect
from utils.db import db
from app import app

def apply_migration():
    """Aplica todas las migraciones pendientes."""
    with app.app_context():
        try:
            print("\n[MIGRACIONES] Aplicando actualizaciones a base de datos...")
            print("="*80)
            
            inspector = inspect(db.engine)
            
            # ============================================================
            # MIGRACIÓN 1: Columnas de validación de streams en emisoras
            # ============================================================
            print("\n[1/3] Verificando columnas de validación en emisoras...")
            emisoras_cols = [col['name'] for col in inspector.get_columns('emisoras')]
            
            validation_cols = ['url_valida', 'es_stream_activo', 'ultima_validacion', 'diagnostico']
            missing_validation = [col for col in validation_cols if col not in emisoras_cols]
            
            if missing_validation:
                print(f"  [ACCIÓN] Agregando {len(missing_validation)} columnas...")
                with db.engine.begin() as conn:
                    if 'url_valida' in missing_validation:
                        conn.execute(text("ALTER TABLE emisoras ADD COLUMN url_valida BOOLEAN DEFAULT TRUE"))
                    if 'es_stream_activo' in missing_validation:
                        conn.execute(text("ALTER TABLE emisoras ADD COLUMN es_stream_activo BOOLEAN DEFAULT TRUE"))
                    if 'ultima_validacion' in missing_validation:
                        conn.execute(text("ALTER TABLE emisoras ADD COLUMN ultima_validacion TIMESTAMP NULL"))
                    if 'diagnostico' in missing_validation:
                        conn.execute(text("ALTER TABLE emisoras ADD COLUMN diagnostico VARCHAR(500) NULL"))
                print("  ✓ Columnas de validación agregadas")
            else:
                print("  ✓ Todas las columnas de validación existen")
            
            # ============================================================
            # MIGRACIÓN 2: Campo estado en emisoras
            # ============================================================
            print("\n[2/3] Verificando campo 'estado' en emisoras...")
            if 'estado' not in emisoras_cols:
                print("  [ACCIÓN] Agregando campo 'estado'...")
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE emisoras ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'activo_hoy'"))
                    conn.execute(text("CREATE INDEX idx_emisoras_estado ON emisoras(estado)"))
                print("  ✓ Campo 'estado' agregado")
            else:
                print("  ✓ Campo 'estado' ya existe")
            
            # ============================================================
            # MIGRACIÓN 3: Campos de metadata de detección en canciones
            # ============================================================
            print("\n[3/3] Verificando campos de metadata en canciones...")
            canciones_cols = [col['name'] for col in inspector.get_columns('canciones')]
            
            metadata_cols = ['fuente', 'razon_prediccion', 'confianza_prediccion']
            missing_metadata = [col for col in metadata_cols if col not in canciones_cols]
            
            if missing_metadata:
                print(f"  [ACCIÓN] Agregando {len(missing_metadata)} columnas...")
                with db.engine.begin() as conn:
                    if 'fuente' in missing_metadata:
                        conn.execute(text("ALTER TABLE canciones ADD COLUMN fuente VARCHAR(20) DEFAULT 'icy'"))
                    if 'razon_prediccion' in missing_metadata:
                        conn.execute(text("ALTER TABLE canciones ADD COLUMN razon_prediccion VARCHAR(200)"))
                    if 'confianza_prediccion' in missing_metadata:
                        conn.execute(text("ALTER TABLE canciones ADD COLUMN confianza_prediccion FLOAT"))
                    conn.execute(text("CREATE INDEX idx_canciones_fuente ON canciones(fuente)"))
                print("  ✓ Campos de metadata agregados")
            else:
                print("  ✓ Todos los campos de metadata existen")
            
            print("\n" + "="*80)
            print("[OK] Todas las migraciones completadas exitosamente!")
            print("="*80 + "\n")
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Error durante migraciones: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = apply_migration()
    sys.exit(0 if success else 1)

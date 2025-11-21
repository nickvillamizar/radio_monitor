#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SISTEMA DE ACTUALIZACIÓN FORZADA - EMISORAS ESTANCADAS
1. Aplica migración para agregar campo 'estado'
2. Resetea todas las emisoras estancadas
3. Marca para procesamiento inmediato
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta
from sqlalchemy import text
import sys

def aplicar_migracion():
    """Aplica migración si es necesario"""
    print("\n[MIGRACIÓN] Verificando si campo 'estado' existe...")
    
    with app.app_context():
        try:
            # Intentar leer el campo
            db.session.execute(text("SELECT estado FROM emisoras LIMIT 1"))
            db.session.commit()
            print("[OK] Campo 'estado' ya existe ✓")
            return True
        except Exception as check_ex:
            # Campo no existe, necesita agregarse
            print(f"[ACCIÓN] Agregando campo 'estado' a emisoras...")
            db.session.rollback()  # Limpiar transacción fallida
            
            try:
                db.session.execute(text("""
                    ALTER TABLE emisoras 
                    ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'activo_hoy'
                """))
                db.session.commit()
                print("[OK] Campo 'estado' agregado ✓")
                
                # Crear índice
                db.session.execute(text("CREATE INDEX idx_emisoras_estado ON emisoras(estado)"))
                db.session.commit()
                print("[OK] Índice creado ✓")
                return True
                
            except Exception as add_ex:
                print(f"[ERROR] No se pudo agregar campo: {add_ex}")
                db.session.rollback()
                return False

def resetear_estancadas():
    """Resetea todas las emisoras que no se han actualizado en 24h"""
    print("\n" + "="*80)
    print("RESETEO DE EMISORAS ESTANCADAS")
    print("="*80)
    
    with app.app_context():
        # 1. OBTENER TODAS
        todas = db.session.query(Emisora).all()
        total = len(todas)
        print(f"\n[SCAN] Total de emisoras: {total}")
        
        # 2. IDENTIFICAR ESTANCADAS
        ahora = datetime.now()
        hace_24h = ahora - timedelta(hours=24)
        
        estancadas = []
        for e in todas:
            if e.ultima_actualizacion is None or e.ultima_actualizacion < hace_24h:
                estancadas.append(e)
        
        print(f"[PROBLEMA] Emisoras ESTANCADAS (>24h sin actualizar): {len(estancadas)}/{total}")
        
        if len(estancadas) == 0:
            print("[OK] Todas las emisoras están actualizadas! ✓")
            return True
        
        # 3. MOSTRAR LISTA
        print(f"\n[LISTA] Primeras 20 estancadas:")
        print("-" * 80)
        for idx, e in enumerate(estancadas[:20], 1):
            dias = (ahora - e.ultima_actualizacion).days if e.ultima_actualizacion else "NUNCA"
            estado_actual = e.estado if hasattr(e, 'estado') and e.estado else "sin_estado"
            print(f"{idx:2d}. {e.nombre:40s} | {str(dias):>5} | {estado_actual}")
        
        if len(estancadas) > 20:
            print(f"... y {len(estancadas) - 20} más")
        
        # 4. RESETEAR
        print("\n" + "-" * 80)
        print("[ACCIÓN] Reseteando para fuerza actualización...")
        print("-" * 80)
        
        actualizadas = 0
        try:
            for e in estancadas:
                # Resetear timestamps
                e.ultima_actualizacion = None
                e.estado = 'activo_hoy'
                e.ultima_cancion = None
                
                actualizadas += 1
                if actualizadas % 10 == 0:
                    print(f"  Procesadas {actualizadas}/{len(estancadas)}...")
            
            db.session.commit()
            print(f"\n[SUCCESS] ✓ Reseteadas {actualizadas} emisoras")
            
        except Exception as ex:
            print(f"\n[ERROR] Fallo al resetear: {ex}")
            db.session.rollback()
            return False
        
        # 5. VERIFICAR
        print("\n[VERIFICACIÓN] Estado post-reset...")
        print("-" * 80)
        
        activo_hoy = db.session.query(Emisora).filter(Emisora.estado == 'activo_hoy').count()
        activo_ayer = db.session.query(Emisora).filter(Emisora.estado == 'activo_ayer').count()
        inactivo = db.session.query(Emisora).filter(Emisora.estado == 'inactivo').count()
        
        print(f"Estado 'activo_hoy': {activo_hoy}")
        print(f"Estado 'activo_ayer': {activo_ayer}")
        print(f"Estado 'inactivo': {inactivo}")
        
        print("\n[CONFIRMACIÓN] Top 15 después del reset:")
        print("-" * 80)
        top_15 = db.session.query(Emisora).order_by(Emisora.id).limit(15).all()
        for idx, e in enumerate(top_15, 1):
            fecha = e.ultima_actualizacion.strftime("%Y-%m-%d %H:%M:%S") if e.ultima_actualizacion else "NULL"
            print(f"{idx:2d}. {e.nombre:40s} | {fecha:19s} | {e.estado}")
        
        print("\n" + "="*80)
        print("[LISTO] Sistema listo para scannear TODAS las emisoras")
        print("="*80 + "\n")
        
        return True

def main():
    try:
        # Aplicar migración
        if not aplicar_migracion():
            return False
        
        # Resetear estancadas
        with app.app_context():
            return resetear_estancadas()
    
    except Exception as ex:
        print(f"\n[FATAL] Error: {ex}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUERZA ACTUALIZACIÓN DE TODAS LAS EMISORAS ESTANCADAS
Resetea el estado y marca para procesamiento inmediato
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta
import sys

def main():
    with app.app_context():
        print("\n" + "="*80)
        print("FUERZA ACTUALIZACIÓN - EMISORAS ESTANCADAS")
        print("="*80 + "\n")
        
        # 1. OBTENER TODAS LAS EMISORAS
        todas = db.session.query(Emisora).all()
        total = len(todas)
        print(f"[SCAN] Total de emisoras: {total}")
        
        # 2. IDENTIFICAR ESTANCADAS (no actualizadas en 24h)
        ahora = datetime.now()
        hace_24h = ahora - timedelta(hours=24)
        
        estancadas = []
        for e in todas:
            if e.ultima_actualizacion is None or e.ultima_actualizacion < hace_24h:
                estancadas.append(e)
        
        print(f"\n[PROBLEMA] Emisoras ESTANCADAS hace >24h: {len(estancadas)}/{total}")
        
        if len(estancadas) == 0:
            print("[OK] Todas las emisoras están actualizadas!")
            return
        
        # 3. MOSTRAR LISTA DE ESTANCADAS
        print("\n[LISTA] Primeras 20 estancadas:")
        print("-" * 80)
        for idx, e in enumerate(estancadas[:20], 1):
            dias = (ahora - e.ultima_actualizacion).days if e.ultima_actualizacion else "NULL"
            print(f"{idx:2d}. {e.nombre:40s} | {dias:>3} días | Estado: {e.estado}")
        
        if len(estancadas) > 20:
            print(f"... y {len(estancadas) - 20} más")
        
        # 4. RESETEAR TIMESTAMPS Y ESTADO
        print("\n" + "-" * 80)
        print("[ACCIÓN] Reseteando timestamps para fuerza actualización...")
        print("-" * 80)
        
        actualizadas = 0
        try:
            for e in estancadas:
                # Resetear a NULL para que sea procesada como NUEVA
                e.ultima_actualizacion = None
                e.estado = 'activo_hoy'  # Forzar estado ACTIVO
                e.ultima_cancion = None
                e.ultimo_artista = None
                
                actualizadas += 1
                if actualizadas % 10 == 0:
                    print(f"  [{actualizadas}/{len(estancadas)}] Reseteadas...")
            
            # COMMIT
            db.session.commit()
            print(f"\n[SUCCESS] ✓ Reseteadas {actualizadas} emisoras")
            
        except Exception as ex:
            print(f"\n[ERROR] Error al resetear: {ex}")
            db.session.rollback()
            return
        
        # 5. VERIFICAR RESULTADO
        print("\n" + "-" * 80)
        print("[VERIFICACIÓN] Estado post-reset...")
        print("-" * 80)
        
        actualizadas_ahora = db.session.query(Emisora).filter(
            (Emisora.ultima_actualizacion == None) | 
            (Emisora.ultima_actualizacion < hace_24h)
        ).count()
        
        print(f"Emisoras SIN actualizar: {actualizadas_ahora}/{total}")
        print(f"Emisoras CON 'activo_hoy': {db.session.query(Emisora).filter(Emisora.estado == 'activo_hoy').count()}/{total}")
        
        # 6. MOSTRAR TOP ESTANCADAS DESPUÉS
        print("\n[CONFIRMACIÓN] Top 10 después del reset:")
        print("-" * 80)
        top_10 = db.session.query(Emisora).order_by(Emisora.ultima_actualizacion.desc()).limit(10).all()
        for idx, e in enumerate(top_10, 1):
            fecha = e.ultima_actualizacion.strftime("%Y-%m-%d %H:%M:%S") if e.ultima_actualizacion else "NULL"
            print(f"{idx:2d}. {e.nombre:40s} | {fecha} | {e.estado}")
        
        print("\n" + "="*80)
        print("[LISTO] Sistema listo para scannear todas las emisoras")
        print("="*80 + "\n")

if __name__ == '__main__':
    main()

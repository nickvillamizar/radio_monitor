#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MONITOR DE ACTUALIZACIÓN EN TIEMPO REAL
Muestra el progreso mientras app.py scannea todas las emisoras
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta
import time
import sys

def mostrar_estado():
    """Muestra estado actual del sistema"""
    with app.app_context():
        ahora = datetime.now()
        hace_24h = ahora - timedelta(hours=24)
        
        # Contadores
        total_emisoras = db.session.query(Emisora).count()
        activo_hoy = db.session.query(Emisora).filter(
            Emisora.ultima_actualizacion >= hace_24h
        ).count()
        activo_ayer = db.session.query(Emisora).filter(
            (Emisora.ultima_actualizacion < hace_24h) &
            (Emisora.ultima_actualizacion >= ahora - timedelta(hours=48))
        ).count()
        inactivo = db.session.query(Emisora).filter(
            (Emisora.ultima_actualizacion == None) |
            (Emisora.ultima_actualizacion < ahora - timedelta(hours=48))
        ).count()
        
        total_canciones = db.session.query(Cancion).count()
        
        # Mostrar
        print(f"\n[{ahora.strftime('%H:%M:%S')}] ESTADO DEL SISTEMA")
        print("=" * 80)
        print(f"Emisoras ACTIVAS (hoy):    {activo_hoy:2d}/71 ({activo_hoy*100//71}%)")
        print(f"Emisoras ACTIVAS (ayer):   {activo_ayer:2d}/71 ({activo_ayer*100//71}%)")
        print(f"Emisoras INACTIVAS:        {inactivo:2d}/71 ({inactivo*100//71}%)")
        print("-" * 80)
        print(f"Total canciones:           {total_canciones}")
        
        # TOP 10 ACTUALIZADAS
        if activo_hoy > 0:
            print("\n[TOP 10 ACTUALIZADAS RECIENTEMENTE]")
            print("-" * 80)
            top = db.session.query(Emisora).order_by(
                Emisora.ultima_actualizacion.desc()
            ).limit(10).all()
            
            for idx, e in enumerate(top, 1):
                tiempo = e.ultima_actualizacion
                hace = (ahora - tiempo).total_seconds() if tiempo else None
                
                if hace is None:
                    tiempo_str = "NUNCA"
                elif hace < 60:
                    tiempo_str = f"Hace {int(hace)}s"
                elif hace < 3600:
                    tiempo_str = f"Hace {int(hace/60)}m"
                else:
                    tiempo_str = f"Hace {int(hace/3600)}h"
                
                cancion = e.ultima_cancion[:50] if e.ultima_cancion else "SIN CANCIÓN"
                print(f"{idx:2d}. {e.nombre:35s} | {tiempo_str:12s} | {cancion}")
        
        # TOP 5 MÁS ANTIGUAS
        print("\n[TOP 5 MÁS ANTIGUAS (INACTIVAS)]")
        print("-" * 80)
        oldest = db.session.query(Emisora).order_by(
            Emisora.ultima_actualizacion.asc()
        ).limit(5).all()
        
        for idx, e in enumerate(oldest, 1):
            tiempo = e.ultima_actualizacion
            fecha_str = tiempo.strftime("%Y-%m-%d %H:%M") if tiempo else "NUNCA"
            print(f"{idx}. {e.nombre:35s} | {fecha_str}")
        
        print("=" * 80)

def main():
    print("\n" + "="*80)
    print("MONITOR DE ACTUALIZACIÓN EN TIEMPO REAL")
    print("Sistema scanneando las 71 emisoras...")
    print("Presiona Ctrl+C para detener")
    print("="*80)
    
    try:
        while True:
            mostrar_estado()
            time.sleep(30)  # Actualizar cada 30 segundos
    except KeyboardInterrupt:
        print("\n\n[DETENIDO] Monitor finalizado")
        sys.exit(0)

if __name__ == '__main__':
    main()

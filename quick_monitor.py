#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Monitor rápido del progreso de actualización"""
import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta
import time
import sys

def status():
    with app.app_context():
        ahora = datetime.now()
        hace_24h = ahora - timedelta(hours=24)
        
        activo_hoy = db.session.query(Emisora).filter(Emisora.ultima_actualizacion >= hace_24h).count()
        inactivo = 71 - activo_hoy
        total_canciones = db.session.query(Cancion).count()
        
        # TOP 5 recientes
        top_recientes = db.session.query(Emisora).order_by(Emisora.ultima_actualizacion.desc()).limit(5).all()
        
        print(f"\r[{ahora.strftime('%H:%M:%S')}] ACTIVAS: {activo_hoy}/71 ({activo_hoy*100//71}%) | PENDIENTES: {inactivo} | CANCIONES: {total_canciones:,}", end="", flush=True)

if __name__ == '__main__':
    print("\n[MONITOR] Actualizando cada 10 segundos... Presiona Ctrl+C para detener\n")
    try:
        while True:
            status()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\n[OK] Monitor finalizado\n")

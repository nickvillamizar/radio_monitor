#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
from app import app, db
from models.emisoras import Emisora, Cancion
from datetime import datetime, timedelta

with app.app_context():
    ahora = datetime.now()
    hace_24h = ahora - timedelta(hours=24)
    
    activo_hoy = db.session.query(Emisora).filter(Emisora.ultima_actualizacion >= hace_24h).count()
    activo_ayer = db.session.query(Emisora).filter((Emisora.ultima_actualizacion < hace_24h) & (Emisora.ultima_actualizacion >= ahora - timedelta(hours=48))).count()
    inactivo = db.session.query(Emisora).filter((Emisora.ultima_actualizacion == None) | (Emisora.ultima_actualizacion < ahora - timedelta(hours=48))).count()
    
    total_canciones = db.session.query(Cancion).count()
    
    print(f"\n[{ahora.strftime('%H:%M:%S')}] ESTADO DEL SISTEMA")
    print("="*80)
    print(f"Emisoras ACTIVAS (hoy):    {activo_hoy:2d}/71 ({activo_hoy*100//71}%)")
    print(f"Emisoras ACTIVAS (ayer):   {activo_ayer:2d}/71 ({activo_ayer*100//71}%)")
    print(f"Emisoras INACTIVAS:        {inactivo:2d}/71 ({inactivo*100//71}%)")
    print("-"*80)
    print(f"Total canciones:           {total_canciones}")
    print("="*80 + "\n")

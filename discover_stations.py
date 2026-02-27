#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Descubrimiento de emisoras reales en BD
"""

import os
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL', 
    'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'))

from app import app
from models.emisoras import Emisora, Cancion
from sqlalchemy import func

print("\n" + "="*80)
print("DESCUBRIMIENTO DE EMISORAS Y ESTADO ACTUAL")
print("="*80 + "\n")

with app.app_context():
    print("TODAS LAS EMISORAS EN BD:\n")
    
    emisoras = Emisora.query.order_by(Emisora.id).all()
    
    for e in emisoras:
        plays = Cancion.query.filter_by(emisora_id=e.id).count()
        last_song = Cancion.query.filter_by(emisora_id=e.id).order_by(
            Cancion.fecha_reproduccion.desc()).first()
        
        last_str = f" | Última: {last_song.artista} - {last_song.titulo}" if last_song else ""
        print(f"[{e.id:3}] {e.nombre:50} | {plays:3} plays{last_str}")
    
    print("\n" + "="*80)
    print("TOTAL:", Emisora.query.count(), "emisoras en BD")
    print("="*80 + "\n")

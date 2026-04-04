#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix corrupt future timestamps in database
Elimina canciones con fechas futuras y resetea ultima_actualizacion de emisoras
"""
import os
from datetime import datetime

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion

with app.app_context():
    print("\n" + "="*100)
    print("FIX DE TIMESTAMPS CORRUPTOS - Limpieza de fechas futuras")
    print("="*100 + "\n")
    
    # Obtener fecha actual
    now = datetime.now()
    print(f"Fecha/hora actual del sistema: {now}\n")
    
    # Contar canciones con fechas futuras
    print("[PASO 1] Detectando canciones con fechas futuras...")
    future_songs = db.session.query(Cancion).filter(
        Cancion.fecha_reproduccion > now
    ).count()
    
    print(f" Canciones con fechas futuras encontradas: {future_songs}")
    
    if future_songs > 0:
        print(f"\n[PASO 2] Eliminando {future_songs} canciones con timestamps corruptos...")
        try:
            deleted = db.session.query(Cancion).filter(
                Cancion.fecha_reproduccion > now
            ).delete()
            
            db.session.commit()
            print(f" [OK] Eliminadas {deleted} canciones")
        except Exception as e:
            db.session.rollback()
            print(f" [ERROR] {e}")
            exit(1)
    else:
        print(" [OK] No hay canciones con fechas futuras")
    
    # Reset emisoras con ultima_actualizacion futura
    print("\n[PASO 3] Reseteando emisoras con fechas futuras...")
    emisoras_futuras = db.session.query(Emisora).filter(
        Emisora.ultima_actualizacion > now
    ).all()
    
    print(f" Emisoras con fechas futuras: {len(emisoras_futuras)}")
    
    if len(emisoras_futuras) > 0:
        for emisora in emisoras_futuras:
            print(f"   - {emisora.nombre}: {emisora.ultima_actualizacion} -> None")
            emisora.ultima_actualizacion = None
        
        try:
            db.session.commit()
            print(f" [OK] Reseteadas {len(emisoras_futuras)} emisoras")
        except Exception as e:
            db.session.rollback()
            print(f" [ERROR] {e}")
            exit(1)
    else:
        print(" [OK] No hay emisoras con fechas futuras")
    
    # Resumen final
    print("\n" + "="*100)
    print("RESUMEN FINAL")
    print("="*100)
    
    total_canciones = db.session.query(Cancion).count()
    total_emisoras = db.session.query(Emisora).count()
    
    print(f"Total canciones en DB: {total_canciones}")
    print(f"Total emisoras en DB: {total_emisoras}")
    print(f"Canciones eliminadas: {future_songs}")
    print(f"Emisoras reseteadas: {len(emisoras_futuras)}")
    
    print("\n[SUCCESS] Limpieza completada. El sistema ahora puede registrar nuevas canciones.")
    print("="*100 + "\n")

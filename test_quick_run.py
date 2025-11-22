#!/usr/bin/env python3
"""Test rápido del detector"""
import os
import sys
sys.path.insert(0, os.getcwd())

from app import app, db
from models.emisoras import Emisora
from utils import stream_reader

with app.app_context():
    print("[*] Conectando a BD...")
    emisoras = Emisora.query.limit(1).all()
    
    if emisoras:
        e = emisoras[0]
        print(f"[*] Probando con {e.nombre}...")
        
        # Simular detección
        try:
            stream_reader.actualizar_emisoras(fallback_to_audd=False)
            print("[OK] Detección completada!")
        except Exception as exc:
            print(f"[ERROR] {exc}")
            import traceback
            traceback.print_exc()
    else:
        print("[WARN] Sin emisoras en BD")

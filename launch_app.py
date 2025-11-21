#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ejecutor de app.py con logging a archivo"""
import subprocess
import sys
import os

log_file = "app_output.log"

print(f"\n[INICIO] Lanzando app.py...")
print(f"[LOG] Logs se guardarán en: {log_file}")
print(f"[INFO] El proceso continuará ejecutándose...\n")

with open(log_file, 'a') as f:
    f.write(f"\n{'='*80}\n")
    f.write(f"INICIO: {open(__file__).readlines()[0]}\n")
    f.write(f"{'='*80}\n\n")
    
    # Ejecutar app.py y guardar output en archivo
    proc = subprocess.Popen(
        [sys.executable, 'app.py'],
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    print(f"[PID] Proceso lanzado con ID: {proc.pid}")
    print(f"[OK] app.py está corriendo en background")
    print(f"\nPara ver el log:")
    print(f"  tail -f {log_file}")

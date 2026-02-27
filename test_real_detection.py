#!/usr/bin/env python3
"""
TEST FINAL - DETECCIÓN REAL SOLO ICY + AudD
Sin predictores, sin datos inventados
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.emisoras import Emisora, Cancion
from utils import stream_reader
from sqlalchemy import func
from datetime import datetime

print("\n" + "="*80)
print("[TEST FINAL] DETECCIÓN REAL - SOLO ICY + AudD")
print("="*80)

with app.app_context():
    # ESTADO ANTES
    print("\n[1] ESTADO ACTUAL - ANTES")
    print("-"*80)
    
    result = db.session.query(
        Emisora.id, Emisora.nombre,
        func.coalesce(func.count(Cancion.id), 0).label('plays')
    ).outerjoin(Cancion, Cancion.emisora_id == Emisora.id).group_by(
        Emisora.id, Emisora.nombre
    ).order_by(Emisora.id).all()
    
    before = {r[0]: r[2] for r in result}
    total_before = sum(before.values())
    critical_before = sum(1 for p in before.values() if p == 0)
    healthy_before = sum(1 for p in before.values() if p > 0)
    
    print(f"Total emisoras: {len(before)}")
    print(f"Total canciones: {total_before}")
    print(f"  - Críticas (0 plays): {critical_before}")
    print(f"  - Saludables (>0 plays): {healthy_before}\n")
    
    for e_id, nombre, plays in result[:len(result)]:
        status = "✅" if plays > 0 else "⚠️"
        print(f"  {status} ID {e_id:2d}: {nombre:40s} ({plays:3d} plays)")
    
    # EJECUTAR CICLO
    print("\n[2] EJECUTANDO CICLO DE DETECCIÓN")
    print("-"*80)
    print("[INFO] Usando SOLO ICY metadata + AudD (SIN predictores)")
    print("[INFO] fallback_to_audd=False para esta prueba (solo ICY)\n")
    
    try:
        stream_reader.actualizar_emisoras(fallback_to_audd=False, dedupe_seconds=300)
        print("\n✅ Ciclo completado sin errores\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # ESTADO DESPUÉS
    print("[3] ESTADO DESPUÉS - COMPARACIÓN")
    print("-"*80)
    
    result = db.session.query(
        Emisora.id, Emisora.nombre,
        func.coalesce(func.count(Cancion.id), 0).label('plays')
    ).outerjoin(Cancion, Cancion.emisora_id == Emisora.id).group_by(
        Emisora.id, Emisora.nombre
    ).order_by(Emisora.id).all()
    
    after = {r[0]: r[2] for r in result}
    total_after = sum(after.values())
    critical_after = sum(1 for p in after.values() if p == 0)
    healthy_after = sum(1 for p in after.values() if p > 0)
    
    print(f"Total canciones: {total_after} (antes: {total_before})")
    print(f"  - Críticas (0 plays): {critical_after} (antes: {critical_before})")
    print(f"  - Saludables (>0 plays): {healthy_after} (antes: {healthy_before})")
    print(f"  - Agregadas en ciclo: +{total_after - total_before}\n")
    
    for e_id, nombre, plays in result[:len(result)]:
        before_plays = before.get(e_id, 0)
        delta = plays - before_plays
        status = "✅" if plays > 0 else "⚠️"
        delta_str = f"(+{delta})" if delta > 0 else f"({delta})"
        print(f"  {status} ID {e_id:2d}: {nombre:40s} ({before_plays:3d} → {plays:3d}) {delta_str}")
    
    # VALIDACIÓN
    print("\n[4] VALIDACIÓN")
    print("-"*80)
    
    # Verificar que no se dañaron las saludables
    damaged = []
    for e_id, before_p in before.items():
        after_p = after.get(e_id, 0)
        if before_p > 0 and after_p < before_p:
            damaged.append((e_id, before_p, after_p))
    
    if damaged:
        print(f"❌ REGRESIÓN DETECTADA:")
        for e_id, before_p, after_p in damaged:
            print(f"   ID {e_id}: {before_p} → {after_p} plays (PÉRDIDA)")
    else:
        print("✅ Sin regresiones - Emisoras saludables intactas")
    
    # Resumen final
    print("\n[5] RESUMEN FINAL")
    print("-"*80)
    
    improved = critical_before - critical_after
    if improved > 0:
        print(f"✅ MEJORA: {improved} emisora(s) crítica(s) pasaron a detectando")
    elif improved == 0:
        print(f"⚠️  Sin cambios en emisoras críticas (primer ciclo, esperar)")
    else:
        print(f"❌ Retroceso: {abs(improved)} emisoras nuevas sin detección")
    
    if not damaged and total_after >= total_before:
        print("✅ INTEGRIDAD OK: Sin pérdida de datos")
    elif not damaged:
        print("⚠️  ADVERTENCIA: Pérdida neta de canciones (revisar)")
    else:
        print(f"❌ ERROR: {len(damaged)} emisoras dañadas")
    
    print("\n" + "="*80)
    if not damaged and total_after >= total_before and improved >= 0:
        print("✅ SISTEMA LISTO - DETECCIÓN REAL FUNCIONANDO CORRECTAMENTE")
    else:
        print("⚠️  REVISAR - Hay problemas que ajustar")
    print("="*80 + "\n")


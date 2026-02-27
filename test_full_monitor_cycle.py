#!/usr/bin/env python3
"""
Test completo de ciclo de monitoreo con todas las correcciones
Verifica que las emisoras problemáticas (ID 11, 12) ahora detecten canciones
"""

import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.emisoras import Cancion, Emisora
from utils.stream_reader import actualizar_emisoras
from sqlalchemy import text

def test_monitor_cycle():
    """Ejecuta ciclo de monitoreo completo"""
    
    with app.app_context():
        print("\n" + "="*70)
        print("[TEST MONITOR] CICLO DE PRUEBA COMPLETO - SISTEMA PRODUCCIÓN")
        print("="*70)
        
        # 1. Contar canciones ANTES
        print("\n[ANTES] Conteo de canciones por emisora:")
        before_counts = {}
        result = db.session.execute(
            text("""
            SELECT e.id, e.nombre, COUNT(c.id) as count
            FROM emisoras e
            LEFT JOIN canciones c ON e.id = c.emisora_id
            GROUP BY e.id, e.nombre
            ORDER BY e.id
            """)
        )
        for row in result:
            before_counts[row[0]] = row[2]
            status = "✅ OK" if row[2] > 0 else "⚠️  SIN DETECTAR"
            print(f"  [ID {row[0]:2d}] {row[1]:40s} | {row[2]:3d} plays {status}")
        
        problematic = [11, 12]  # Emisoras problemáticas
        good = [i for i in before_counts.keys() if i not in problematic]
        
        print(f"\n[INFO] Emisoras problemáticas: {problematic}")
        print(f"[INFO] Emisoras buenas: {good}")
        print(f"[INFO] Total canciones ANTES: {sum(before_counts.values())}")
        
        # 2. Ejecutar ciclo de monitoreo
        print("\n[MONITOR] Iniciando ciclo de actualización...")
        print("-"*70)
        start = time.time()
        try:
            actualizar_emisoras()
            elapsed = time.time() - start
            print(f"[MONITOR] Ciclo completado en {elapsed:.1f}s")
        except Exception as e:
            print(f"[ERROR] Fallo en ciclo: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 3. Contar canciones DESPUÉS
        print("\n[DESPUÉS] Conteo de canciones por emisora:")
        after_counts = {}
        result = db.session.execute(
            text("""
            SELECT e.id, e.nombre, COUNT(c.id) as count
            FROM emisoras e
            LEFT JOIN canciones c ON e.id = c.emisora_id
            GROUP BY e.id, e.nombre
            ORDER BY e.id
            """)
        )
        for row in result:
            after_counts[row[0]] = row[2]
            delta = after_counts[row[0]] - before_counts.get(row[0], 0)
            status = "✅ OK" if after_counts[row[0]] > 0 else "⚠️  SIN DETECTAR"
            delta_str = f"(+{delta})" if delta > 0 else f"({delta})"
            print(f"  [ID {row[0]:2d}] {row[1]:40s} | {after_counts[row[0]]:3d} plays {delta_str} {status}")
        
        # 4. Análisis de resultados
        print("\n" + "="*70)
        print("[RESULTADO] ANÁLISIS")
        print("="*70)
        
        total_before = sum(before_counts.values())
        total_after = sum(after_counts.values())
        total_added = total_after - total_before
        
        print(f"\nTotal de canciones:")
        print(f"  ANTES:  {total_before}")
        print(f"  DESPUÉS: {total_after}")
        print(f"  AGREGADAS: +{total_added}")
        
        # Verificar emisoras problemáticas
        print(f"\nEstaciones problemáticas (deben tener detecciones):")
        problematic_status = {}
        for pid in problematic:
            before = before_counts.get(pid, 0)
            after = after_counts.get(pid, 0)
            added = after - before
            status = "✅ DETECTANDO" if added > 0 else "❌ SIN CAMBIOS"
            problematic_status[pid] = added > 0
            print(f"  ID {pid}: {before} → {after} (Δ +{added}) {status}")
        
        # Verificar que no se dañaron las buenas
        print(f"\nEstaciones buenas (no deben empeorar):")
        good_status = {}
        for gid in good:
            before = before_counts.get(gid, 0)
            after = after_counts.get(gid, 0)
            delta = after - before
            status = "✅ INTACTA" if delta >= 0 else "❌ REGRESIÓN"
            good_status[gid] = delta >= 0
            print(f"  ID {gid}: {before} → {after} (Δ {delta:+d}) {status}")
        
        # 5. Conclusión
        print("\n" + "="*70)
        print("[CONCLUSIÓN]")
        print("="*70)
        
        problematic_ok = all(problematic_status.values())
        regression_ok = all(good_status.values())
        
        if problematic_ok and regression_ok:
            print("✅ EXCELENTE: Sistema en producción listo")
            print("   ✓ Emisoras problemáticas ahora detectan")
            print("   ✓ Emisoras buenas sin regresiones")
            return True
        elif problematic_ok and not regression_ok:
            print("⚠️  ADVERTENCIA: Detección mejorada pero regresión en buenas")
            failed_good = [gid for gid in good if not good_status[gid]]
            print(f"   Regresión en IDs: {failed_good}")
            return False
        elif not problematic_ok:
            print("❌ FALLO: Emisoras problemáticas aún sin detectar")
            failed_prob = [pid for pid in problematic if not problematic_status[pid]]
            print(f"   Sin progreso en IDs: {failed_prob}")
            return False
        
        return True

if __name__ == "__main__":
    success = test_monitor_cycle()
    sys.exit(0 if success else 1)

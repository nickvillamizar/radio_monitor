#!/usr/bin/env python3
"""
AUDITORÍA INTEGRAL DEL SISTEMA DE MONITOREO MUSICAL
====================================================
Verifica:
1. Estado actual de detección en cada emisora
2. Ejecuta un ciclo de actualización
3. Valida que las mejoras funcionan sin romper lo existente
4. Genera reporte detallado
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar la carpeta al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from utils.db import db
from models.emisoras import Emisora, Cancion
from utils import stream_reader
from sqlalchemy import func

def audit_stations_before():
    """Auditar estado ANTES de ejecutar actualizar_emisoras."""
    print("\n" + "="*80)
    print("AUDITORÍA PRE-ACTUALIZACIÓN")
    print("="*80 + "\n")
    
    with app.app_context():
        stats = {}
        
        # Contar plays por emisora
        results = db.session.query(
            Emisora.id,
            Emisora.nombre,
            func.coalesce(func.count(Cancion.id), 0).label("plays")
        ).outerjoin(Cancion, Cancion.emisora_id == Emisora.id).group_by(
            Emisora.id, Emisora.nombre
        ).order_by(func.coalesce(func.count(Cancion.id), 0)).all()
        
        critical = []
        warning = []
        healthy = []
        
        for e_id, nombre, plays in results:
            if plays == 0:
                critical.append((e_id, nombre, plays))
            elif plays <= 2:
                warning.append((e_id, nombre, plays))
            else:
                healthy.append((e_id, nombre, plays))
        
        print(f"[OK] Emisoras SALUDABLES: {len(healthy)}")
        for e_id, nombre, plays in healthy[:5]:
            print(f"     ID {e_id}: {nombre} ({plays} plays)")
        if len(healthy) > 5:
            print(f"     ... y {len(healthy)-5} más")
        
        print(f"\n[!] Emisoras EN RIESGO (1-2 plays): {len(warning)}")
        for e_id, nombre, plays in warning:
            print(f"     ID {e_id}: {nombre} ({plays} plays)")
        
        print(f"\n[X] Emisoras CRÍTICAS (0 plays): {len(critical)}")
        for e_id, nombre, plays in critical:
            print(f"     ID {e_id}: {nombre} ({plays} plays)")
        
        print(f"\nTOTAL: {len(healthy) + len(warning) + len(critical)} emisoras")
        
        return {
            'critical': critical,
            'warning': warning,
            'healthy': healthy
        }

def run_monitor_cycle():
    """Ejecutar un ciclo de actualización."""
    print("\n" + "="*80)
    print("EJECUTANDO CICLO DE ACTUALIZACIÓN")
    print("="*80 + "\n")
    
    with app.app_context():
        try:
            stream_reader.actualizar_emisoras(
                fallback_to_audd=False,  # SIN AudD, solo ICY
                dedupe_seconds=300
            )
            print("\n✅ Ciclo completado exitosamente\n")
            return True
        except Exception as e:
            print(f"\n❌ Error en ciclo: {e}\n")
            import traceback
            traceback.print_exc()
            return False

def audit_stations_after():
    """Auditar estado DESPUÉS de ejecutar actualizar_emisoras."""
    print("\n" + "="*80)
    print("AUDITORÍA POST-ACTUALIZACIÓN")
    print("="*80 + "\n")
    
    with app.app_context():
        results = db.session.query(
            Emisora.id,
            Emisora.nombre,
            func.coalesce(func.count(Cancion.id), 0).label("plays")
        ).outerjoin(Cancion, Cancion.emisora_id == Emisora.id).group_by(
            Emisora.id, Emisora.nombre
        ).order_by(func.coalesce(func.count(Cancion.id), 0)).all()
        
        critical = []
        warning = []
        healthy = []
        
        for e_id, nombre, plays in results:
            if plays == 0:
                critical.append((e_id, nombre, plays))
            elif plays <= 2:
                warning.append((e_id, nombre, plays))
            else:
                healthy.append((e_id, nombre, plays))
        
        print(f"[OK] Emisoras SALUDABLES: {len(healthy)}")
        for e_id, nombre, plays in healthy[:5]:
            print(f"     ID {e_id}: {nombre} ({plays} plays)")
        if len(healthy) > 5:
            print(f"     ... y {len(healthy)-5} más")
        
        print(f"\n[!] Emisoras EN RIESGO (1-2 plays): {len(warning)}")
        for e_id, nombre, plays in warning:
            print(f"     ID {e_id}: {nombre} ({plays} plays)")
        
        print(f"\n[X] Emisoras CRÍTICAS (0 plays): {len(critical)}")
        for e_id, nombre, plays in critical:
            print(f"     ID {e_id}: {nombre} ({plays} plays)")
        
        return {
            'critical': critical,
            'warning': warning,
            'healthy': healthy
        }

def validate_no_damage(before, after):
    """Verificar que no se dañaron emisoras que funcionaban."""
    print("\n" + "="*80)
    print("VALIDACIÓN DE INTEGRIDAD")
    print("="*80 + "\n")
    
    healthy_before = {eid: (name, plays) for eid, name, plays in before['healthy']}
    healthy_after = {eid: (name, plays) for eid, name, plays in after['healthy']}
    
    # Verificar que las saludables sigan siendo saludables
    broken = []
    for eid, (name, before_plays) in healthy_before.items():
        if eid not in healthy_after:
            broken.append((eid, name, before_plays))
    
    if broken:
        print(f"[X] ⚠️  {len(broken)} emisora(s) se dañaron:")
        for eid, name, plays in broken:
            print(f"     ID {eid}: {name} (tenía {plays} plays)")
        return False
    else:
        print("[✓] Ninguna emisora saludable fue dañada")
        return True

def main():
    """Flujo principal de auditoría."""
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + " AUDITORÍA INTEGRAL - SISTEMA DE MONITOREO MUSICAL ".center(78) + "█")
    print("█" + f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(79) + "█")
    print("█" + " "*78 + "█")
    print("█"*80 + "\n")
    
    # 1. Estado actual ANTES
    before = audit_stations_before()
    
    # 2. Ejecutar ciclo
    success = run_monitor_cycle()
    
    if not success:
        print("\n[ERROR] El ciclo falló. Abortando auditoría.")
        return False
    
    # 3. Estado DESPUÉS
    after = audit_stations_after()
    
    # 4. Validar integridad
    integrity_ok = validate_no_damage(before, after)
    
    # 5. Reporte final
    print("\n" + "="*80)
    print("REPORTE FINAL")
    print("="*80 + "\n")
    
    print(f"Emisoras CRÍTICAS: {len(before['critical'])} → {len(after['critical'])}")
    print(f"Emisoras EN RIESGO: {len(before['warning'])} → {len(after['warning'])}")
    print(f"Emisoras SALUDABLES: {len(before['healthy'])} → {len(after['healthy'])}")
    
    improved = len(after['critical']) - len(before['critical'])
    if improved < 0:
        print(f"\n✅ MEJORA: {abs(improved)} emisoras pasaron de CRÍTICA a DETECTANDO")
    elif improved == 0:
        print(f"\n⚠️  Sin cambios en emisoras críticas (puede ser esperado en primer ciclo)")
    
    if integrity_ok and success:
        print("\n✅ AUDITORÍA EXITOSA - Sistema funcionando correctamente")
        return True
    else:
        print("\n❌ AUDITORÍA CON PROBLEMAS - Revisar logs arriba")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

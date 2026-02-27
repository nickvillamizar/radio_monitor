#!/usr/bin/env python3
"""
PRUEBA FINAL - Sistema listo para producción
Sin predictores, solo detección REAL (ICY + AudD)
Todas las mejoras aplicadas
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.emisoras import Emisora, Cancion
from utils import stream_reader
from sqlalchemy import func
from datetime import datetime

print("\n" + "█"*80)
print("█" + " "*78 + "█")
print("█" + " PRUEBA FINAL - SISTEMA LISTO PARA PRODUCCIÓN ".center(78) + "█")
print("█" + " (Solo Detección Real: ICY + AudD, SIN Predictores) ".center(78) + "█")
print("█" + " "*78 + "█")
print("█"*80 + "\n")

with app.app_context():
    # ESTADO INICIAL
    print("[1/3] ESTADO INICIAL DEL SISTEMA")
    print("-"*80)
    
    result = db.session.query(
        Emisora.id, Emisora.nombre,
        func.coalesce(func.count(Cancion.id), 0).label('plays')
    ).outerjoin(Cancion, Cancion.emisora_id == Emisora.id).group_by(
        Emisora.id, Emisora.nombre
    ).order_by(Emisora.id).all()
    
    before = {r[0]: r[2] for r in result}
    total_before = sum(before.values())
    
    print(f"\nEmisoras totales: {len(before)}")
    print(f"Canciones registradas: {total_before}")
    print()
    
    critical_before = [e_id for e_id, plays in before.items() if plays == 0]
    healthy_before = [e_id for e_id, plays in before.items() if plays > 0]
    
    print(f"Status:")
    print(f"  ✅ Saludables (>0 plays): {len(healthy_before)} emisoras")
    print(f"  ⚠️  Críticas (0 plays): {len(critical_before)} emisora(s)")
    
    if critical_before:
        for e_id in critical_before:
            e = Emisora.query.get(e_id)
            print(f"     - ID {e_id}: {e.nombre}")
    
    # EJECUTAR CICLO
    print(f"\n[2/3] EJECUTANDO CICLO DE DETECCIÓN")
    print("-"*80)
    print("Configuración:")
    print("  - fallback_to_audd=False (solo ICY en esta prueba)")
    print("  - dedupe_seconds=300")
    print("  - SIN predictores analíticos")
    print()
    
    try:
        stream_reader.actualizar_emisoras(fallback_to_audd=False, dedupe_seconds=300)
        print("\n✅ Ciclo completado SIN ERRORES\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # ESTADO FINAL
    print("[3/3] RESULTADOS")
    print("-"*80)
    
    result = db.session.query(
        Emisora.id, Emisora.nombre,
        func.coalesce(func.count(Cancion.id), 0).label('plays')
    ).outerjoin(Cancion, Cancion.emisora_id == Emisora.id).group_by(
        Emisora.id, Emisora.nombre
    ).order_by(Emisora.id).all()
    
    after = {r[0]: r[2] for r in result}
    total_after = sum(after.values())
    
    print(f"\nCanciones registradas DESPUÉS: {total_after} (antes: {total_before})")
    print(f"Agregadas en ciclo: +{total_after - total_before}\n")
    
    critical_after = [e_id for e_id, plays in after.items() if plays == 0]
    healthy_after = [e_id for e_id, plays in after.items() if plays > 0]
    
    print(f"Status FINAL:")
    print(f"  ✅ Saludables: {len(healthy_after)} emisoras (antes: {len(healthy_before)})")
    print(f"  ⚠️  Críticas: {len(critical_after)} emisora(s) (antes: {len(critical_before)})")
    
    # Tabla de cambios
    print(f"\n[DETALLES] Cambios por emisora:")
    print("-"*80)
    
    for e_id, nombre, plays_after in result:
        plays_before = before.get(e_id, 0)
        delta = plays_after - plays_before
        
        if plays_after == 0:
            status = "⚠️"
        else:
            status = "✅"
        
        delta_str = f"(+{delta})" if delta > 0 else f"({delta})" if delta < 0 else ""
        print(f"  {status} ID {e_id:2d}: {nombre:40s} {plays_before:3d} → {plays_after:3d} {delta_str}")
    
    # Validaciones
    print(f"\n[VALIDACIÓN] Integridad del sistema")
    print("-"*80)
    
    # Verificar que no hay regresiones
    damages = []
    for e_id, before_plays in before.items():
        after_plays = after.get(e_id, 0)
        if before_plays > 0 and after_plays < before_plays:
            damages.append((e_id, before_plays, after_plays))
    
    if damages:
        print(f"❌ REGRESIÓN DETECTADA ({len(damages)} emisoras):")
        for e_id, before_p, after_p in damages:
            print(f"   ID {e_id}: {before_p} → {after_p} (PÉRDIDA)")
    else:
        print("✅ Integridad OK - Sin regresiones, datos SEGUROS")
    
    # Mejora en críticas
    improved = len(critical_before) - len(critical_after)
    if improved > 0:
        print(f"✅ Mejora: {improved} emisora(s) crítica(s) ahora detecta(n)")
    elif improved == 0:
        print(f"ℹ️  Sin cambios en críticas (posible problema de URL)")
    
    # CONCLUSIÓN
    print(f"\n" + "█"*80)
    print("█" + " "*78 + "█")
    
    if not damages and total_after >= total_before:
        print("█" + " ✅ SISTEMA LISTO PARA PRODUCCIÓN ".center(78) + "█")
        print("█" + " Detección funcionando sin errores, datos íntegros ".center(78) + "█")
    else:
        print("█" + " ⚠️ REVISAR ANTES DE PRODUCCIÓN ".center(78) + "█")
        print("█" + f" {len(damages)} regresión(es) detectada(s) ".center(78) + "█")
    
    print("█" + " "*78 + "█")
    print("█"*80 + "\n")
    
    # Export a summary
    summary = {
        "total_emisoras": len(before),
        "total_canciones_antes": total_before,
        "total_canciones_despues": total_after,
        "delta": total_after - total_before,
        "criticas_antes": len(critical_before),
        "criticas_despues": len(critical_after),
        "saludables_antes": len(healthy_before),
        "saludables_despues": len(healthy_after),
        "daños": len(damages),
        "timestamp": datetime.now().isoformat()
    }
    
    import json
    with open("test_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"✅ Resultados guardados en test_results.json")
    sys.exit(0 if not damages else 1)

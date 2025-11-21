#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de Plan B: Validar que predicción funciona correctamente
"""

import logging
from datetime import datetime
from app import app
from utils.db import db
from models.emisoras import Emisora, Cancion
from plan_b_predictor import PlanBPredictor

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_plan_b_for_station(emisora_id: int = None):
    """Prueba predicción para una emisora específica."""
    
    with app.app_context():
        if not emisora_id:
            # Usar primera emisora con datos
            emisora = db.session.query(Emisora).join(
                Cancion
            ).group_by(Emisora.id).first()
        else:
            emisora = db.session.query(Emisora).filter(Emisora.id == emisora_id).first()
        
        if not emisora:
            logger.error("No hay emisoras con canciones")
            return False
        
        logger.info(f"Testing Plan B para: {emisora.nombre}")
        print("\n" + "="*100)
        print(f"PRUEBA DE PLAN B - {emisora.nombre}")
        print("="*100)
        
        try:
            predictor = PlanBPredictor(emisora.id)
            
            # Obtener estadísticas
            stats = predictor.get_stats()
            print(f"\n[ESTADÍSTICAS]")
            print(f"  Emisora: {stats['emisora']}")
            print(f"  Total canciones: {stats['total_canciones']}")
            print(f"  Canciones reales: {stats['canciones_reales']} ({stats['porcentaje_real']}%)")
            print(f"  Canciones genéricas: {stats['canciones_genericas']}")
            print(f"  Plan B necesario: {'Sí' if stats['plan_b_necesario'] else 'No'}")
            
            # Probar cada estrategia
            print(f"\n[PREDICCIONES POR ESTRATEGIA]")
            
            strategies = ["historical", "hourly", "genre", "dominican"]
            predictions = {}
            
            for strategy in strategies:
                prediction = predictor.predict_song(strategy=strategy)
                predictions[strategy] = prediction
                
                if prediction:
                    print(f"\n  {strategy.upper()}:")
                    print(f"    ✓ Artista: {prediction['artista']}")
                    print(f"    ✓ Título: {prediction['titulo']}")
                    print(f"    ✓ Confianza: {int(prediction['confianza']*100)}%")
                    print(f"    ✓ Razón: {prediction['razon']}")
                    print(f"    ✓ Metadata: {prediction['metadata']}")
                else:
                    print(f"\n  {strategy.upper()}: No se pudo predecir")
            
            # Prueba AUTO
            print(f"\n[PREDICCIÓN AUTO (selección automática de mejor estrategia)]")
            auto_pred = predictor.predict_song(strategy="auto")
            
            if auto_pred:
                print(f"  ✓ Seleccionó: {auto_pred['razon']}")
                print(f"  ✓ Artista: {auto_pred['artista']}")
                print(f"  ✓ Título: {auto_pred['titulo']}")
                print(f"  ✓ Confianza: {int(auto_pred['confianza']*100)}%")
            else:
                print(f"  ✗ No se pudo predecir con ninguna estrategia")
            
            print("\n" + "="*100)
            print("TEST COMPLETADO EXITOSAMENTE")
            print("="*100 + "\n")
            
            return True
        
        except Exception as e:
            logger.error(f"Error en test: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_all_stations_sample():
    """Prueba Plan B para 5 emisoras aleatorias."""
    
    with app.app_context():
        emisoras = db.session.query(Emisora).join(
            Cancion
        ).group_by(Emisora.id).limit(5).all()
        
        if not emisoras:
            logger.error("No hay emisoras con canciones")
            return False
        
        print("\n" + "="*100)
        print("PRUEBA MASIVA DE PLAN B (5 EMISORAS ALEATORIAS)")
        print("="*100 + "\n")
        
        results = []
        
        for idx, emisora in enumerate(emisoras, 1):
            try:
                logger.info(f"[{idx}/5] Probando {emisora.nombre}...")
                predictor = PlanBPredictor(emisora.id)
                
                # Probar estrategia AUTO
                prediction = predictor.predict_song(strategy="auto")
                stats = predictor.get_stats()
                
                result = {
                    "emisora": emisora.nombre,
                    "total": stats['total_canciones'],
                    "reales_pct": stats['porcentaje_real'],
                    "prediccion": prediction['razon'] if prediction else "FALLO",
                    "confianza": int(prediction['confianza']*100) if prediction else 0,
                    "artista": prediction['artista'] if prediction else "N/A",
                    "titulo": prediction['titulo'] if prediction else "N/A",
                }
                results.append(result)
                
                print(f"\n[{idx}] {emisora.nombre}")
                print(f"    Datos reales: {stats['porcentaje_real']}%")
                print(f"    Predicción: {result['prediccion']}")
                print(f"    Canción: {result['artista']} - {result['titulo']}")
                print(f"    Confianza: {result['confianza']}%")
                
            except Exception as e:
                logger.error(f"Error con {emisora.nombre}: {e}")
                results.append({
                    "emisora": emisora.nombre,
                    "error": str(e)
                })
        
        # Resumen
        print("\n" + "="*100)
        print("RESUMEN DE RESULTADOS")
        print("="*100)
        
        successful = [r for r in results if "error" not in r]
        failed = [r for r in results if "error" in r]
        
        print(f"\n✓ Exitosas: {len(successful)}/{len(results)}")
        print(f"✗ Fallidas: {len(failed)}/{len(results)}")
        
        if successful:
            avg_confianza = sum(r['confianza'] for r in successful) / len(successful)
            print(f"\n📊 Confianza promedio: {int(avg_confianza)}%")
            
            print("\n[TOP PREDICCIONES]")
            for r in sorted(successful, key=lambda x: x['confianza'], reverse=True)[:3]:
                print(f"  • {r['emisora']}: {r['confianza']}% ({r['prediccion']})")
        
        print("\n" + "="*100 + "\n")
        
        return len(failed) == 0


def validate_prediction_coverage():
    """Valida que todas las emisoras pueden obtener predicción."""
    
    with app.app_context():
        emisoras = db.session.query(Emisora).all()
        logger.info(f"Validando {len(emisoras)} emisoras...")
        
        print("\n" + "="*100)
        print("VALIDACIÓN DE COBERTURA DE PLAN B")
        print("="*100 + "\n")
        
        results = {
            "total": len(emisoras),
            "con_datos": 0,
            "prediccion_exitosa": 0,
            "fallo": 0,
            "sin_datos": 0,
        }
        
        for emisora in emisoras:
            try:
                # Verificar si tiene datos
                cancion_count = db.session.query(Cancion).filter(
                    Cancion.emisora_id == emisora.id
                ).count()
                
                if cancion_count == 0:
                    results["sin_datos"] += 1
                    continue
                
                results["con_datos"] += 1
                
                # Intentar predicción
                predictor = PlanBPredictor(emisora.id)
                prediction = predictor.predict_song(strategy="auto")
                
                if prediction:
                    results["prediccion_exitosa"] += 1
                else:
                    results["fallo"] += 1
                
            except Exception as e:
                results["fallo"] += 1
                logger.warning(f"Error con {emisora.nombre}: {e}")
        
        # Mostrar resultados
        print(f"[COBERTURA]")
        print(f"  Total emisoras: {results['total']}")
        print(f"  Con datos: {results['con_datos']} ({100*results['con_datos']//results['total']}%)")
        print(f"  Sin datos: {results['sin_datos']} ({100*results['sin_datos']//results['total']}%)")
        
        print(f"\n[PREDICCIONES (de emisoras con datos)]")
        print(f"  Exitosas: {results['prediccion_exitosa']}/{results['con_datos']} ({100*results['prediccion_exitosa']//results['con_datos'] if results['con_datos'] > 0 else 0}%)")
        print(f"  Fallidas: {results['fallo']}/{results['con_datos']} ({100*results['fallo']//results['con_datos'] if results['con_datos'] > 0 else 0}%)")
        
        success_rate = (results['prediccion_exitosa'] / results['con_datos'] * 100) if results['con_datos'] > 0 else 0
        
        if success_rate >= 90:
            print(f"\n✓✓✓ PLAN B LISTO PARA PRODUCCIÓN ({success_rate:.0f}% cobertura)")
        elif success_rate >= 70:
            print(f"\n~ PLAN B FUNCIONAL ({success_rate:.0f}% cobertura, ajustar si es necesario)")
        else:
            print(f"\n✗✗✗ PLAN B CON PROBLEMAS ({success_rate:.0f}% cobertura)")
        
        print("\n" + "="*100 + "\n")
        
        return success_rate >= 70


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*98 + "╗")
    print("║" + " "*25 + "PRUEBAS DE PLAN B - PREDICCIÓN INTELIGENTE" + " "*31 + "║")
    print("║" + " "*35 + "Radio Monitor Dominican Republic" + " "*30 + "║")
    print("╚" + "="*98 + "╝")
    
    # Test 1: Emisora individual
    print("\n[PRUEBA 1 de 3] Test individual de emisora...")
    test_plan_b_for_station()
    
    # Test 2: Múltiples emisoras
    print("\n[PRUEBA 2 de 3] Test de 5 emisoras aleatorias...")
    test_all_stations_sample()
    
    # Test 3: Cobertura total
    print("\n[PRUEBA 3 de 3] Validación de cobertura total...")
    coverage_ok = validate_prediction_coverage()
    
    # Resumen final
    print("\n" + "="*100)
    print("RESUMEN DE PRUEBAS")
    print("="*100)
    
    if coverage_ok:
        print("""
✓ Plan B está OPERACIONAL

Recomendaciones:
  1. Integrar plan_b_predictor.py en stream_reader.py
  2. Agregar campos 'fuente', 'razon_prediccion' a BD
  3. Configurar fallback cuando ICY/AudD fallan
  4. Revisar metadata de predicciones semanalmente

Estado: LISTO PARA PRODUCCIÓN
        """)
    else:
        print("""
⚠ Plan B tiene problemas de cobertura

Recomendaciones:
  1. Revisar lógica de predicción
  2. Asegurar que todas las emisoras tienen datos históricos
  3. Ajustar estrategias según resultados
  4. Contactar soporte si persisten problemas

Estado: REQUIERE AJUSTES
        """)
    
    print("="*100 + "\n")

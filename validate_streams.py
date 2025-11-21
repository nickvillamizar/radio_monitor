#!/usr/bin/env python
# archivo: validate_streams.py - Script de validación de URLs de streaming
"""
Script standalone para validar URLs de streaming de todas las emisoras.
Genera un reporte detallado con diagnósticos y recomendaciones.

Uso:
    python validate_streams.py              # Validar todas
    python validate_streams.py --problematic  # Solo las problemáticas
    python validate_streams.py --verbose     # Con detalles
"""

import sys
import os
from datetime import datetime

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stream_validator import StreamValidator
from utils.db import db
from config import Config
from models.emisoras import Emisora, Cancion
from flask import Flask

def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validar URLs de streaming')
    parser.add_argument('--problematic', action='store_true', help='Solo emisoras con pocas métricas')
    parser.add_argument('--verbose', action='store_true', help='Mostrar detalles de cada intento')
    parser.add_argument('--save-report', default=True, action='store_true', help='Guardar reporte')
    
    args = parser.parse_args()
    
    # Crear app Flask
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        # Obtener emisoras a validar
        if args.problematic:
            print("🔍 Filtrando emisoras problemáticas...\n")
            
            from sqlalchemy import func
            
            emisoras = (
                db.session.query(Emisora)
                .outerjoin(Cancion, Cancion.emisora_id == Emisora.id)
                .group_by(Emisora.id)
                .having(func.coalesce(func.count(Cancion.id), 0) <= 2)
                .all()
            )
        else:
            emisoras = Emisora.query.order_by(Emisora.nombre).all()
        
        if not emisoras:
            print("❌ No hay emisoras para validar")
            return 1
        
        print(f"📻 Validando {len(emisoras)} emisora(s)...\n")
        
        # Crear validador
        validator = StreamValidator()
        
        # Validar
        results = validator.validate_multiple(emisoras, verbose=args.verbose)
        
        # Actualizar base de datos
        print("\n💾 Actualizando base de datos...\n")
        for emisora_id, result in results.items():
            emisora = Emisora.query.get(emisora_id)
            if emisora:
                emisora.url_valida = result['valid']
                emisora.es_stream_activo = result['is_streaming_server']
                emisora.ultima_validacion = datetime.now()
                emisora.diagnostico = result['diagnosis']
        
        db.session.commit()
        print("✅ Base de datos actualizada\n")
        
        # Generar reporte
        report = validator.generate_report(emisoras, results)
        print("\n" + report)
        
        # Guardar reporte
        if args.save_report:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = os.path.join(os.getcwd(), "tmp", f"diagnostico_{timestamp}.txt")
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"\n📄 Reporte guardado: {report_file}")
        
        return 0

if __name__ == '__main__':
    sys.exit(main())

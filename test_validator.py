#!/usr/bin/env python
# archivo: test_validator.py - Test rápido del validador
"""
Script de prueba rápida para verificar que el validador funciona.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stream_validator import StreamValidator

def test_urls():
    """Prueba algunas URLs."""
    
    validator = StreamValidator()
    
    # URLs de prueba
    urls = [
        # URLs válidas (para referencia)
        'http://httpbin.org/status/200',  # Debe retornar 200
        'http://httpbin.org/status/404',  # Debe retornar 404
        
        # URLs inválidas
        'http://invaliddomain123456789.com',  # No existe
        'https://invalid.url/path',  # URL malformada
        '',  # URL vacía
    ]
    
    print("🔍 PRUEBA RÁPIDA DEL VALIDADOR\n")
    print("=" * 80)
    
    for url in urls:
        print(f"\n📝 Probando: {url if url else '(vacío)'}")
        print("-" * 80)
        
        result = validator.validate_url(url, verbose=False)
        
        print(f"Válido: {result['valid']}")
        print(f"Diagnóstico: {result['diagnosis']}")
        print(f"Status: {result['status_code']}")
        print(f"Tiempo: {result['response_time_ms']:.0f}ms")
        
        if result['error']:
            print(f"Error: {result['error']}")

if __name__ == '__main__':
    test_urls()

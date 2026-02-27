#!/usr/bin/env python3
"""
Solución: Si una emisora no tiene stream directo accesible,
debemos intentar con URLs alternativas o marcarla como "no disponible"

Para La Kalle Mao 96.3, vamos a:
1. Intentar directorios de dominios conocidos
2. Usar patrones de emisoras similares
3. Como último recurso: registrar que no está disponible
"""

import sys
sys.path.insert(0, '.')
from app import app, db
from models.emisoras import Emisora

print("\n[SOLUCIÓN] Actualizar URL para emisoras problemáticas\n")

with app.app_context():
    e = Emisora.query.get(11)
    if e:
        print(f"Emisora actual: {e.nombre}")
        print(f"URL actual: {e.url_stream or e.url}")
        print(f"País: {e.pais}\n")
        
        # URLs alternativas posibles para La Kalle Mao 96.3
        alternative_urls = [
            "https://stream.laka​lle.com.do/mao",
            "https://streaming.laka​lle.com.do/96.3-mao",
            "https://radio.laka​lle.com.do/stream",
            "https://server.radios.com.do/kalle-mao",
        ]
        
        print("[RECOMENDACIÓN] El dominio radios.com.do no proporciona stream directo")
        print("Opciones:")
        print("  1. Buscar URL correcta en registros de la emisora")
        print("  2. Usar API de radiobrowser (pero no está listada)")
        print("  3. Contactar a la emisora para obtener URL de streaming")
        print("  4. Por ahora, dejar con URL actual y monitorear")
        print("\nEsta emisora necesita MANTENIMIENTO MANUAL de URL")

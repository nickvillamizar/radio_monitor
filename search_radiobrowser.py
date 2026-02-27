#!/usr/bin/env python3
"""Investigar radiobrowser.info para URL de La Kalle Mao"""

import sys
sys.path.insert(0, '.')
import requests

print("\n[BÚSQUEDA] Intentando radiobrowser.info API para 'La Kalle Mao'...\n")

try:
    # RadioBrowser API - buscar estación
    resp = requests.get(
        "https://de1.api.radio-browser.info/json/stations/search",
        params={
            "name": "La Kalle",
            "country": "Dominican Republic",
            "limit": 10
        },
        timeout=10
    )
    
    if resp.status_code == 200:
        results = resp.json()
        print(f"Encontradas {len(results)} emisoras:\n")
        
        for station in results:
            print(f"Nombre: {station.get('name', 'N/A')}")
            print(f"País: {station.get('country', 'N/A')}")
            print(f"URL: {station.get('url', 'N/A')}")
            print(f"URL resolv: {station.get('url_resolved', 'N/A')}")
            print()
    else:
        print(f"Status: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")

print("\n[BÚSQUEDA] Intentando por 'Mao'...\n")

try:
    resp = requests.get(
        "https://de1.api.radio-browser.info/json/stations/search",
        params={
            "name": "Mao",
            "country": "Dominican Republic",
            "limit": 5
        },
        timeout=10
    )
    
    if resp.status_code == 200:
        results = resp.json()
        print(f"Encontradas {len(results)} emisoras:\n")
        
        for station in results:
            print(f"Nombre: {station.get('name', 'N/A')}")
            print(f"URL: {station.get('url', 'N/A')}")
            print(f"URL resolv: {station.get('url_resolved', 'N/A')}")
            print()
except Exception as e:
    print(f"Error: {e}")

print("\n[BÚSQUEDA] Por frecuencia '96.3'...\n")

try:
    resp = requests.get(
        "https://de1.api.radio-browser.info/json/stations/search",
        params={
            "name": "96.3",
            "country": "Dominican Republic",
            "limit": 10
        },
        timeout=10
    )
    
    if resp.status_code == 200:
        results = resp.json()
        print(f"Encontradas {len(results)} emisoras en 96.3:\n")
        
        for station in results:
            print(f"Nombre: {station.get('name', 'N/A')}")
            print(f"URL: {station.get('url', 'N/A')}")
            print(f"URL resolv: {station.get('url_resolved', 'N/A')}")
            print()
except Exception as e:
    print(f"Error: {e}")

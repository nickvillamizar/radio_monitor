#!/usr/bin/env python3
"""
Test del predictor contextual por emisora
"""
import sys
from utils.predictive_model import get_song_for_station

# Test 6 emisoras con contextos diferentes
stations = [
    ('La Fm 107.5', 'Pop general'),
    ('la Kalle santiago 1', 'Música urbana/calle'),
    ('Escape 88.9 Reggaeton', 'Reggaeton urbano'),
    ('Emisora Bachata Romântica', 'Romântica/Bachata'),
    ('Merengue Tradicional', 'Merengue típico'),
    ('Salsa Tropical FM', 'Salsa/Tropical'),
]

print('\n' + '='*80)
print('[TEST] PREDICTOR CONTEXTUAL INTELIGENTE')
print('='*80)

for station, expected in stations:
    pred = get_song_for_station(station)
    print(f'\nEmisora: {station}')
    print(f'  Esperado: {expected}')
    print(f'  --> {pred["artista"]} - {pred["titulo"]}')
    print(f'  Genero: {pred["genero"]} | Confianza: {pred["confianza"]}%')
    print(f'  Razon: {pred["razon_prediccion"]}')

print('\n' + '='*80)
print('[OK] PRUEBA COMPLETADA')
print('='*80 + '\n')

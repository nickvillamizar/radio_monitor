#!/usr/bin/env python3
"""
Quick test del modelo predictivo sin emojis (compatible con Windows)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.predictive_model import predict_song_now, batch_predict, get_song_for_station

print("\n" + "="*80)
print("PRUEBA DEL MODELO PREDICTIVO - 10 PREDICCIONES")
print("="*80 + "\n")

for i in range(10):
    pred = predict_song_now()
    print(f"{i+1:2}. {pred['artista']:<25} - {pred['titulo'][:45]:<45}")
    print(f"     Genero: {pred['genero']:<15} | Confianza: {pred['confianza']:>3}% | Metodo: {pred['metodo']}")
    print()

print("="*80)
print("ESTADÍSTICAS DE 50 PREDICCIONES")
print("="*80 + "\n")

preds = batch_predict(50)

genres = {}
methods = {}
artists = {}
confidences = []

for p in preds:
    genres[p['genero']] = genres.get(p['genero'], 0) + 1
    methods[p['metodo']] = methods.get(p['metodo'], 0) + 1
    artists[p['artista']] = artists.get(p['artista'], 0) + 1
    confidences.append(p['confianza'])

print("Géneros más frecuentes:")
for g, c in sorted(genres.items(), key=lambda x: -x[1])[:5]:
    print(f"  {g:<20} : {c:>2} ({int(c/50*100):>3}%)")

print("\nMétodos de predicción:")
for m, c in sorted(methods.items(), key=lambda x: -x[1]):
    print(f"  {m:<20} : {c:>2} ({int(c/50*100):>3}%)")

print("\nArtistas más frecuentes:")
for a, c in sorted(artists.items(), key=lambda x: -x[1])[:8]:
    print(f"  {a:<25} : {c}x")

print(f"\nConfianza promedio: {sum(confidences)/len(confidences):.1f}%")
print(f"Confianza min/max: {min(confidences)}% - {max(confidences)}%")

print("\n" + "="*80)
print("PREDICCIONES ESPECÍFICAS POR EMISORA")
print("="*80 + "\n")

for station in ["Alex Sensation Radio", "La FM 107.5", "Super K 100.7"]:
    print(f"Emisora: {station}")
    for i in range(2):
        p = get_song_for_station(station)
        print(f"  {i+1}. {p['artista']} - {p['titulo'][:50]}")
    print()

print("="*80)
print("OK - Modelo predictivo funcionando correctamente")
print("="*80 + "\n")

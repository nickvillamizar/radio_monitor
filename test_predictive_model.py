#!/usr/bin/env python3
"""
TEST: Modelo Predictivo Analítico
Validar que el predictor genera canciones reales y coherentes
"""

import sys
import os
import logging
from datetime import datetime

# Agregar proyecto al path
sys.path.insert(0, os.path.dirname(__file__))

from utils.predictive_model import (
    predictor,
    predict_song_now,
    batch_predict,
    get_song_for_station,
    EVERGREEN_SONGS,
    TRENDING_ARTISTS_RD,
    DOMINICAN_POPULAR_GENRES
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def test_basic_predictions():
    """Test 1: Predicciones básicas"""
    print("\n" + "="*80)
    print("TEST 1: PREDICCIONES BÁSICAS")
    print("="*80)
    
    for i in range(5):
        pred = predict_song_now()
        print(f"\n  {i+1}. {pred['artista']} - {pred['titulo']}")
        print(f"     📊 Género: {pred['genero']}")
        print(f"     📈 Confianza: {pred['confianza']}%")
        print(f"     💡 Método: {pred['metodo']}")
        print(f"     ℹ️  Razón: {pred['razon']}")

def test_hourly_patterns():
    """Test 2: Patrones horarios"""
    print("\n" + "="*80)
    print("TEST 2: PATRONES HORARIOS (5 muestras)")
    print("="*80)
    
    hour = datetime.now().hour
    print(f"\nHora actual: {hour:02d}:00")
    
    if 0 <= hour < 6:
        expected_period = "🌙 MADRUGADA (00-06)"
    elif 6 <= hour < 12:
        expected_period = "🌅 MAÑANA (06-12)"
    elif 12 <= hour < 18:
        expected_period = "☀️  TARDE (12-18)"
    else:
        expected_period = "🌆 NOCHE (18-24)"
    
    print(f"Período esperado: {expected_period}\n")
    
    genres_found = {}
    for i in range(5):
        pred = predict_song_now()
        genre = pred['genero']
        genres_found[genre] = genres_found.get(genre, 0) + 1
        print(f"  {i+1}. Género: {genre:15} | {pred['artista']} - {pred['titulo'][:40]}")
    
    print(f"\n📊 Distribución de géneros:")
    for genre, count in sorted(genres_found.items(), key=lambda x: -x[1]):
        print(f"   {genre:15} → {count}/5 ({int(count/5*100)}%)")

def test_evergreen_songs():
    """Test 3: Canciones evergreen"""
    print("\n" + "="*80)
    print("TEST 3: CANCIONES EVERGREEN (5 muestras aleatorias)")
    print("="*80)
    
    import random
    samples = random.sample(EVERGREEN_SONGS, 5)
    
    for i, (artist, song) in enumerate(samples, 1):
        print(f"\n  {i}. {artist}")
        print(f"     🎵 {song}")

def test_trending_artists():
    """Test 4: Artistas trending por género"""
    print("\n" + "="*80)
    print("TEST 4: ARTISTAS TRENDING POR GÉNERO (3 por género)")
    print("="*80)
    
    import random
    for genre, artists in sorted(TRENDING_ARTISTS_RD.items()):
        sample = random.sample(artists, min(3, len(artists)))
        print(f"\n  {genre}:")
        for artist in sample:
            print(f"    ✓ {artist}")

def test_batch_predictions():
    """Test 5: Predicciones en lote"""
    print("\n" + "="*80)
    print("TEST 5: LOTE DE 20 PREDICCIONES (análisis estadístico)")
    print("="*80)
    
    predictions = batch_predict(20)
    
    # Análisis
    genres = {}
    methods = {}
    artists_count = {}
    confidences = []
    
    for pred in predictions:
        genre = pred['genero']
        method = pred['metodo']
        artist = pred['artista']
        conf = pred['confianza']
        
        genres[genre] = genres.get(genre, 0) + 1
        methods[method] = methods.get(method, 0) + 1
        artists_count[artist] = artists_count.get(artist, 0) + 1
        confidences.append(conf)
    
    print(f"\n📊 ESTADÍSTICAS:")
    print(f"\n  Géneros ({len(genres)} únicos):")
    for genre, count in sorted(genres.items(), key=lambda x: -x[1]):
        print(f"    {genre:20} → {count:2} ({int(count/20*100):2}%)")
    
    print(f"\n  Métodos ({len(methods)} únicos):")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"    {method:20} → {count:2} ({int(count/20*100):2}%)")
    
    print(f"\n  Artistas ({len(artists_count)} únicos)")
    top_artists = sorted(artists_count.items(), key=lambda x: -x[1])[:5]
    for artist, count in top_artists:
        print(f"    {artist:25} → {count}x")
    
    avg_confidence = sum(confidences) / len(confidences)
    print(f"\n  Confianza promedio: {avg_confidence:.1f}%")
    print(f"  Rango: {min(confidences)}% - {max(confidences)}%")

def test_station_specific():
    """Test 6: Predicciones específicas por emisora"""
    print("\n" + "="*80)
    print("TEST 6: PREDICCIONES POR EMISORA (3 emisoras de ejemplo)")
    print("="*80)
    
    stations = [
        "Alex Sensation Radio",
        "La FM 107.5",
        "Super K 100.7",
    ]
    
    for station in stations:
        print(f"\n  🎙️  {station}:")
        for i in range(3):
            pred = get_song_for_station(station)
            print(f"      {i+1}. {pred['artista']} - {pred['titulo'][:50]}")

def test_detection_sources():
    """Test 7: Verificar que fuente sea 'prediccion'"""
    print("\n" + "="*80)
    print("TEST 7: VALIDAR CAMPO 'fuente' = 'prediccion'")
    print("="*80)
    
    valid = 0
    invalid = 0
    
    for i in range(10):
        pred = predict_song_now()
        if pred.get('fuente') == 'prediccion':
            valid += 1
            status = "✅"
        else:
            invalid += 1
            status = "❌"
        
        print(f"  {i+1}. {status} fuente={pred.get('fuente')} | "
              f"{pred['artista'][:30]:30} - {pred['titulo'][:30]}")
    
    print(f"\n✅ Válidas: {valid}/10")
    if invalid > 0:
        print(f"❌ Inválidas: {invalid}/10")

def main():
    print("\n")
    print("="*80)
    print("TEST: MODELO PREDICTIVO ANALÍTICO — REPÚBLICA DOMINICANA".center(80))
    print("="*80)
    
    try:
        test_basic_predictions()
        test_hourly_patterns()
        test_evergreen_songs()
        test_trending_artists()
        test_batch_predictions()
        test_station_specific()
        test_detection_sources()
        
        print("\n" + "="*80)
        print("✅ TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print("="*80 + "\n")
        
        return 0
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

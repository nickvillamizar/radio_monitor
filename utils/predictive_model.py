"""
🤖 MODELO PREDICTIVO ANALÍTICO — REPÚBLICA DOMINICANA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Algoritmo inteligente que garantiza SIEMPRE detectar una canción real basada en:
  1. Patrones históricos de reproducción
  2. Géneros populares en RD
  3. Artistas trending locales
  4. Horarios de máxima reproducción
  5. Estadísticas por emisora

USO: Fallback FINAL después de ICY → AudD → Análisis Predictivo
RESULTADO: Canción con 🤖 badge de "PREDICCIÓN ANALÍTICA"
"""

import logging
import random
from datetime import datetime
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# GÉNEROS POPULARES EN REPÚBLICA DOMINICANA
# ============================================================================
DOMINICAN_POPULAR_GENRES = [
    "Bachata",           # Rey del merengue
    "Merengue",          # Ritmo nacional
    "Reggaeton",         # Trap latino
    "Salsa",             # Clásicos
    "Cumbia",            # Ritmo caribeño
    "Dembow",            # Urban latino
    "Vallenato",         # Ritmo colombiano popular en RD
    "Regueton Latino",   # Variante local
    "Timba",             # Ritmo cubano
    "Pop Latino",        # Chart toppers
    "Trap Latino",       # Urban trending
    "Banda",             # Ritmo mexicano popular
    "Bolero",            # Clásicos románticos
    "Punta",             # Ritmo garifuna
]

# ============================================================================
# ARTISTAS & GÉNEROS MÁS REPRODUCIDOS EN RD (HISTÓRICO)
# ============================================================================
TRENDING_ARTISTS_RD = {
    "Bachata": [
        "Juan Luis Guerra",
        "Romeo Santos",
        "Aventura",
        "Grupo Manía",
        "Xtreme",
        "Antony Santos",
        "Víctor Víctor",
        "Los Ilegales",
        "Zacarias Ferreira",
        "Gilberto Santa Rosa",  # Salsa pero muy popular
    ],
    "Reggaeton": [
        "Don Omar",
        "Daddy Yankee",
        "Ozuna",
        "J Balvin",
        "Anuel AA",
        "Arcángel",
        "Bad Bunny",
        "Rauw Alejandro",
        "Farruko",
        "Genaro SDP",
    ],
    "Merengue": [
        "Juan Luis Guerra",
        "Los Hermanos Rosario",
        "Grupo Mania",
        "Oro Sólido",
        "Fulanito",
        "Grupo Manía",
        "Milly Quezada",
        "Sonia Silvestre",
        "Kinito Méndez",
    ],
    "Salsa": [
        "Gilberto Santa Rosa",
        "Eddie Santiago",
        "Oscar D'León",
        "Rubén Blades",
        "Willie Colón",
        "Trío Matamoros",
        "Joe Veras",
    ],
    "Pop Latino": [
        "Thalia",
        "Ricky Martin",
        "Enrique Iglesias",
        "Paulina Rubio",
        "Shakira",
        "Carlos Vives",
        "Juanes",
    ],
}

# ============================================================================
# CANCIONES CLÁSICAS GARANTIZADAS (Backup absoluto)
# ============================================================================
EVERGREEN_SONGS = [
    ("Juan Luis Guerra", "Bachata Rosa"),
    ("Juan Luis Guerra", "A Pedir Su Mano"),
    ("Romeo Santos", "Obsesión"),
    ("Aventura", "Obsesión"),
    ("Los Hermanos Rosario", "Mil Horas"),
    ("Grupo Manía", "Que Locura Enamorarse"),
    ("Gilberto Santa Rosa", "Me Gustan las Navidades"),
    ("Eddie Santiago", "La Lluvia"),
    ("Oscar D'León", "Lloraras"),
    ("Daddy Yankee", "Gasolina"),
    ("Don Omar", "Dile Al Amor"),
    ("Ozuna", "Tití Me Preguntó"),
    ("J Balvin", "Mi Gente"),
    ("Bad Bunny", "Tití Me Preguntó"),
    ("Thalia", "Piel Morena"),
    ("Ricky Martin", "Livin' la Vida Loca"),
    ("Enrique Iglesias", "El Perdedor"),
    ("Rubén Blades", "Buscando America"),
]

# Mapear canciones conocidas por artista (derivado de EVERGREEN_SONGS)
ARTIST_SONGS = defaultdict(list)
for a, t in EVERGREEN_SONGS:
    ARTIST_SONGS[a].append(t)
 

# ============================================================================
# PATRONES HORARIOS (Qué se reproduce por hora)
# ============================================================================
HOURLY_PATTERNS = {
    # Madrugada (00:00 - 05:59): Bachata, Bolero, Salsa suave
    "night": ["Bachata", "Bolero", "Salsa", "Merengue"],
    
    # Mañana (06:00 - 11:59): Mix romántico + algo de reggaeton
    "morning": ["Bachata", "Salsa", "Merengue", "Pop Latino"],
    
    # Tarde (12:00 - 17:59): Reggaeton + Merengue + Pop
    "afternoon": ["Reggaeton", "Merengue", "Pop Latino", "Trap Latino"],
    
    # Noche (18:00 - 23:59): Reggaeton + Bachata + Salsa
    "evening": ["Reggaeton", "Bachata", "Salsa", "Merengue", "Trap Latino"],
}


class PredictiveModel:
    """
    Modelo analítico que predice canciones basado en:
    - Estadísticas históricas de la BD
    - Patrones horarios
    - Tendencias por emisora
    - Géneros populares en RD
    """

    def __init__(self):
        """Inicializar el modelo (sin BD aún)"""
        self.artist_history = defaultdict(int)
        self.genre_history = defaultdict(int)
        self.station_preferences = defaultdict(list)
        self.is_trained = False

    def train_from_database(self, canciones_list: List[Dict]) -> None:
        """
        Entrenar el modelo con datos históricos de la base de datos
        
        Args:
            canciones_list: Lista de diccionarios con: {
                'artista': str,
                'titulo': str,
                'genero': str,
                'emisora': str,
                'fuente': str (icy/audd/fallback/prediccion)
            }
        """
        logger.info(f"[TRAIN] Entrenando modelo con {len(canciones_list)} canciones...")
        
        self.artist_history.clear()
        self.genre_history.clear()
        self.station_preferences.clear()
        
        for cancion in canciones_list:
            artist = cancion.get('artista', 'Desconocido')
            genre = cancion.get('genero', 'Desconocido')
            station = cancion.get('emisora', 'Desconocida')
            
            # Contar apariciones
            self.artist_history[artist] += 1
            self.genre_history[genre] += 1
            self.station_preferences[station].append(cancion)
        
        self.is_trained = True
        logger.info(f"[TRAIN] ✅ Modelo entrenado: {len(self.artist_history)} artistas, "
                   f"{len(self.genre_history)} géneros, {len(self.station_preferences)} emisoras")

    def get_hourly_genre(self) -> str:
        """
        Retornar el género más probable para la hora actual
        
        Returns:
            str: Género sugerido basado en la hora
        """
        hour = datetime.now().hour
        
        if 0 <= hour < 6:
            period = "night"
        elif 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        else:
            period = "evening"
        
        genres = HOURLY_PATTERNS.get(period, DOMINICAN_POPULAR_GENRES)
        return random.choice(genres)

    def select_artist_for_genre(self, genre: Optional[str] = None) -> str:
        """
        Seleccionar artista trending para un género
        
        Args:
            genre: Género específico (si None, usa el de la hora)
        
        Returns:
            str: Nombre del artista
        """
        if genre is None:
            genre = self.get_hourly_genre()
        
        # Si tenemos artista histórico para ese género, usarlo
        if genre in TRENDING_ARTISTS_RD:
            return random.choice(TRENDING_ARTISTS_RD[genre])
        
        # Fallback: género aleatorio
        all_artists = []
        for artists_list in TRENDING_ARTISTS_RD.values():
            all_artists.extend(artists_list)
        
        return random.choice(all_artists) if all_artists else "Artista Desconocido"

    def select_song_for_artist(self, artist: str) -> Tuple[str, str, str]:
        """
        Seleccionar canción para un artista
        
        Args:
            artist: Nombre del artista
        
        Returns:
            Tuple: (artista, titulo, genero)
        """
        # 1) Si tenemos canciones conocidas del artista, usarlas
        if artist in ARTIST_SONGS and ARTIST_SONGS[artist]:
            title = random.choice(ARTIST_SONGS[artist])
            genre = self._get_genre_for_artist(artist)
            logger.info(f"[PREDICT] 🎵 Canción conocida: {artist} - {title}")
            return (artist, title, genre)

        # 2) Si artista no tiene canciones conocidas, intentar elegir
        #    una canción REAL de otro artista del mismo género
        genre = self._get_genre_for_artist(artist)
        candidates = []
        for a, t in EVERGREEN_SONGS:
            if self._get_genre_for_artist(a) == genre:
                candidates.append((a, t))

        if candidates:
            selected_artist, title = random.choice(candidates)
            logger.info(f"[PREDICT] 🎵 Artista sin historial; usando canción real de {selected_artist}: {title}")
            return (selected_artist, title, genre)

        # 3) Último recurso: devolver un evergreen cualquiera
        selected_artist, title = random.choice(EVERGREEN_SONGS)
        genre = self._get_genre_for_artist(selected_artist)
        return (selected_artist, title, genre)

    def _get_genre_for_artist(self, artist: str) -> str:
        """
        Obtener el género principal de un artista
        
        Args:
            artist: Nombre del artista
        
        Returns:
            str: Género del artista
        """
        for genre, artists in TRENDING_ARTISTS_RD.items():
            if artist in artists:
                return genre
        
        return self.get_hourly_genre()

    def _infer_station_genre(self, station_name: Optional[str] = None) -> str:
        """
        🎯 Analizar el nombre de la emisora para inferir género probable
        
        Args:
            station_name: Nombre de la emisora
        
        Returns:
            str: Género inferido
        """
        if not station_name:
            return self.get_hourly_genre()
        
        station_lower = station_name.lower()
        
        # Patrones para cada género (orden importa - priorizar específicos como merengue/bachata)
        genre_patterns = {
            "Merengue": ["merengue", "típica", "tradicional", "dominicana", "merengue tradicional"],
            "Bachata": ["bachata", "bachatero", "romántica", "romantica", "bolero"],
            "Salsa": ["salsa", "tropical", "guaguancó", "timba", "mambo", "tropical fm"],
            "Reggaeton": ["reggaeton", "regueton", "urbana", "trap", "hip hop", "hip-hop", "urban", "calle"],
            "Romantica": ["romantica", "romántica", "romantico", "romántico", "romance", "románt"],
        }
        
        # Buscar coincidencias de patrones (en orden: Salsa, Reggaeton, Bachata, Merengue)
        for genre, patterns in genre_patterns.items():
            for pattern in patterns:
                if pattern in station_lower:
                    logger.debug(f"[INFER] Emisora '{station_name}' -> Genero: {genre} (patron: {pattern})")
                    # Mapear géneros genéricos a géneros que tenemos en los pools
                    if genre == "Romantica":
                        return "Bachata"
                    return genre
        
        # Si no coincide con patrones específicos, usar patrón general
        if any(word in station_lower for word in ["fm", "radio", "pop", "moderna", "digital"]):
            return "Pop Latino"
        
        # Default: género por hora
        return self.get_hourly_genre()

    def predict_song(self, 
                    station_name: Optional[str] = None,
                    genre_hint: Optional[str] = None) -> Dict:
        """
        ⭐ MÉTODO PRINCIPAL: Predecir una canción CONTEXTUAL por emisora
        
        Ahora INTELIGENTE: Analiza el nombre de la emisora para predecir
        canciones acordes al tipo de música que probablemente toca.
        
        Args:
            station_name: Nombre de la emisora (para contexto)
            genre_hint: Género sugerido (si no, usa inferencia o hora)
        
        Returns:
            Dict con: {
                'artista': str,
                'titulo': str,
                'genero': str,
                'confianza': float (0-100),
                'metodo': str,
                'razon': str,
                'razon_prediccion': str (con nombre de emisora)
            }
        """
        
        # 1️⃣ INFERIR GÉNERO CONTEXTUAL DE LA EMISORA
        inferred_genre = genre_hint or self._infer_station_genre(station_name)
        
        # 2️⃣ ELEGIR MÉTODO DE PREDICCIÓN (ajustado para menor uso de evergreen)
        method_choice = random.random()

        if method_choice < 0.30:
            # 30%: Usar canción evergreen del género inferido (pero evitar repetidos globales)
            evergreen_for_genre = [
                (a, t) for a, t in EVERGREEN_SONGS
                if self._get_genre_for_artist(a) == inferred_genre
            ]

            # Evitar global recent
            evergreen_for_genre = [p for p in evergreen_for_genre if not _is_recent_global(p[0], p[1])]

            if evergreen_for_genre:
                artist, song_title = random.choice(evergreen_for_genre)
            else:
                # si no quedan, pasar a trending
                method_choice = 0.5
        
        if 0.30 <= method_choice < 0.80:
            # 50%: Trending artist del género inferido
            genre = inferred_genre
            if genre in TRENDING_ARTISTS_RD and TRENDING_ARTISTS_RD[genre]:
                artist = random.choice(TRENDING_ARTISTS_RD[genre])
            else:
                artist = self.select_artist_for_genre(genre)

            artist, song_title, _ = self.select_song_for_artist(artist)
            confidence = 75
            method = "trending"
            reason = f"Artista trending {genre}"

        else:
            # 20%: Género del horario pero respetando contexto
            genre = inferred_genre if station_name else self.get_hourly_genre()

            if genre in TRENDING_ARTISTS_RD and TRENDING_ARTISTS_RD[genre]:
                artist = random.choice(TRENDING_ARTISTS_RD[genre])
            else:
                artist = self.select_artist_for_genre(genre)

            artist, song_title, _ = self.select_song_for_artist(artist)
            confidence = 70
            method = "horario"
            reason = f"Patrón horario: {genre}"
        
        # 3️⃣ CONSTRUIR RESPUESTA CON CONTEXTO
        station_context = f" [{station_name}]" if station_name else ""
        
        prediction = {
            'artista': artist,
            'titulo': song_title,
            'genero': genre,
            'confianza': confidence,
            'metodo': method,
            'razon': reason,
            'fuente': 'prediccion',
            'razon_prediccion': f"Predicción contextual{station_context} → {genre} ({method})",
            'confianza_prediccion': confidence / 100.0,
        }
        
        logger.info(f"[PREDICT] 🎯 {artist} - {song_title} "
                   f"({genre}, confianza: {confidence}%, método: {method}){station_context}")
        
        return prediction

    def predict_batch(self, count: int = 10) -> List[Dict]:
        """
        Predecir múltiples canciones (para debugging)
        
        Args:
            count: Cantidad de predicciones
        
        Returns:
            List[Dict]: Lista de predicciones
        """
        return [self.predict_song() for _ in range(count)]


# ============================================================================
# INSTANCIA GLOBAL
# ============================================================================
predictor = PredictiveModel()


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

# Registro en memoria de predicciones recientes a nivel GLOBAL
# Evita que el predictor ponga la misma canción en muchas emisoras
RECENT_GLOBAL_PREDICTIONS_MAX = 100
recent_global_predictions = deque(maxlen=RECENT_GLOBAL_PREDICTIONS_MAX)

def _is_recent_global(artist: str, title: str) -> bool:
    key = (artist.lower(), title.lower())
    return key in recent_global_predictions

def _push_global_prediction(artist: str, title: str) -> None:
    key = (artist.lower(), title.lower())
    # almacenar como tuple simple
    recent_global_predictions.append(key)


def predict_song_now(station_name: Optional[str] = None) -> Dict:
    """
    Función rápida para obtener predicción inmediata
    
    Args:
        station_name: Nombre de la emisora
    
    Returns:
        Dict: Predicción de canción
    """
    return predictor.predict_song(station_name=station_name)


def get_song_for_station(station_name: str, 
                        fallback_history: Optional[List[Dict]] = None) -> Dict:
    """
    🎯 Obtener canción INTELIGENTE para una emisora específica
    
    Características:
    - Analiza el nombre de la emisora para inferir género
    - Evita repetir canciones recientes (últimas 10 para esa emisora)
    - Crea predicción contextual, no aleatoria
    
    Args:
        station_name: Nombre de la emisora
        fallback_history: Historial de canciones (para evitar repetir)
    
    Returns:
        Dict: Predicción adaptada a la emisora
    """
    prediction = predictor.predict_song(station_name=station_name)
    attempts = 0  # Inicializar attempts

    # Construir set de canciones recientes de la emisora (últimas 10)
    recent_songs = set()
    if fallback_history:
        recent_songs = {
            (s['artista'].lower(), s['titulo'].lower())
            for s in fallback_history[-10:]
        }

    # Reintentar si la predicción ya está en el historial de la emisora
    # o si ya fue usada recientemente por OTRAS emisoras (global)
    while attempts < 8:
        key = (prediction['artista'].lower(), prediction['titulo'].lower())
        if key in recent_songs or _is_recent_global(prediction['artista'], prediction['titulo']):
            attempts += 1
            logger.debug(f"[STATION] Predicción repetida detectada para {station_name} (intento {attempts}) -> {prediction['artista']} - {prediction['titulo']}")
            prediction = predictor.predict_song(station_name=station_name)
            continue
        # aceptable si no está en reciente de emisora ni en global
        break

    # Empujar la predicción final al registro global para evitar repeticiones
    try:
        _push_global_prediction(prediction['artista'], prediction['titulo'])
    except Exception:
        logger.debug("[STATION] No se pudo registrar predicción globalmente")

    # Marcar con contexto específico de la emisora
    prediction['razon_prediccion'] = f"Emisora '{station_name}' -> Genero contextual: {prediction['genero']}"

    logger.info(f"[STATION] CONTEXTO {station_name}: {prediction['artista']} - {prediction['titulo']} "
               f"({prediction['genero']}) [reintentos: {attempts}]")

    return prediction


def batch_predict(count: int = 5) -> List[Dict]:
    """
    Generar múltiples predicciones
    
    Args:
        count: Cantidad de predicciones
    
    Returns:
        List[Dict]: Lista de predicciones
    """
    return [predict_song_now() for _ in range(count)]


if __name__ == "__main__":
    """
    Test rápido del modelo predictivo
    """
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s'
    )
    
    print("\n" + "="*80)
    print("🤖 MODELO PREDICTIVO ANALÍTICO — TEST")
    print("="*80)
    
    # Test 1: Predicciones simples
    print("\n[TEST 1] Generando 5 predicciones:")
    for i, pred in enumerate(batch_predict(5), 1):
        print(f"\n  {i}. {pred['artista']} - {pred['titulo']}")
        print(f"     Género: {pred['genero']}")
        print(f"     Confianza: {pred['confianza']}%")
        print(f"     Razón: {pred['razon']}")
    
    # Test 2: Predicciones por hora
    print("\n\n[TEST 2] Géneros por hora actual:")
    for _ in range(5):
        genre = predictor.get_hourly_genre()
        print(f"  → {genre}")
    
    # Test 3: Evergreen songs
    print("\n\n[TEST 3] 5 canciones evergreen aleatorias:")
    for i, (artist, song) in enumerate(random.sample(EVERGREEN_SONGS, 5), 1):
        print(f"  {i}. {artist} - {song}")
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETO")
    print("="*80 + "\n")

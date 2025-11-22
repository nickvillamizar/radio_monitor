#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plan B: Predicción Inteligente de Canciones
============================================
Cuando la detección ICY/AudD falla, usa esta lógica para predecir
canciones con criterio basado en datos reales históricos.

Estrategias en orden de prioridad:
1. Reproducción Histórica (TOP 3 últimas 48h)
2. Reproducción por Horario (matutina/tarde/noche)
3. Reproducción por Género Esperado
4. Reproducción con Preferencias Dominicanas
"""

import logging
from datetime import datetime, timedelta
from random import choice, randint
from typing import Optional, Dict, List, Tuple

# Imports tardíos dentro de funciones para evitar ciclos de importación
# No importar aquí: from utils.db import db
# No importar aquí: from models.emisoras import Emisora, Cancion

logger = logging.getLogger(__name__)

class PlanBPredictor:
    """Sistema de predicción inteligente de canciones cuando falla la detección."""
    
    # Géneros esperados por tipo de emisora
    GENRE_MAP = {
        "tropical": ["Merengue", "Bachata", "Salsa", "Cumbia", "Bolero"],
        "reggaeton": ["Reggaeton", "Trap Latino", "Urbano", "Dembow"],
        "rock": ["Rock", "Rock Latino", "Hard Rock", "Rock Pop"],
        "pop": ["Pop", "Pop Latino", "Baladas Pop"],
        "jazz": ["Jazz", "Jazz Fusión"],
        "clásica": ["Clásica", "Orquesta", "Sinfonía"],
        "cristiana": ["Adoración", "Alabanza", "Cristiana"],
        "variada": None,  # Sin restricción de género
    }
    
    # Artistas/géneros preferidos en República Dominicana
    DOMINICAN_PREFERENCES = {
        "artists": [
            "Juan Luis Guerra", "ALEX DURAN", "Aventura", "Don Omar",
            "Anthony Santos", "Grupo Manía", "Sech", "Bad Bunny",
            "Rosalía", "J Balvin", "Zacarias Ferreira", "Elvis Martínez",
            "Wisin & Yandel", "Héctor Lavoe", "Willie Colón",
        ],
        "genres": [
            "Merengue", "Bachata", "Reggaeton", "Salsa",
            "Dembow", "Urbano", "Trap Latino",
        ]
    }
    
    def __init__(self, emisora_id: int):
        """Inicializa predictor para una emisora específica."""
        from utils.db import db  # Import tardío para evitar ciclos
        from models.emisoras import Emisora
        
        self.emisora_id = emisora_id
        self.emisora = db.session.query(Emisora).filter(
            Emisora.id == emisora_id
        ).first()
        
        if not self.emisora:
            logger.error(f"[PLAN_B] Emisora {emisora_id} no encontrada")
            raise ValueError(f"Emisora {emisora_id} no existe")
        
        logger.info(f"[PLAN_B] Inicializando predictor para: {self.emisora.nombre}")
    
    def predict_song(self, strategy: str = "auto") -> Optional[Dict]:
        """
        Predice una canción usando la estrategia especificada.
        
        Args:
            strategy: "auto" (mejor opción), "historical", "hourly", "genre", "dominican"
        
        Returns:
            Dict con {artista, titulo, razon} o None si no hay datos
        """
        try:
            if strategy == "auto":
                # Intentar estrategias en orden de prioridad
                result = self._predict_historical()
                if result:
                    return result
                    
                result = self._predict_hourly()
                if result:
                    return result
                    
                result = self._predict_by_genre()
                if result:
                    return result
                    
                result = self._predict_dominican()
                if result:
                    return result
                    
                logger.warning(f"[PLAN_B] No se pudo predecir canción para {self.emisora.nombre}")
                return None
            
            elif strategy == "historical":
                return self._predict_historical()
            elif strategy == "hourly":
                return self._predict_hourly()
            elif strategy == "genre":
                return self._predict_by_genre()
            elif strategy == "dominican":
                return self._predict_dominican()
            else:
                logger.error(f"[PLAN_B] Estrategia desconocida: {strategy}")
                return None
                
        except Exception as e:
            logger.error(f"[PLAN_B] Error prediciendo canción: {e}")
            return None
    
    def _predict_historical(self) -> Optional[Dict]:
        """
        Estrategia 1: Reproducción Histórica
        Obtiene TOP 3 canciones de últimas 48h y selecciona aleatoriamente.
        """
        from utils.db import db
        from models.emisoras import Cancion
        from sqlalchemy import func, desc
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=48)
            
            top_songs = db.session.query(
                Cancion.artista,
                Cancion.titulo,
                func.count(Cancion.id).label('count')
            ).filter(
                Cancion.emisora_id == self.emisora_id,
                Cancion.fecha_reproduccion >= cutoff_time,
                ~Cancion.artista.like('%Desconocido%'),
                ~Cancion.titulo.like('%Transmisión%')
            ).group_by(
                Cancion.artista,
                Cancion.titulo
            ).order_by(
                desc('count')
            ).limit(3).all()
            
            if top_songs:
                artista, titulo, _ = choice(top_songs)
                logger.info(f"[PLAN_B] Predicción HISTÓRICA: {artista} - {titulo}")
                return {
                    "artista": artista,
                    "titulo": titulo,
                    "razon": "historical_top3",
                    "confianza": 0.85,
                    "metadata": f"Top 3 últimas 48h de {self.emisora.nombre}"
                }
        except Exception as e:
            logger.warning(f"[PLAN_B] Error en predicción histórica: {e}")
        
        return None
    
    def _predict_hourly(self) -> Optional[Dict]:
        """
        Estrategia 2: Reproducción por Horario
        Segmenta por hora del día y usa TOP de ese horario.
        """
        try:
            now = datetime.now()
            current_hour = now.hour
            
            # Clasificar horarios
            if 6 <= current_hour < 12:
                hora_label = "matutina (6-12)"
            elif 12 <= current_hour < 18:
                hora_label = "tarde (12-18)"
            else:
                hora_label = "noche (18-6)"
            
            # Obtener canciones de horas similares del histórico
            top_for_hour = db.session.query(
                Cancion.artista,
                Cancion.titulo,
                func.count(Cancion.id).label('count')
            ).filter(
                Cancion.emisora_id == self.emisora_id,
                func.extract('hour', Cancion.fecha_reproduccion).between(
                    max(6, current_hour - 2),
                    min(23, current_hour + 2)
                ),
                ~Cancion.artista.like('%Desconocido%'),
                ~Cancion.titulo.like('%Transmisión%')
            ).group_by(
                Cancion.artista,
                Cancion.titulo
            ).order_by(
                desc('count')
            ).limit(3).all()
            
            if top_for_hour:
                artista, titulo, _ = choice(top_for_hour)
                logger.info(f"[PLAN_B] Predicción HORARIA ({hora_label}): {artista} - {titulo}")
                return {
                    "artista": artista,
                    "titulo": titulo,
                    "razon": "hourly_pattern",
                    "confianza": 0.75,
                    "metadata": f"Patrón horario {hora_label}"
                }
        except Exception as e:
            logger.warning(f"[PLAN_B] Error en predicción horaria: {e}")
        
        return None
    
    def _predict_by_genre(self) -> Optional[Dict]:
        """
        Estrategia 3: Reproducción por Género
        Clasifica emisora por género y selecciona del TOP de ese género.
        """
        try:
            # Detectar género probable de la emisora (por nombre)
            nombre_lower = self.emisora.nombre.lower()
            detected_genre = "variada"  # Por defecto
            
            for genre, keywords in [
                ("tropical", ["tropical", "merengue", "bachata", "criolla"]),
                ("reggaeton", ["reggaeton", "urbano", "dembow", "zumba"]),
                ("rock", ["rock", "metal", "punk"]),
                ("pop", ["pop", "éxitos", "número"]),
                ("variada", ["fuerte", "nueva", "expreso", "dale", "oxígeno"]),
            ]:
                if any(kw in nombre_lower for kw in keywords):
                    detected_genre = genre
                    break
            
            genre_keywords = self.GENRE_MAP.get(detected_genre, None)
            
            query = db.session.query(
                Cancion.artista,
                Cancion.titulo,
                func.count(Cancion.id).label('count')
            ).filter(
                Cancion.emisora_id == self.emisora_id,
                ~Cancion.artista.like('%Desconocido%'),
                ~Cancion.titulo.like('%Transmisión%')
            )
            
            if genre_keywords:
                # Filtrar por palabras clave de género (búsqueda aproximada)
                query = query.filter(
                    Cancion.genero_probable.in_(genre_keywords)
                    if hasattr(Cancion, 'genero_probable')
                    else True
                )
            
            top_genre = query.group_by(
                Cancion.artista,
                Cancion.titulo
            ).order_by(
                desc('count')
            ).limit(5).all()
            
            if top_genre:
                artista, titulo, _ = choice(top_genre)
                logger.info(f"[PLAN_B] Predicción GÉNERO ({detected_genre}): {artista} - {titulo}")
                return {
                    "artista": artista,
                    "titulo": titulo,
                    "razon": "genre_pattern",
                    "confianza": 0.70,
                    "metadata": f"Género detectado: {detected_genre}"
                }
        except Exception as e:
            logger.warning(f"[PLAN_B] Error en predicción por género: {e}")
        
        return None
    
    def _predict_dominican(self) -> Optional[Dict]:
        """
        Estrategia 4: Reproducción Dominicana
        Prioriza artistas y géneros populares en República Dominicana.
        """
        try:
            # Buscar canciones de artistas dominicanos preferidos
            dominican_artists = self.DOMINICAN_PREFERENCES["artists"]
            
            for artist in dominican_artists:
                cancion = db.session.query(
                    Cancion
                ).filter(
                    Cancion.emisora_id == self.emisora_id,
                    Cancion.artista.ilike(f"%{artist}%"),
                    ~Cancion.artista.like('%Desconocido%')
                ).order_by(
                    desc(Cancion.fecha_reproduccion)
                ).first()
                
                if cancion:
                    logger.info(f"[PLAN_B] Predicción DOMINICANA: {cancion.artista} - {cancion.titulo}")
                    return {
                        "artista": cancion.artista,
                        "titulo": cancion.titulo,
                        "razon": "dominican_artist",
                        "confianza": 0.80,
                        "metadata": f"Artista dominicano: {artist}"
                    }
            
            # Si no hay artistas específicos, obtener TOP general de la emisora
            top_general = db.session.query(
                Cancion.artista,
                Cancion.titulo,
                func.count(Cancion.id).label('count')
            ).filter(
                Cancion.emisora_id == self.emisora_id,
                ~Cancion.artista.like('%Desconocido%'),
                ~Cancion.titulo.like('%Transmisión%')
            ).group_by(
                Cancion.artista,
                Cancion.titulo
            ).order_by(
                desc('count')
            ).limit(10).all()
            
            if top_general:
                artista, titulo, _ = choice(top_general)
                logger.info(f"[PLAN_B] Predicción FALLBACK (TOP general): {artista} - {titulo}")
                return {
                    "artista": artista,
                    "titulo": titulo,
                    "razon": "top_general",
                    "confianza": 0.65,
                    "metadata": "TOP canciones general de emisora"
                }
        
        except Exception as e:
            logger.warning(f"[PLAN_B] Error en predicción dominicana: {e}")
        
        return None
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas de confiabilidad para la emisora."""
        try:
            total = db.session.query(Cancion).filter(
                Cancion.emisora_id == self.emisora_id
            ).count()
            
            reales = db.session.query(Cancion).filter(
                Cancion.emisora_id == self.emisora_id,
                ~Cancion.artista.like('%Desconocido%'),
                ~Cancion.titulo.like('%Transmisión%')
            ).count()
            
            generic = total - reales
            pct_real = (100 * reales // total) if total > 0 else 0
            
            return {
                "emisora": self.emisora.nombre,
                "total_canciones": total,
                "canciones_reales": reales,
                "canciones_genericas": generic,
                "porcentaje_real": pct_real,
                "plan_b_necesario": pct_real < 80,
            }
        except Exception as e:
            logger.error(f"[PLAN_B] Error obteniendo stats: {e}")
            return {}


def predict_for_all_stations() -> Dict:
    """Genera predicciones para todas las emisoras como referencia."""
    logger.info("[PLAN_B] Generando predicciones de referencia para todas las emisoras...")
    
    results = {}
    emisoras = db.session.query(Emisora).all()
    
    for emisora in emisoras:
        try:
            predictor = PlanBPredictor(emisora.id)
            prediction = predictor.predict_song()
            stats = predictor.get_stats()
            
            results[emisora.nombre] = {
                "prediction": prediction,
                "stats": stats,
            }
        except Exception as e:
            logger.error(f"[PLAN_B] Error para {emisora.nombre}: {e}")
            results[emisora.nombre] = {"error": str(e)}
    
    return results


if __name__ == "__main__":
    # Testing
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s'
    )
    
    try:
        # Obtener primera emisora para test
        from app import app
        with app.app_context():
            emisora_test = db.session.query(Emisora).first()
            if emisora_test:
                logger.info(f"Testing Plan B con: {emisora_test.nombre}")
                predictor = PlanBPredictor(emisora_test.id)
                
                # Probar cada estrategia
                print("\n" + "="*80)
                print("PRUEBA DE PLAN B - PREDICCIÓN DE CANCIONES")
                print("="*80 + "\n")
                
                for strategy in ["historical", "hourly", "genre", "dominican"]:
                    result = predictor.predict_song(strategy=strategy)
                    if result:
                        print(f"[{strategy.upper()}]")
                        print(f"  Artista: {result['artista']}")
                        print(f"  Título: {result['titulo']}")
                        print(f"  Confianza: {result['confianza']*100:.0f}%")
                        print(f"  Razón: {result['razon']}")
                        print()
                
                stats = predictor.get_stats()
                print(f"[ESTADÍSTICAS]")
                print(f"  Total canciones: {stats['total_canciones']}")
                print(f"  Reales: {stats['canciones_reales']} ({stats['porcentaje_real']}%)")
                print(f"  Plan B necesario: {stats['plan_b_necesario']}\n")
            else:
                logger.error("No hay emisoras en la base de datos")
    except Exception as e:
        logger.error(f"Error en test: {e}")
        import traceback
        traceback.print_exc()

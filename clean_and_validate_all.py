#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIMPIEZA Y VALIDACIÓN EXHAUSTIVA DE DATOS
==========================================
Script agresivo para eliminar datos inválidos, genéricos y defectuosos.
Objetivo: Maximizar calidad de datos reales.
"""

import os
import logging
import sys
import re
from datetime import datetime

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app
from utils.db import db
from models.emisoras import Cancion, Emisora

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('clean_and_validate.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# PATRONES DE RECHAZO
# ============================================================================

# Exactamente estos valores son INVÁLIDOS
INVALID_EXACT = {
    "desconocido - transmisión en vivo",
    "desconocido - transmision en vivo",
    "artista desconocido - transmisión en vivo",
    "artista desconocido - transmision en vivo",
    "now playing info goes here",
    "transmisión",
    "transmision",
    "-",
    "–",
    "—",
    "...",
    "----",
    "unknown",
    "n/a",
    "not available",
    "no disponible",
    "sin titulo",
    "sin información",
}

# Palabras que indican datos GENÉRICOS en artista
INVALID_ARTIST_KEYWORDS = {
    "desconocido",
    "unknown",
    "artista desconocido",
    "ads",
    "advert",
    "advertisement",
    "publicidad",
    "comercial",
    "now playing",
    "transmision",
    "transmisión",
    "en vivo",
    "live",
    "stream",
    "radio",
    "fm",
    "am",
    "estacion",
    "station",
}

# Palabras que indican datos GENÉRICOS en título
INVALID_TITLE_KEYWORDS = {
    "transmisión",
    "transmision",
    "en vivo",
    "live stream",
    "now playing",
    "block",
    "stream",
    "vdownloader",
    "audio oficial",
    "video oficial",
    "videoclip oficial",
    "official video",
    "official audio",
    "estás escuchando",
    "estas escuchando",
    "escuchando",
    "now on air",
    "info goes here",
    "no title",
    "sin titulo",
}

# Patrones de basura que aparecen en datos
GARBAGE_PATTERNS = [
    r'\(Video.*?\)',
    r'\(Audio.*?\)',
    r'\(Videoclip.*?\)',
    r'VDownloader',
    r'vdownloader',
    r'\[.*?\]',
    r'\{.*?\}',
    r'\(.*?Official.*?\)',
    r'HD\)',
    r'4K\)',
    r'HQ\)',
    r'LQ\)',
    r'320kbps',
    r'128kbps',
    r'64kbps',
    r'\.mp3',
    r'\.wav',
]

# ============================================================================
# VALIDADORES
# ============================================================================

def is_valid_string(text: str, min_length: int = 3) -> bool:
    """Valida que sea string válido."""
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    if len(text) < min_length:
        return False
    
    # No solo caracteres especiales o números
    if not any(c.isalpha() for c in text):
        return False
    
    return True


def is_valid_artist(artist: str) -> bool:
    """Valida artista con criterio ESTRICTO."""
    if not is_valid_string(artist):
        return False
    
    artist_lower = artist.lower().strip()
    
    # Exactos rechazados
    if artist_lower in INVALID_EXACT:
        return False
    
    # Contiene palabras prohibidas
    for kw in INVALID_ARTIST_KEYWORDS:
        if kw in artist_lower:
            return False
    
    # Muy corto o muy específico
    words = artist.split()
    if len(words) > 10:
        return False
    
    # Si empieza con números o caracteres especiales
    if artist[0].isdigit() or artist[0] in '-.,;:!?*':
        return False
    
    return True


def is_valid_title(title: str) -> bool:
    """Valida título con criterio ESTRICTO."""
    if not is_valid_string(title):
        return False
    
    title_lower = title.lower().strip()
    
    # Exactos rechazados
    if title_lower in INVALID_EXACT:
        return False
    
    # Contiene palabras prohibidas
    for kw in INVALID_TITLE_KEYWORDS:
        if kw in title_lower:
            return False
    
    # Muy largo (probable malformado)
    if len(title) > 300:
        return False
    
    # Si empieza con números o caracteres especiales
    if title[0].isdigit() or title[0] in '-.,;:!?*':
        return False
    
    return True


def clean_string(text: str) -> str:
    """Limpia basura de strings."""
    if not text:
        return ""
    
    text = text.strip()
    
    # Remover patrones de basura
    for pattern in GARBAGE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def detect_swapped(artist: str, title: str) -> bool:
    """Detecta si artista y título están invertidos."""
    if not artist or not title:
        return False
    
    # Si el título parece nombre de persona (2 partes, ambas capitalizadas)
    # y el artista es muy largo, probablemente estén invertidos
    
    title_words = title.split()
    artist_words = artist.split()
    
    # Título muy corto y muchas palabras, probable que sea canción
    if len(title_words) > 5 and len(artist_words) <= 3:
        # Probablemente está al revés
        return True
    
    # Si el artista contiene "- " varias veces, está malformado
    if artist.count(" - ") > 1:
        return True
    
    return False


# ============================================================================
# LIMPIEZA
# ============================================================================

def clean_database():
    """Limpia la base de datos de forma exhaustiva."""
    
    with app.app_context():
        print("\n" + "="*100)
        print("LIMPIEZA Y VALIDACIÓN EXHAUSTIVA DE CANCIONES")
        print("="*100 + "\n")
        
        # Estadísticas
        stats = {
            "total": 0,
            "valid": 0,
            "invalid_artist": 0,
            "invalid_title": 0,
            "invalid_both": 0,
            "garbage_removed": 0,
            "swapped": 0,
            "cleaned": 0,
            "deleted": 0,
        }
        
        # Obtener todas las canciones
        all_canciones = db.session.query(Cancion).all()
        stats["total"] = len(all_canciones)
        
        logger.info(f"[INICIO] Procesando {stats['total']} canciones...\n")
        
        to_delete = []
        to_update = []
        
        for idx, cancion in enumerate(all_canciones, 1):
            artista = cancion.artista
            titulo = cancion.titulo
            
            if idx % 1000 == 0:
                logger.info(f"[PROGRESO] {idx}/{stats['total']} procesadas...")
            
            # Limpieza básica
            artista_clean = clean_string(artista) if artista else ""
            titulo_clean = clean_string(titulo) if titulo else ""
            
            if artista != artista_clean or titulo != titulo_clean:
                stats["garbage_removed"] += 1
            
            # Validar artista
            if not is_valid_artist(artista_clean):
                stats["invalid_artist"] += 1
                
                # Si el título es válido, podríamos intentar guardar solo el título
                if is_valid_title(titulo_clean):
                    # Guardar solo título
                    to_update.append((cancion.id, "Artista Desconocido", titulo_clean))
                    stats["cleaned"] += 1
                else:
                    # Ambos inválidos - eliminar
                    to_delete.append(cancion.id)
                    stats["deleted"] += 1
                    stats["invalid_both"] += 1
                continue
            
            # Validar título
            if not is_valid_title(titulo_clean):
                stats["invalid_title"] += 1
                
                # Si el artista es válido, podríamos intentar guardar solo el artista
                if is_valid_artist(artista_clean):
                    # Guardar solo artista
                    to_update.append((cancion.id, artista_clean, "Canción Desconocida"))
                    stats["cleaned"] += 1
                else:
                    # Ambos inválidos - eliminar
                    to_delete.append(cancion.id)
                    stats["deleted"] += 1
                    stats["invalid_both"] += 1
                continue
            
            # Ambos válidos
            stats["valid"] += 1
            
            # Pero pueden estar invertidos
            if detect_swapped(artista_clean, titulo_clean):
                stats["swapped"] += 1
                logger.debug(f"[SWAP] Detectado: '{artista}' <-> '{titulo}'")
                to_update.append((cancion.id, titulo_clean, artista_clean))
                stats["cleaned"] += 1
            
            # O necesitar limpieza
            elif artista != artista_clean or titulo != titulo_clean:
                to_update.append((cancion.id, artista_clean, titulo_clean))
                stats["cleaned"] += 1
        
        # APLICAR CAMBIOS
        print("\n" + "-"*100)
        print(f"[APPLY] Aplicando cambios: {len(to_update)} actualizaciones, {len(to_delete)} eliminaciones")
        print("-"*100 + "\n")
        
        # Actualizar
        for cancion_id, new_artist, new_title in to_update:
            try:
                db.session.execute(
                    f"""UPDATE canciones 
                       SET artista = '{new_artist.replace("'", "''")}', 
                           titulo = '{new_title.replace("'", "''")}' 
                       WHERE id = {cancion_id}"""
                )
            except Exception as e:
                logger.error(f"Error actualizando {cancion_id}: {e}")
        
        # Eliminar
        if to_delete:
            try:
                db.session.execute(
                    f"DELETE FROM canciones WHERE id IN ({','.join(map(str, to_delete))})"
                )
            except Exception as e:
                logger.error(f"Error eliminando: {e}")
        
        # Commit
        try:
            db.session.commit()
            logger.info(f"[SUCCESS] Cambios aplicados exitosamente\n")
        except Exception as e:
            logger.error(f"[ERROR] Error en commit: {e}")
            db.session.rollback()
        
        # REPORTE
        print("="*100)
        print("REPORTE DE LIMPIEZA")
        print("="*100)
        print(f"\n[ENTRADA]")
        print(f"  Total canciones: {stats['total']}")
        
        print(f"\n[VALIDACIÓN]")
        print(f"  ✓ Válidas:           {stats['valid']} ({100*stats['valid']//stats['total']}%)")
        print(f"  ✗ Artista inválido:  {stats['invalid_artist']}")
        print(f"  ✗ Título inválido:   {stats['invalid_title']}")
        print(f"  ✗ Ambos inválidos:   {stats['invalid_both']}")
        
        print(f"\n[CORRECCIONES]")
        print(f"  🧹 Basura removida:      {stats['garbage_removed']}")
        print(f"  🔄 Invertidos corregidos: {stats['swapped']}")
        print(f"  ✏️  Limpiadas:           {stats['cleaned']}")
        print(f"  🗑️  Eliminadas:           {stats['deleted']}")
        
        print(f"\n[SALIDA]")
        final_valid = stats['valid'] + stats['cleaned'] - stats['deleted']
        print(f"  Total después: {stats['total'] - stats['deleted']}")
        print(f"  Válidas ahora:  {final_valid}")
        print(f"  Tasa mejora:    {100*final_valid//stats['total']}%")
        
        print("\n" + "="*100 + "\n")


def analyze_problematic():
    """Analiza qué canciones son problemáticas."""
    
    with app.app_context():
        print("\n" + "="*100)
        print("ANÁLISIS DE CANCIONES PROBLEMÁTICAS")
        print("="*100 + "\n")
        
        # Artistas problemáticos
        print("[ARTISTAS INVÁLIDOS] - Top 20")
        print("-"*100)
        
        from sqlalchemy import or_
        
        problematic_artists = db.session.query(
            Cancion.artista,
            db.func.count(Cancion.id).label('count')
        ).filter(
            or_(
                Cancion.artista.ilike('%desconocido%'),
                Cancion.artista.ilike('%unknown%'),
                Cancion.artista.ilike('%ads%'),
                Cancion.artista.ilike('%now playing%'),
                Cancion.artista == '-',
                Cancion.artista == '–',
                Cancion.artista == '—'
            )
        ).group_by(Cancion.artista).order_by(
            db.func.count(Cancion.id).desc()
        ).limit(20).all()
        
        for artista, count in problematic_artists:
            print(f"  • '{artista}': {count}x")
        
        # Títulos problemáticos
        print("\n[TÍTULOS INVÁLIDOS] - Top 20")
        print("-"*100)
        
        problematic_titles = db.session.query(
            Cancion.titulo,
            db.func.count(Cancion.id).label('count')
        ).filter(
            or_(
                Cancion.titulo.ilike('%transmisión%'),
                Cancion.titulo.ilike('%transmision%'),
                Cancion.titulo.ilike('%block%'),
                Cancion.titulo.ilike('%vdownloader%'),
                Cancion.titulo.ilike('%now playing%'),
                Cancion.titulo == '-',
                Cancion.titulo == '–',
                Cancion.titulo == '—'
            )
        ).group_by(Cancion.titulo).order_by(
            db.func.count(Cancion.id).desc()
        ).limit(20).all()
        
        for titulo, count in problematic_titles:
            print(f"  • '{titulo}': {count}x")
        
        print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    # Análisis primero
    analyze_problematic()
    
    # Luego limpiar
    input("Presiona ENTER para proceder con la limpieza (esto es irreversible)...")
    clean_database()
    
    print("[OK] LIMPIEZA COMPLETADA\n")

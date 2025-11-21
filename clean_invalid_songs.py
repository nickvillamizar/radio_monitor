#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIMPIEZA AGRESIVA V2 - Usando ORM correctamente
"""

import os
import logging
import sys
from datetime import datetime
from sqlalchemy import or_

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app
from utils.db import db
from models.emisoras import Cancion, Emisora

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clean_database_orm():
    """Limpia usando ORM directamente (más confiable)."""
    
    with app.app_context():
        print("\n" + "="*100)
        print("LIMPIEZA AGRESIVA V2 - Eliminando datos INVÁLIDOS")
        print("="*100 + "\n")
        
        # Estadísticas
        stats = {
            "analizado": 0,
            "eliminar": 0,
            "preservar": 0,
        }
        
        # Categorías a eliminar
        to_delete_count = db.session.query(Cancion).filter(
            or_(
                Cancion.artista.ilike('%desconocido%'),
                Cancion.artista.ilike('%unknown%'),
                Cancion.artista.ilike('%ads%'),
                Cancion.artista.ilike('%now playing%'),
                Cancion.artista == '-',
                Cancion.artista == '–',
                Cancion.artista == '—',
                Cancion.titulo.ilike('%transmisión%'),
                Cancion.titulo.ilike('%transmision%'),
                Cancion.titulo.ilike('%block%'),
                Cancion.titulo.ilike('%vdownloader%'),
                Cancion.titulo.ilike('%now playing%'),
                Cancion.titulo == '-',
                Cancion.titulo == '–',
                Cancion.titulo == '—',
            )
        ).count()
        
        print(f"[ANÁLISIS] Canciones a eliminar: {to_delete_count}")
        print(f"[ANÁLISIS] Canciones a preservar: {db.session.query(Cancion).count() - to_delete_count}\n")
        
        # Eliminar
        print(f"[DELETE] Eliminando canciones inválidas...")
        try:
            deleted = db.session.query(Cancion).filter(
                or_(
                    Cancion.artista.ilike('%desconocido%'),
                    Cancion.artista.ilike('%unknown%'),
                    Cancion.artista.ilike('%ads%'),
                    Cancion.artista.ilike('%now playing%'),
                    Cancion.artista == '-',
                    Cancion.artista == '–',
                    Cancion.artista == '—',
                    Cancion.titulo.ilike('%transmisión%'),
                    Cancion.titulo.ilike('%transmision%'),
                    Cancion.titulo.ilike('%block%'),
                    Cancion.titulo.ilike('%vdownloader%'),
                    Cancion.titulo.ilike('%now playing%'),
                    Cancion.titulo == '-',
                    Cancion.titulo == '–',
                    Cancion.titulo == '—',
                )
            ).delete(synchronize_session=False)
            
            db.session.commit()
            logger.info(f"[SUCCESS] {deleted} canciones eliminadas\n")
            
            # Estadísticas finales
            total_restante = db.session.query(Cancion).count()
            total_original = total_restante + deleted
            
            print("="*100)
            print("REPORTE DE LIMPIEZA")
            print("="*100)
            print(f"\nCanciones antes: {total_original}")
            print(f"Canciones eliminadas: {deleted}")
            print(f"Canciones después: {total_restante}")
            print(f"Porcentaje eliminado: {100*deleted//total_original}%")
            print(f"\nEstado: ✓ LIMPIEZA COMPLETADA\n")
            print("="*100 + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] {e}")
            db.session.rollback()
            return False


if __name__ == "__main__":
    clean_database_orm()

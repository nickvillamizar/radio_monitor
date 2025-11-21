"""
Force Detection - Fuerza la detección de canciones para emisoras específicas
Utiliza las nuevas URLs y fuerza el proceso de detección
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app, db
from models.emisoras import Emisora, Cancion
from utils.stream_reader import get_icy_metadata, capture_and_recognize_audd, parse_title_artist
from datetime import datetime
import requests

# Emisoras con URLs nuevas que queremos probar inmediatamente
EMISORAS_A_FORZAR = [114, 115]

def intentar_deteccion_manual(emisora):
    """
    Intenta detectar canción de una emisora manualmente
    """
    url = emisora.url_stream
    
    if not url:
        return False, "Sin URL"
    
    print(f"  Intentando GET ICY metadata...", end=" ", flush=True)
    
    try:
        # Intento 1: GET ICY metadata
        titulo_artist = get_icy_metadata(url)
        
        if titulo_artist and titulo_artist != "Desconocido - Transmisión en Vivo":
            print(f"[OK] Detectada: {titulo_artist[:60]}")
            artista, titulo = parse_title_artist(titulo_artist)
            return True, f"{artista} - {titulo}"
        else:
            print(f"[FAIL] ICY no válido")
    except Exception as e:
        print(f"[ERROR] {str(e)[:30]}")
    
    # Intento 2: AudD
    print(f"  Intentando AudD fingerprinting...", end=" ", flush=True)
    try:
        audd_result = capture_and_recognize_audd(url)
        if audd_result and audd_result != "Desconocido - Transmisión en Vivo":
            print(f"[OK] Detectada: {audd_result[:60]}")
            return True, audd_result
        else:
            print(f"[FAIL] AudD no devolvió resultado")
    except Exception as e:
        print(f"[ERROR] {str(e)[:30]}")
    
    return False, "No se pudo detectar"

with app.app_context():
    print("\n" + "="*90)
    print("FORCE DETECTION - DETECCION FORZADA CON URLS NUEVAS")
    print("="*90 + "\n")
    
    total_canciones_antes = db.session.query(Cancion).count()
    print(f"Canciones antes: {total_canciones_antes}\n")
    
    for emisora_id in EMISORAS_A_FORZAR:
        emisora = db.session.query(Emisora).filter(Emisora.id == emisora_id).first()
        
        if not emisora:
            print(f"[{emisora_id}] ERROR - Emisora no encontrada")
            continue
        
        print(f"\n[{emisora_id}] {emisora.nombre}")
        print("-" * 90)
        print(f"URL: {emisora.url_stream}")
        
        # Contar canciones antes
        canciones_antes = db.session.query(Cancion).filter(
            Cancion.emisora_id == emisora_id
        ).count()
        
        print(f"Canciones en BD antes: {canciones_antes}")
        
        # Intentar detección manual
        print(f"Iniciando detección...")
        exito, resultado = intentar_deteccion_manual(emisora)
        
        if exito:
            # Guardar canción en BD
            artista, titulo = resultado.split(' - ', 1) if ' - ' in resultado else ('Desconocido', resultado)
            
            # Verificar que no sea duplicada (últimas 30s)
            from datetime import timedelta
            hace_30s = datetime.now() - timedelta(seconds=30)
            duplicada = db.session.query(Cancion).filter(
                Cancion.emisora_id == emisora_id,
                Cancion.artista == artista,
                Cancion.titulo == titulo,
                Cancion.timestamp >= hace_30s
            ).first()
            
            if not duplicada:
                nueva_cancion = Cancion(
                    emisora_id=emisora_id,
                    artista=artista,
                    titulo=titulo,
                    timestamp=datetime.now(),
                    fuente='ICY/AudD'
                )
                db.session.add(nueva_cancion)
                db.session.commit()
                print(f"  [SAVED] Guardada en BD")
            else:
                print(f"  [SKIP] Duplicada en últimas 30s")
        
        # Contar canciones después
        canciones_despues = db.session.query(Cancion).filter(
            Cancion.emisora_id == emisora_id
        ).count()
        
        nuevas_canciones = canciones_despues - canciones_antes
        print(f"Total canciones ahora: {canciones_despues} (+{nuevas_canciones})")
    
    # RESUMEN FINAL
    total_canciones_despues = db.session.query(Cancion).count()
    nuevas_canciones_total = total_canciones_despues - total_canciones_antes
    
    print("\n" + "="*90)
    print("RESUMEN DE DETECCION FORZADA")
    print("="*90)
    print(f"\nCanciones ANTES: {total_canciones_antes}")
    print(f"Canciones DESPUES: {total_canciones_despues}")
    print(f"NUEVAS: {nuevas_canciones_total}\n")
    
    # Status por emisora
    for emisora_id in EMISORAS_A_FORZAR:
        cancion_count = db.session.query(Cancion).filter(
            Cancion.emisora_id == emisora_id
        ).count()
        emisora = db.session.query(Emisora).filter(
            Emisora.id == emisora_id
        ).first()
        estado = "OK - Detectadas" if cancion_count > 0 else "FALLA - Sin canciones"
        print(f"[{emisora_id}] {emisora.nombre}: {cancion_count} canciones ({estado})")
    
    print("\n" + "="*90 + "\n")

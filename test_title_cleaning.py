#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

# Import the functions
sys.path.insert(0, '/c/Users/57321/OneDrive/Escritorio/radio_monitor-main/radio_monitor-main')
from utils.stream_reader import normalize_string, clean_stream_title, is_valid_metadata, parse_title_artist

print("\n" + "="*100)
print("[TEST] VALIDACIÓN DE LIMPIEZA Y PARSING DE TÍTULOS")
print("="*100 + "\n")

# Test cases: (raw_title, expected_clean, should_validate)
test_cases = [
    # Real cases from the debug
    ("Now On Air:Anthony Santos vs Luis Vargas Mix 2014 - Anthony Santos vs Luis Vargas Mix 2014",
     "Anthony Santos vs Luis Vargas Mix 2014 - Anthony Santos vs Luis Vargas Mix 2014",
     True),
    
    # False positives we want to reject
    ("Desconocido - Transmisión en Vivo", None, False),
    ("Estás escuchando la super mix", None, False),
    
    # Real songs
    ("Now Playing: Coldplay - Fix You",
     "Coldplay - Fix You",
     True),
    
    ("Shakira - Hips Don't Lie",
     "Shakira - Hips Don't Lie",
     True),
    
    ("[EN VIVO] - Música variada",
     None,
     False),
]

for i, (raw, expected_clean, should_validate) in enumerate(test_cases, 1):
    print(f"[TEST {i}] Input: {raw}")
    
    # Clean
    cleaned = clean_stream_title(raw)
    print(f"  => Limpio: {cleaned}")
    
    if expected_clean:
        if cleaned == expected_clean:
            print(f"  [OK] Limpieza correcta")
        else:
            print(f"  [FAIL] Esperado: {expected_clean}")
    
    # Validate
    is_valid = is_valid_metadata(cleaned)
    print(f"  => ¿Válido?: {is_valid}")
    
    if is_valid == should_validate:
        print(f"  [OK] Validación correcta")
    else:
        print(f"  [FAIL] Esperado validación: {should_validate}")
    
    # Parse
    if is_valid:
        artist, title = parse_title_artist(cleaned)
        print(f"  => Artista: {artist}")
        print(f"  => Título: {title}")
    
    print()

print("="*100)
print("[TEST] FIN")
print("="*100 + "\n")

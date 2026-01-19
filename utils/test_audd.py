"""
Simple test script to capture audio from a stream (or local audio file) and
send it to AudD for debugging. It writes the raw AudD JSON response to tmp/.

Usage:
  python utils/test_audd.py <stream_url>

Environment:
  AUDD_API_TOKEN must be set in your environment or .env

This script is for debugging only — do not commit tokens to VCS.
"""
import os
import sys
import time
import requests
import subprocess

TEMP_DIR = os.path.join(os.getcwd(), "tmp")
os.makedirs(TEMP_DIR, exist_ok=True)

AUDD_TOKEN = os.getenv("AUDD_API_TOKEN")

if not AUDD_TOKEN:
    print("AUDD_API_TOKEN no encontrado en el entorno. Exportalo o añade a .env")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python utils/test_audd.py <stream_url_or_local_file>")
    sys.exit(1)

stream = sys.argv[1]

# Si la entrada es un archivo local y ya es WAV, evitamos ffmpeg
is_local_wav = os.path.exists(stream) and stream.lower().endswith('.wav')

sample_path = os.path.join(TEMP_DIR, f"test_audd_{int(time.time())}.wav")

try:
    if not is_local_wav:
        duration = 20
        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", stream,
            "-t", str(duration),
            "-ac", "1",
            "-ar", "44100",
            "-f", "wav",
            sample_path
        ]
        print(f"Capturando {duration}s desde: {stream}")
        subprocess.run(cmd, check=True)
    else:
        # copiar archivo local
        import shutil
        shutil.copyfile(stream, sample_path)

    with open(sample_path, "rb") as f:
        files = {"file": ("sample.wav", f, "audio/wav")}
        data = {"api_token": AUDD_TOKEN, "return": "spotify"}
        print("Enviando a AudD...")
        resp = requests.post("https://api.audd.io/", files=files, data=data, timeout=60)

    print(f"HTTP status: {resp.status_code}")
    try:
        j = resp.json()
        print("Respuesta AudD:")
        print(j)
    except Exception as e:
        print("No se pudo parsear JSON:", e)
        print(resp.text)

    # Guardar copia
    try:
        fname = os.path.join(TEMP_DIR, f"audd_test_resp_{int(time.time())}.json")
        with open(fname, "w", encoding="utf-8") as _f:
            _f.write(resp.text)
        print("Respuesta guardada en:", fname)
    except Exception as e:
        print("No se pudo guardar respuesta:", e)

finally:
    try:
        if os.path.exists(sample_path):
            os.remove(sample_path)
    except:
        pass

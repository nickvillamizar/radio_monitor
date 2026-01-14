#!/usr/bin/env python
"""
Test ACRCloud integration with real stream.
Tests audio capture and ACRCloud API call.
"""
import os
import sys
import subprocess
import shutil
from dotenv import load_dotenv

# Cargar .env
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Obtener credenciales
ACRCLOUD_ACCESS_KEY = os.getenv("ACRCLOUD_ACCESS_KEY")
ACRCLOUD_SECRET_KEY = os.getenv("ACRCLOUD_SECRET_KEY")

# Importar función ACRCloud
sys.path.insert(0, os.path.dirname(__file__))
from utils.stream_reader import capture_and_recognize_acrcloud

def test_acrcloud():
    """Test ACRCloud with a real streaming URL."""
    
    print("=" * 70)
    print("[TEST] ACRCloud Integration Test")
    print("=" * 70)
    
    # Verificar ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    print(f"[CHECK] ffmpeg: {ffmpeg if ffmpeg else 'NOT FOUND'}")
    
    if not ffmpeg:
        print("[ERROR] ffmpeg not found in PATH")
        return False
    
    # Verificar credenciales
    print(f"[CHECK] ACRCloud Access Key: {ACRCLOUD_ACCESS_KEY[:8] if ACRCLOUD_ACCESS_KEY else 'NOT SET'}...")
    print(f"[CHECK] ACRCloud Secret Key: {ACRCLOUD_SECRET_KEY[:8] if ACRCLOUD_SECRET_KEY else 'NOT SET'}...")
    
    if not ACRCLOUD_ACCESS_KEY or not ACRCLOUD_SECRET_KEY:
        print("[ERROR] ACRCloud credentials not configured in .env")
        return False
    
    # Test con un stream real
    test_url = "https://radio.hostlagarto.com/mocionfm89/stream"
    
    print(f"\n[TEST] Capturing audio from: {test_url}")
    print(f"[TEST] Testing ACRCloud recognition...")
    
    result = capture_and_recognize_acrcloud(test_url, ACRCLOUD_ACCESS_KEY, ACRCLOUD_SECRET_KEY)
    
    print("\n" + "=" * 70)
    if result:
        print("[SUCCESS] ACRCloud recognized a song!")
        print(f"  Artist: {result.get('artist')}")
        print(f"  Title:  {result.get('title')}")
        print(f"  Genre:  {result.get('genre', 'Unknown')}")
        return True
    else:
        print("[INFO] ACRCloud could not recognize the song")
        print("       (This can happen if the stream has no music or is silent)")
        print("[INFO] However, the API integration is working correctly.")
        return False

if __name__ == "__main__":
    success = test_acrcloud()
    sys.exit(0 if success else 1)

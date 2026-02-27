#!/usr/bin/env python
"""
Health check script for Render deployment.
Verifies that critical dependencies (ffmpeg, ACRCloud/AudD credentials, DATABASE_URL) are available.
Called by Docker HEALTHCHECK and by startup monitoring.
"""
import os
import sys
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_ffmpeg():
    """Verify ffmpeg is installed and accessible."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        logger.info(f"✓ ffmpeg found at: {ffmpeg_path}")
        return True
    else:
        logger.error("✗ ffmpeg NOT found in PATH")
        return False

def check_acrcloud_credentials():
    """Verify ACRCloud credentials (primary)."""
    access_key = os.getenv("ACRCLOUD_ACCESS_KEY")
    secret_key = os.getenv("ACRCLOUD_SECRET_KEY")
    
    if access_key and secret_key:
        masked_key = f"{access_key[:8]}...{access_key[-8:]}" if len(access_key) > 16 else "***"
        logger.info(f"✓ ACRCLOUD credentials are set: {masked_key}")
        return True
    else:
        logger.warning("⚠ ACRCLOUD credentials NOT fully set (required for primary music recognition)")
        return False

def check_audd_token():
    """Verify AUDD_API_TOKEN (fallback)."""
    token = os.getenv("AUDD_API_TOKEN")
    if token:
        # Log only first/last 8 chars for security
        masked = f"{token[:8]}...{token[-8:]}" if len(token) > 16 else "***"
        logger.info(f"✓ AUDD_API_TOKEN is set (fallback): {masked}")
        return True
    else:
        logger.warning("⚠ AUDD_API_TOKEN NOT set (fallback authentication disabled)")
        return False

def check_database_url():
    """Verify DATABASE_URL is set."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        logger.info(f"✓ DATABASE_URL is set")
        return True
    else:
        logger.error("✗ DATABASE_URL NOT set")
        return False

def check_secret_key():
    """Verify SECRET_KEY is set."""
    secret = os.getenv("SECRET_KEY")
    if secret:
        logger.info(f"✓ SECRET_KEY is set")
        return True
    else:
        logger.error("✗ SECRET_KEY NOT set")
        return False

if __name__ == "__main__":
    logger.info("="*70)
    logger.info("[HEALTHCHECK] Verificando dependencias críticas...")
    logger.info("="*70)
    
    ffmpeg_ok = check_ffmpeg()
    acrcloud_ok = check_acrcloud_credentials()
    audd_ok = check_audd_token()
    db_ok = check_database_url()
    secret_ok = check_secret_key()
    
    # Must have: ffmpeg, DB, SECRET_KEY
    # Should have: ACRCloud OR AudD (at least one recognition method)
    critical_ok = ffmpeg_ok and db_ok and secret_ok and (acrcloud_ok or audd_ok)
    
    logger.info("="*70)
    logger.info(f"[{'PASS' if ffmpeg_ok else 'FAIL'}] ffmpeg")
    logger.info(f"[{'PASS' if acrcloud_ok else 'WARN'}] ACRCloud (primary)")
    logger.info(f"[{'PASS' if audd_ok else 'WARN'}] AudD (fallback)")
    logger.info(f"[{'PASS' if db_ok else 'FAIL'}] DATABASE_URL")
    logger.info(f"[{'PASS' if secret_ok else 'FAIL'}] SECRET_KEY")
    logger.info("="*70)
    logger.info(f"[{'PASS' if critical_ok else 'FAIL'}] OVERALL HEALTH")
    logger.info("="*70)
    
    # Exit code: 0 = healthy, non-zero = unhealthy
    sys.exit(0 if critical_ok else 1)

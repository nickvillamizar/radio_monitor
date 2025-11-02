#!/usr/bin/env python3
# scan_once.py
# Ejecuta UNA pasada del monitor (usa la configuración y db del Flask app),
# registra logs y sale. Diseñado para ser llamado por cron cada X minutos.

import sys
import traceback
from datetime import datetime
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "cron_python.log"

# For consistent timezone output:
os.environ.setdefault("TZ", "America/Bogota")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def main():
    log("🔁 START SCAN (scan_once.py)")
    try:
        # Import app and stream_reader from your project
        # This will use your app.config and SQLAlchemy db
        import app as app_module
        from utils import stream_reader
    except Exception as exc:
        log("❌ Error importando app/stream_reader: " + str(exc))
        log(traceback.format_exc())
        return 2

    try:
        app = app_module.app
    except Exception as exc:
        log("❌ app no encontrada en app.py: " + str(exc))
        log(traceback.format_exc())
        return 2

    try:
        with app.app_context():
            log("🛰️  Llamando a stream_reader.actualizar_emisoras(...)")
            # Llamá a la función que ya tenés. Si acepta argumentos, ajustá.
            stream_reader.actualizar_emisoras(fallback_to_audd=bool(app.config.get("AUDD_API_TOKEN", "")))
            log("✅ actualizar_emisoras() completado")
    except Exception as exc:
        log("❌ Error en actualizar_emisoras: " + str(exc))
        log(traceback.format_exc())
        return 3

    log("✔️ SCAN COMPLETE (scan_once.py)")
    return 0

if __name__ == "__main__":
    sys.exit(main())

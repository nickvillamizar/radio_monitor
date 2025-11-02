# archivo: radio_monitor/config.py
import os

class Config:
    # 🔹 Conexión exclusiva a Neon DB
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")  # No más localhost ni fallback

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 🔹 Intervalo entre actualizaciones (en segundos)
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", 60))

    # 🔹 Token de API para Audd.io
    AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")

    # 🔹 Clave secreta Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecreto")


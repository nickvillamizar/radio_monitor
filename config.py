# archivo: radio_monitor/config.py
import os

class Config:
    # 🔹 Configuración de base de datos PostgreSQL
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL")
        or "postgresql+pg8000://postgres:1234@localhost:5432/radio_monitor"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 🔹 Intervalo entre actualizaciones (en segundos)
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", 60))

    # 🔹 Token de API para Audd.io (opcional, puede quedar vacío)
    AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN", "")

    # 🔹 Clave secreta Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecreto")

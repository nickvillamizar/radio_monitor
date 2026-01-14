
import os

class Config:
    # 🔹 Conexión exclusiva a Neon DB
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )

    # 🔹 Usar psycopg3 driver para compatibilidad con Python 3.13
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

    SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 🔹 Intervalo entre actualizaciones (en segundos)
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", 60))

    # 🔹 Token de API para Audd.io
    AUDD_API_TOKEN = os.getenv(
        "AUDD_API_TOKEN",
        ""
    )

    # 🔹 Clave secreta Flask
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "clave_super_secreta_por_defecto"
    )

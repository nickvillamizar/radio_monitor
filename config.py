
import os

class Config:
    # 🔹 Conexión exclusiva a Neon DB
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_KwHW54JXqORz@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 🔹 Intervalo entre actualizaciones (en segundos)
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", 60))

    # 🔹 Token de API para Audd.io
    AUDD_API_TOKEN = os.getenv(
        "AUDD_API_TOKEN",
        "TU_TOKEN_DE_PAGO"
    )

    # 🔹 Clave secreta Flask
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "clave_super_secreta_por_defecto"
    )

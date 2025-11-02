# check_db.py
from config import Config
from sqlalchemy import create_engine, text
import os

conf = Config()
# intenta usar DATABASE_URL si existe, si no, intenta construir desde config
db_url = getattr(conf, "SQLALCHEMY_DATABASE_URI", None) or os.environ.get("DATABASE_URL")
print("Usando DB URL:", db_url or "(no encontrado)")

if not db_url:
    raise SystemExit("No se encontró la URL de la base de datos en Config o en env DATABASE_URL")

engine = create_engine(db_url, future=True)

with engine.connect() as conn:
    print("Conectado OK. Ejecutando checks...")
    r = conn.execute(text("SELECT COUNT(*) AS total FROM plays"))
    print("plays total:", r.scalar() or 0)
    try:
        r2 = conn.execute(text("SELECT MAX(scanned_at) AS last_scan FROM plays"))
        print("Último scanned_at:", r2.scalar())
    except Exception as e:
        print("No se pudo consultar scanned_at:", e)

    print("Top 10 plays (artist / title / count):")
    try:
        rows = conn.execute(text("""
            SELECT artist, title, COUNT(*) AS cnt
            FROM plays
            WHERE (artist IS NOT NULL AND artist <> '') OR (title IS NOT NULL AND title <> '')
            GROUP BY artist, title
            ORDER BY cnt DESC
            LIMIT 10
        """)).all()
        for r in rows:
            print(r)
    except Exception as e:
        print("Error en consulta de agregados:", e)

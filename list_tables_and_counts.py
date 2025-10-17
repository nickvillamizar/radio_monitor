# list_tables_and_counts.py
from app import app
from utils.db import db
from sqlalchemy import inspect, text

def table_count(conn, table):
    try:
        r = conn.execute(text(f"SELECT COUNT(*) FROM \"{table}\""))
        return r.scalar()
    except Exception as e:
        return f"ERROR: {e}"

with app.app_context():
    engine = db.get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("DB engine:", engine.url)
    print("Tablas detectadas:", tables)
    with engine.connect() as conn:
        for t in tables:
            print(f" - {t}: {table_count(conn, t)} filas")

# ensure_models_create.py
from app import app
from utils.db import db
import importlib

# importa explícitamente los módulos de modelos para que SQLAlchemy conozca las clases
try:
    import models.emisoras as m_emisoras
    print("models.emisoras importado OK")
except Exception as e:
    print("Error importando models.emisoras:", e)

with app.app_context():
    print("Ejecutando db.create_all() ...")
    db.create_all()
    print("db.create_all() finalizado.")
    # mostrar tablas creadas
    engine = db.get_engine()
    from sqlalchemy import inspect
    inspector = inspect(engine)
    print("Tablas ahora:", inspector.get_table_names())

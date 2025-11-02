# archivo: cargar_emisoras.py
import json
from flask import Flask
from config import Config
from utils.db import db
from models.emisoras import Emisora

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def load_json(path="emisoras.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def upsert(emisoras):
    inserted = 0
    with app.app_context():
        db.create_all()
        for e in emisoras:
            nombre = e.get("nombre")
            url = e.get("url_stream") or e.get("url") or ""
            if not nombre or not url:
                continue
            emis = Emisora.query.filter_by(nombre=nombre).first()
            if not emis:
                emis = Emisora(
                    nombre=nombre,
                    url_stream=url,
                    ciudad=e.get("ciudad"),
                    genero=e.get("genero"),
                    plataforma=e.get("plataforma"),
                    sitio_web=e.get("sitio_web"),
                )
                db.session.add(emis)
                inserted += 1
            else:
                emis.url_stream = url
                emis.ciudad = e.get("ciudad")
                emis.genero = e.get("genero")
                emis.plataforma = e.get("plataforma")
                emis.sitio_web = e.get("sitio_web")
        db.session.commit()
    return inserted

if __name__ == "__main__":
    data = load_json("emisoras.json")
    n = upsert(data)
    print(f"{n} emisoras insertadas (o actualizadas).")

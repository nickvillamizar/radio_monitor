# archivo: models/emisoras.py
from datetime import datetime
from utils.db import db

class Emisora(db.Model):
    __tablename__ = 'emisoras'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    url_stream = db.Column(db.String(255), nullable=False)
    pais = db.Column(db.String(80), nullable=True)
    ultima_cancion = db.Column(db.String(255))
    ultima_actualizacion = db.Column(db.DateTime)

    # 🔹 Campos extra opcionales usados por cargar_emisoras.py
    ciudad = db.Column(db.String(120))
    genero = db.Column(db.String(120))
    plataforma = db.Column(db.String(120))
    sitio_web = db.Column(db.String(255))

    # relaciones
    canciones = db.relationship("Cancion", backref="emisora", lazy="dynamic")
    por_master = db.relationship("CancionPorEmisora", backref="emisora", lazy="dynamic")



class Cancion(db.Model):
    __tablename__ = "canciones"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(300))
    artista = db.Column(db.String(300))
    emisora_id = db.Column(db.Integer, db.ForeignKey("emisoras.id"))
    fecha_reproduccion = db.Column(db.DateTime, default=datetime.now)


# ---------------------------
# Tablas maestras (agregados)
# ---------------------------
class CancionMaster(db.Model):
    __tablename__ = "canciones_master"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.Text)
    artista = db.Column(db.Text)
    normalized_key = db.Column(db.Text, nullable=False, unique=True, index=True)
    total_plays = db.Column(db.Integer, nullable=False, default=0, index=True)
    first_play = db.Column(db.DateTime)
    last_play = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # relación a per-emisora
    por_emisora = db.relationship("CancionPorEmisora", backref="master", lazy="dynamic")


class CancionPorEmisora(db.Model):
    __tablename__ = "canciones_por_emisora"
    id = db.Column(db.Integer, primary_key=True)
    master_id = db.Column(db.Integer, db.ForeignKey("canciones_master.id", ondelete="CASCADE"), nullable=False, index=True)
    emisora_id = db.Column(db.Integer, db.ForeignKey("emisoras.id", ondelete="CASCADE"), nullable=False, index=True)
    plays = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("master_id", "emisora_id", name="uix_master_emisora"),
    )

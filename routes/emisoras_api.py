from flask import Blueprint, jsonify, request
from models.emisoras import Emisora, db

emisoras_api = Blueprint('emisoras_api', __name__)

# -----------------------------------------------------------
# 🔹 GET — Listar todas las emisoras
# -----------------------------------------------------------
@emisoras_api.route("/api/emisoras", methods=["GET"])
def listar_emisoras():
    emisoras = Emisora.query.all()
    data = [
        {
            "id": e.id,
            "nombre": e.nombre,
            "url_stream": e.url_stream,
            "pais": e.pais or "",
            "ultima_cancion": e.ultima_cancion or "",
            "ultima_actualizacion": (
                e.ultima_actualizacion.strftime("%Y-%m-%d %H:%M:%S")
                if e.ultima_actualizacion else ""
            )
        }
        for e in emisoras
    ]
    return jsonify(data), 200


# -----------------------------------------------------------
# 🔹 POST — Crear nueva emisora
# -----------------------------------------------------------
@emisoras_api.route("/api/emisoras", methods=["POST"])
def crear_emisora():
    data = request.get_json()
    if not data or "nombre" not in data or "url_stream" not in data:
        return jsonify({"error": "Faltan campos obligatorios"}), 400

    emisora = Emisora(
        nombre=data["nombre"].strip(),
        url_stream=data["url_stream"].strip(),
        pais=data.get("pais", "").strip() or None
    )

    db.session.add(emisora)
    db.session.commit()
    return jsonify({"message": "Emisora creada correctamente"}), 201


# -----------------------------------------------------------
# 🔹 PUT — Actualizar emisora existente
# -----------------------------------------------------------
@emisoras_api.route("/api/emisoras/<int:emisora_id>", methods=["PUT"])
def actualizar_emisora(emisora_id):
    emisora = Emisora.query.get(emisora_id)
    if not emisora:
        return jsonify({"error": "Emisora no encontrada"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Sin datos para actualizar"}), 400

    emisora.nombre = data.get("nombre", emisora.nombre).strip()
    emisora.url_stream = data.get("url_stream", emisora.url_stream).strip()
    emisora.pais = data.get("pais", emisora.pais)
    db.session.commit()

    return jsonify({"message": "Emisora actualizada correctamente"}), 200


# -----------------------------------------------------------
# 🔹 DELETE — Eliminar emisora
# -----------------------------------------------------------
@emisoras_api.route("/api/emisoras/<int:emisora_id>", methods=["DELETE"])
def eliminar_emisora(emisora_id):
    emisora = Emisora.query.get(emisora_id)
    if not emisora:
        return jsonify({"error": "Emisora no encontrada"}), 404

    db.session.delete(emisora)
    db.session.commit()
    return jsonify({"message": "Emisora eliminada correctamente"}), 200

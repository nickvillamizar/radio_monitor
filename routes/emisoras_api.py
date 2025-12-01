from flask import Blueprint, jsonify, request
from models.emisoras import Emisora, Cancion, db
from datetime import datetime, timedelta
from sqlalchemy import func

emisoras_api = Blueprint('emisoras_api', __name__)

def calcular_estado(emisora):
    """Calcula estado basado en fecha de última actualización."""
    if not emisora.ultima_actualizacion:
        return "sin_datos", "#888"
    
    dias = (datetime.now() - emisora.ultima_actualizacion).days
    
    if dias == 0:
        return "activo_hoy", "#00aa44"
    elif dias <= 1:
        return "activo_ayer", "#00ff88"
    elif dias <= 7:
        return "activo_semana", "#ffaa00"
    elif dias <= 30:
        return "inactivo_mes", "#ff6600"
    else:
        return "inactivo_mucho", "#cc0000"


# GET — Listar todas las emisoras
@emisoras_api.route("/api/emisoras", methods=["GET"])
def listar_emisoras():
    """Retorna lista de emisoras con estado y plays recientes."""
    try:
        emisoras = Emisora.query.order_by(Emisora.nombre).all()
        
        data = []
        for e in emisoras:
            try:
                ahora = datetime.now()
                estado, color = calcular_estado(e)
                dias = (ahora - e.ultima_actualizacion).days if e.ultima_actualizacion else None
                
                # Calcular plays 24h
                plays_24h = db.session.query(func.count(Cancion.id)).filter(
                    Cancion.emisora_id == e.id,
                    Cancion.fecha_reproduccion >= ahora - timedelta(days=1)
                ).scalar() or 0
                
                # Calcular plays 7d
                plays_7d = db.session.query(func.count(Cancion.id)).filter(
                    Cancion.emisora_id == e.id,
                    Cancion.fecha_reproduccion >= ahora - timedelta(days=7)
                ).scalar() or 0
                
                item = {
                    "id": int(e.id),
                    "nombre": str(e.nombre) if e.nombre else "",
                    "pais": str(e.pais) if e.pais else "",
                    "url_stream": str(e.url_stream) if e.url_stream else "",
                    "ultima_actualizacion": e.ultima_actualizacion.isoformat() if e.ultima_actualizacion else None,
                    "dias_sin_actualizar": dias,
                    "estado": estado,
                    "color": color,
                    "ultima_cancion": str(e.ultima_cancion) if e.ultima_cancion else "Desconocido - Transmisión en Vivo",
                    "plays_24h": int(plays_24h),
                    "plays_7d": int(plays_7d)
                }
                data.append(item)
            except Exception as ex:
                print(f"Error procesando emisora {e.id}: {ex}")
                pass
        
        return jsonify(data), 200
    
    except Exception as e:
        print(f"ERROR CRÍTICO en listar_emisoras: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
# POST — Crear nueva emisora
@emisoras_api.route("/api/emisoras", methods=["POST"])
def crear_emisora():
    """Crear nueva emisora con validación básica."""
    try:
        data = request.get_json() or {}
        
        # Validar obligatorios
        nombre = data.get("nombre", "").strip()
        url = data.get("url_stream", "").strip()
        
        if not nombre:
            return jsonify({"error": "Nombre es obligatorio"}), 400
        if not url:
            return jsonify({"error": "URL es obligatoria"}), 400
        
        # Validar formato URL
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": "URL debe comenzar con http:// o https://"}), 400
        
        # Verificar no duplicado
        if Emisora.query.filter_by(nombre=nombre).first():
            return jsonify({"error": "Ya existe una emisora con este nombre"}), 409
        
        # Crear
        emisora = Emisora(
            nombre=nombre,
            url_stream=url,
            pais=data.get("pais", "").strip() or None,
            ciudad=data.get("ciudad", "").strip() or None
        )
        db.session.add(emisora)
        db.session.commit()
        
        return jsonify({"message": "Creada", "id": emisora.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# PUT — Actualizar emisora
@emisoras_api.route("/api/emisoras/<int:emisora_id>", methods=["PUT"])
def actualizar_emisora(emisora_id):
    """Actualizar datos de emisora."""
    try:
        emisora = Emisora.query.get(emisora_id)
        if not emisora:
            return jsonify({"error": "No encontrada"}), 404
        
        data = request.get_json() or {}
        
        # Actualizar nombre
        if "nombre" in data:
            nombre = data["nombre"].strip()
            if not nombre:
                return jsonify({"error": "Nombre no puede estar vacío"}), 400
            if Emisora.query.filter(Emisora.nombre == nombre, Emisora.id != emisora_id).first():
                return jsonify({"error": "Nombre duplicado"}), 409
            emisora.nombre = nombre
        
        # Actualizar URL
        if "url_stream" in data:
            url = data["url_stream"].strip()
            if not url:
                return jsonify({"error": "URL no puede estar vacía"}), 400
            if not url.startswith(("http://", "https://")):
                return jsonify({"error": "URL debe comenzar con http:// o https://"}), 400
            emisora.url_stream = url
        
        # Otros campos
        if "pais" in data:
            emisora.pais = data["pais"].strip() or None
        if "ciudad" in data:
            emisora.ciudad = data["ciudad"].strip() or None
        
        db.session.commit()
        return jsonify({"message": "Actualizada"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# DELETE — Eliminar emisora
@emisoras_api.route("/api/emisoras/<int:emisora_id>", methods=["DELETE"])
def eliminar_emisora(emisora_id):
    """Eliminar una emisora."""
    try:
        emisora = Emisora.query.get(emisora_id)
        if not emisora:
            return jsonify({"error": "No encontrada"}), 404
        
        nombre = emisora.nombre
        db.session.delete(emisora)
        db.session.commit()
        return jsonify({"message": f"Eliminada: {nombre}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# GET — Estadísticas
@emisoras_api.route("/api/emisoras/stats", methods=["GET"])
def get_stats():
    """Retorna estadísticas de emisoras."""
    try:
        emisoras = Emisora.query.all()
        ahora = datetime.now()
        
        stats = {
            "total": len(emisoras),
            "activas_hoy": 0,
            "activas_ayer": 0,
            "activas_semana": 0,
            "inactivas_mes": 0,
            "inactivas_mucho": 0,
            "sin_datos": 0
        }
        
        for e in emisoras:
            if not e.ultima_actualizacion:
                stats["sin_datos"] += 1
            else:
                dias = (ahora - e.ultima_actualizacion).days
                if dias == 0:
                    stats["activas_hoy"] += 1
                elif dias <= 1:
                    stats["activas_ayer"] += 1
                elif dias <= 7:
                    stats["activas_semana"] += 1
                elif dias <= 30:
                    stats["inactivas_mes"] += 1
                else:
                    stats["inactivas_mucho"] += 1
        
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Incidencia, Trabajador
from extensions import db
from schemas import IncidenciaSchema, IncidenciaCreateSchema 

blp = Blueprint("incidencias", __name__, description="Gestión de Incidencias")

@blp.route("/incidencias")
class IncidenciaList(MethodView):
    
    @jwt_required()
    @blp.arguments(IncidenciaCreateSchema)
    def post(self, data):
        """Crear una nueva incidencia (Vacaciones, Baja...)"""
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if not trabajador:
            abort(404, message="Usuario no encontrado")

        nueva_incidencia = Incidencia(
            id_trabajador=user_id,
            tipo=data["tipo"],
            fecha_inicio=data["fecha_inicio"],
            fecha_fin=data["fecha_fin"],
            comentario_trabajador=data.get("comentario_trabajador", ""),
            estado="PENDIENTE"
        )

        try:
            db.session.add(nueva_incidencia)
            db.session.commit()
        except Exception as e:
            abort(500, message=f"Error al guardar incidencia: {str(e)}")

        return {"message": "Incidencia solicitada correctamente"}, 201
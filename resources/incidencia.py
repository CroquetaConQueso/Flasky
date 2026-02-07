from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import Incidencia, Trabajador
from extensions import db
from schemas import IncidenciaSchema, IncidenciaCreateSchema

blp = Blueprint("incidencias", __name__, description="Gestión de incidencias")

# Este módulo expone los endpoints que usa la app móvil para solicitar y consultar incidencias.
# La intención es centralizar “vacaciones/baja/asuntos/olvidos” en un flujo simple: crear solicitud y ver historial.

@blp.route("/incidencias")
class IncidenciaList(MethodView):
    # Endpoint unificado para incidencias del usuario autenticado:
    # - POST: crea una solicitud (queda PENDIENTE para que RRHH/administración la gestione).
    # - GET: devuelve el historial del propio usuario para mostrarlo en “Mis solicitudes”.
    @jwt_required()
    @blp.arguments(IncidenciaCreateSchema)
    def post(self, data):
        """Crear incidencia"""
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if not trabajador:
            abort(404, message="Usuario no encontrado")

        nueva = Incidencia(
            id_trabajador=trabajador.id_trabajador,
            tipo=data["tipo"],
            fecha_inicio=data["fecha_inicio"],
            fecha_fin=data["fecha_fin"],
            comentario_trabajador=data.get("comentario_trabajador", ""),
            estado="PENDIENTE"
        )

        try:
            db.session.add(nueva)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            abort(500, message=f"Error al guardar incidencia: {str(e)}")

        return {"message": "Incidencia solicitada correctamente"}, 201

    @jwt_required()
    @blp.response(200, IncidenciaSchema(many=True))
    def get(self):
        """Historial de incidencias"""
        user_id = get_jwt_identity()
        return (
            Incidencia.query
            .filter_by(id_trabajador=user_id)
            .order_by(Incidencia.fecha_solicitud.desc())
            .all()
        )

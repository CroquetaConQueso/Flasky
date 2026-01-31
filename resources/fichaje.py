import math
from datetime import datetime
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Trabajador, Fichaje, Empresa, Incidencia
from schemas import FichajeInputSchema, FichajeOutputSchema

blp = Blueprint("fichajes", __name__, description="Fichajes y Control de Presencia")

def calcular_distancia(lat1, lon1, lat2, lon2):
    # Fórmula de Haversine para calcular distancia entre coordenadas
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

@blp.route("/fichar")
class Fichar(MethodView):
    @jwt_required()
    @blp.arguments(FichajeInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, fichaje_data):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)
        empresa = trabajador.empresa

        if not empresa:
            abort(400, message="El trabajador no tiene empresa asignada.")

        if empresa.latitud and empresa.longitud:
            distancia = calcular_distancia(
                fichaje_data["latitud"],
                fichaje_data["longitud"],
                empresa.latitud,
                empresa.longitud
            )
            
            radio_permitido = (empresa.radio or 100) + 10
            
            if distancia > radio_permitido:
                abort(403, message=f"Estás demasiado lejos de la empresa ({int(distancia)}m). Acércate para fichar.")

        ultimo_fichaje = (
            Fichaje.query.filter_by(id_trabajador=user_id)
            .order_by(Fichaje.fecha_hora.desc())
            .first()
        )

        tipo_nuevo = "ENTRADA"
        
        if ultimo_fichaje:
            segundos_transcurridos = (datetime.now() - ultimo_fichaje.fecha_hora).total_seconds()
            
            # Bloqueo para evitar dobles clicks accidentales
            if segundos_transcurridos < 60:
                abort(429, message="Ya has fichado hace un momento. Espera un minuto.")

            if ultimo_fichaje.tipo == "ENTRADA":
                horas_transcurridas = segundos_transcurridos / 3600
                
                # Detección de olvido de salida del día anterior (Zombie)
                if horas_transcurridas > 16:
                    nueva_incidencia = Incidencia(
                        id_trabajador=user_id,
                        tipo='OLVIDO',
                        fecha_inicio=ultimo_fichaje.fecha_hora.date(),
                        fecha_fin=ultimo_fichaje.fecha_hora.date(),
                        comentario_trabajador=f"Autogenerada: Se detectó un turno abierto de {int(horas_transcurridas)} horas.",
                        estado='PENDIENTE',
                        comentario_admin="Detectado por el sistema al fichar al día siguiente."
                    )
                    db.session.add(nueva_incidencia)
                    # Mantenemos tipo_nuevo = 'ENTRADA' para iniciar el nuevo turno correctamente
                else:
                    tipo_nuevo = "SALIDA"

        nuevo_fichaje = Fichaje(
            id_trabajador=user_id,
            latitud=fichaje_data["latitud"],
            longitud=fichaje_data["longitud"],
            tipo=tipo_nuevo,
            fecha_hora=datetime.now()
        )

        db.session.add(nuevo_fichaje)
        db.session.commit()

        return nuevo_fichaje

@blp.route("/mis-fichajes")
class MisFichajes(MethodView):
    @jwt_required()
    @blp.response(200, FichajeOutputSchema(many=True))
    def get(self):
        user_id = get_jwt_identity()
        return (
            Fichaje.query.filter_by(id_trabajador=user_id)
            .order_by(Fichaje.fecha_hora.desc())
            .limit(50)
            .all()
        )
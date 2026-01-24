import math
from datetime import datetime
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
# IMPORTANTE: Añadimos 'Incidencia' a los imports
from models import Trabajador, Fichaje, Empresa, Incidencia
from schemas import FichajeInputSchema, FichajeOutputSchema

blp = Blueprint("fichajes", __name__, description="Fichajes y Control de Presencia")

# Función auxiliar para calcular distancia (Fórmula de Haversine)
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000  # Radio de la Tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distancia = R * c
    return distancia

@blp.route("/fichar")
class Fichar(MethodView):
    @jwt_required()
    @blp.arguments(FichajeInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, fichaje_data):
        # 1. Identificar al usuario
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)
        empresa = trabajador.empresa

        if not empresa:
            abort(400, message="El trabajador no tiene empresa asignada.")

        # 2. Validar Geolocalización (Solo si la empresa tiene coordenadas configuradas)
        if empresa.latitud and empresa.longitud:
            distancia = calcular_distancia(
                fichaje_data["latitud"],
                fichaje_data["longitud"],
                empresa.latitud,
                empresa.longitud
            )
            
            # Margen de seguridad (el radio definido + 10 metros por precisión del GPS)
            radio_permitido = (empresa.radio or 100) + 10
            
            if distancia > radio_permitido:
                abort(403, message=f"Estás demasiado lejos de la empresa ({int(distancia)}m). Acércate para fichar.")

        # 3. Determinar si es ENTRADA o SALIDA (Lógica Inteligente)
        ultimo_fichaje = (
            Fichaje.query.filter_by(id_trabajador=user_id)
            .order_by(Fichaje.fecha_hora.desc())
            .first()
        )

        tipo_nuevo = "ENTRADA"
        
        if ultimo_fichaje and ultimo_fichaje.tipo == "ENTRADA":
            # Calculamos cuántas horas han pasado
            horas_transcurridas = (datetime.now() - ultimo_fichaje.fecha_hora).total_seconds() / 3600
            
            # UMBRAL DE OLVIDO: 16 Horas
            if horas_transcurridas > 16:
                # Caso ZOMBIE: Han pasado más de 16h, asumimos que se olvidó de salir ayer.
                # Acción A: El fichaje actual cuenta como una NUEVA ENTRADA para hoy.
                tipo_nuevo = "ENTRADA" 
                
                # Acción B: Generar Incidencia Automática
                nueva_incidencia = Incidencia(
                    id_trabajador=user_id,
                    tipo='OLVIDO',
                    fecha_inicio=ultimo_fichaje.fecha_hora.date(), # Fecha del error
                    fecha_fin=ultimo_fichaje.fecha_hora.date(),
                    comentario_trabajador=f"Autogenerada: Se detectó un turno abierto de {int(horas_transcurridas)} horas.",
                    estado='PENDIENTE', # Tú la revisarás en el panel
                    comentario_admin="Detectado por el sistema al fichar al día siguiente."
                )
                db.session.add(nueva_incidencia)
                # El usuario verá un mensaje distinto en la app o simplemente fichará 'Entrada' correctamente.
                
            else:
                # Caso NORMAL: Cierra el turno
                tipo_nuevo = "SALIDA"

        # 4. Guardar Fichaje
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
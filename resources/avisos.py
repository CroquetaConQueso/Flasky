from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo 
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from models import Trabajador, Dia, Franja, Fichaje

blp = Blueprint("avisos", __name__, description="Avisos y recordatorios")

# Configuración
TZ = ZoneInfo("Europe/Madrid")
MARGEN_MINUTOS = 15

DIAS_SEMANA = {
    0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
    4: "viernes", 5: "sabado", 6: "domingo"
}

@blp.route("/recordatorio-fichaje")
class RecordatorioFichaje(MethodView):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)

        # Hora local actual
        now = datetime.now(TZ).replace(tzinfo=None)
        hoy = now.date()

        nombre_dia = DIAS_SEMANA[hoy.weekday()]
        dia_db = Dia.query.filter_by(nombre=nombre_dia).first()

        # 1. Comprobaciones básicas (Día existe, tiene horario)
        if not dia_db or not trabajador.idHorario:
            return {"avisar": False, "motivo": "SIN_HORARIO_O_DIA"}

        # 2. ¿Trabaja hoy?
        franjas_hoy = Franja.query.filter_by(
            id_horario=trabajador.idHorario,
            id_dia=dia_db.id
        ).all()

        if not franjas_hoy:
            return {"avisar": False, "motivo": "HOY_LIBRA"}

        # 3. ¿Ya pasó la hora de entrada + margen?
        hora_entrada_min = min(f.hora_entrada for f in franjas_hoy)
        hora_limite = datetime.combine(hoy, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)

        if now < hora_limite:
            return {"avisar": False, "motivo": "AUN_NO_TOCA"}

        # 4. ¿Tiene ENTRADA hoy?
        inicio_dia = datetime.combine(hoy, dtime.min)
        fin_dia = datetime.combine(hoy, dtime.max)

        fichaje_entrada = Fichaje.query.filter(
            Fichaje.id_trabajador == trabajador.id_trabajador,
            func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
            Fichaje.fecha_hora >= inicio_dia,
            Fichaje.fecha_hora <= fin_dia
        ).first()

        if fichaje_entrada:
            return {"avisar": False, "motivo": "YA_FICHO"}

        # 5. SI LLEGA AQUÍ: Debe fichar y no lo ha hecho
        return {
            "avisar": True, 
            "motivo": "FALTA_ENTRADA", 
            "titulo": "¡Te has olvidado de fichar!", 
            "mensaje": f"Hola {trabajador.nombre}, hoy trabajas y no consta tu entrada."
        }
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from models import Trabajador, Dia, Franja, Fichaje

blp = Blueprint("avisos", __name__, description="Avisos y recordatorios")

TZ = ZoneInfo("Europe/Madrid")
MARGEN_MINUTOS = 15

DIAS_SEMANA = {
    0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
    4: "viernes", 5: "sabado", 6: "domingo"
}

# Endpoint que devuelve un recordatorio si el trabajador debía entrar hoy, ya pasó la hora de entrada (+margen)
# y no existe un fichaje de tipo ENTRADA registrado en el día actual.
def _local_now_naive():
    # Hora Madrid en naive (sin tzinfo)
    return datetime.now(TZ).replace(tzinfo=None)

def _get_franjas_hoy(trabajador: Trabajador, hoy_fecha):
    # Franjas de hoy para el horario del trabajador
    if not trabajador.idHorario:
        return []

    nombre_dia = DIAS_SEMANA.get(hoy_fecha.weekday())
    if not nombre_dia:
        return []

    dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
    if not dia_db:
        return []

    return Franja.query.filter_by(id_horario=trabajador.idHorario, id_dia=dia_db.id).all()

def _tiene_entrada_hoy(trabajador: Trabajador, hoy_fecha):
    # True si existe ENTRADA hoy
    inicio_dia = datetime.combine(hoy_fecha, dtime.min)
    fin_dia = datetime.combine(hoy_fecha, dtime.max)

    fichaje_entrada = Fichaje.query.filter(
        Fichaje.id_trabajador == trabajador.id_trabajador,
        func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
        Fichaje.fecha_hora >= inicio_dia,
        Fichaje.fecha_hora <= fin_dia
    ).first()

    return fichaje_entrada is not None

@blp.route("/recordatorio-fichaje")
class RecordatorioFichaje(MethodView):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()

        try:
            user_id_int = int(user_id)
        except Exception:
            user_id_int = user_id

        trabajador = Trabajador.query.get(user_id_int)
        if not trabajador:
            abort(404, message="Usuario no encontrado")

        now = _local_now_naive()
        hoy = now.date()

        franjas_hoy = _get_franjas_hoy(trabajador, hoy)
        if not franjas_hoy:
            if not trabajador.idHorario:
                return {"avisar": False, "motivo": "SIN_HORARIO"}

            nombre_dia = DIAS_SEMANA.get(hoy.weekday())
            dia_db = Dia.query.filter_by(nombre=nombre_dia).first() if nombre_dia else None
            if not dia_db:
                return {"avisar": False, "motivo": "DIA_NO_CONFIGURADO"}

            return {"avisar": False, "motivo": "HOY_LIBRA"}

        hora_entrada_min = min((f.hora_entrada for f in franjas_hoy if f.hora_entrada), default=None)
        if not hora_entrada_min:
            return {"avisar": False, "motivo": "SIN_HORA_ENTRADA"}

        hora_limite = datetime.combine(hoy, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)
        if now < hora_limite:
            return {"avisar": False, "motivo": "AUN_NO_TOCA"}

        if _tiene_entrada_hoy(trabajador, hoy):
            return {"avisar": False, "motivo": "YA_FICHO"}

        return {
            "avisar": True,
            "motivo": "FALTA_ENTRADA",
            "titulo": "¡Te has olvidado de fichar!",
            "mensaje": f"Hola {trabajador.nombre}, hoy trabajas y no consta tu entrada."
        }

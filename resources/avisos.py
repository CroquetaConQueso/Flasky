from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from models import Trabajador, Dia, Franja, Fichaje

blp = Blueprint("avisos", __name__, description="Avisos y recordatorios")

# Config: referencia temporal y margen de cortesía
TZ = ZoneInfo("Europe/Madrid")
MARGEN_MINUTOS = 15

DIAS_SEMANA = {
    0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
    4: "viernes", 5: "sabado", 6: "domingo"
}

# ---------------------------------------------------------------------
# Helpers: fecha/hora y horario del día
# ---------------------------------------------------------------------

def _local_now_naive():
    """Hora actual en Madrid (naive) para comparar con BD."""
    return datetime.now(TZ).replace(tzinfo=None)


def _get_dia_db(hoy_fecha):
    """Devuelve el Dia (BD) asociado a la fecha."""
    nombre_dia = DIAS_SEMANA.get(hoy_fecha.weekday())
    if not nombre_dia:
        return None
    return Dia.query.filter_by(nombre=nombre_dia).first()


def _get_franjas_hoy(trabajador: Trabajador, hoy_fecha):
    """Franjas del trabajador para el día indicado."""
    if not trabajador.idHorario:
        return []

    dia_db = _get_dia_db(hoy_fecha)
    if not dia_db:
        return []

    return Franja.query.filter_by(id_horario=trabajador.idHorario, id_dia=dia_db.id).all()


def _day_range(hoy_fecha):
    """Rango completo del día [00:00, 23:59:59.999999]."""
    inicio_dia = datetime.combine(hoy_fecha, dtime.min)
    fin_dia = datetime.combine(hoy_fecha, dtime.max)
    return inicio_dia, fin_dia


def _hora_limite_entrada(franjas_hoy, hoy_fecha):
    """Límite de ENTRADA: primera hora de entrada + margen."""
    hora_entrada_min = min((f.hora_entrada for f in franjas_hoy if f.hora_entrada), default=None)
    if not hora_entrada_min:
        return None
    return datetime.combine(hoy_fecha, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)


def _hora_limite_salida(franjas_hoy, hoy_fecha):
    """Límite de SALIDA: última salida + margen (soporta cruce de medianoche)."""
    limites = []
    for f in franjas_hoy:
        if not f.hora_entrada or not f.hora_salida:
            continue

        dt_out = datetime.combine(hoy_fecha, f.hora_salida)

        if f.hora_salida < f.hora_entrada:
            dt_out = dt_out + timedelta(days=1)

        limites.append(dt_out)

    if not limites:
        return None

    dt_max = max(limites)
    return dt_max + timedelta(minutes=MARGEN_MINUTOS)

# ---------------------------------------------------------------------
# Helpers: fichajes y respuesta estándar
# ---------------------------------------------------------------------

def _ultimo_fichaje_absoluto(trabajador_id):
    """Último fichaje histórico (sin filtrar por fecha)."""
    return Fichaje.query.filter_by(
        id_trabajador=trabajador_id
    ).order_by(Fichaje.fecha_hora.desc()).first()


def _tiene_entrada_hoy(trabajador_id, hoy_fecha) -> bool:
    """True si existe ENTRADA registrada hoy."""
    inicio, fin = _day_range(hoy_fecha)
    return Fichaje.query.filter(
        Fichaje.id_trabajador == trabajador_id,
        func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
        Fichaje.fecha_hora >= inicio,
        Fichaje.fecha_hora <= fin
    ).first() is not None


def _resp(avisar: bool, motivo: str, titulo: str = None, mensaje: str = None):
    """Payload JSON uniforme para el cliente."""
    data = {"avisar": bool(avisar), "motivo": motivo}
    if titulo:
        data["titulo"] = titulo
    if mensaje:
        data["mensaje"] = mensaje
    return data

# ---------------------------------------------------------------------
# Endpoint: recordatorio de fichaje (entrada/salida)
# ---------------------------------------------------------------------

@blp.route("/recordatorio-fichaje")
class RecordatorioFichaje(MethodView):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        try:
            user_id_int = int(user_id)
        except:
            user_id_int = user_id

        trabajador = Trabajador.query.get(user_id_int)
        if not trabajador: abort(404)

        now = _local_now_naive()
        hoy = now.date()

        # Estado "dentro/fuera" basado en el último fichaje global
        ultimo_fichaje = _ultimo_fichaje_absoluto(trabajador.id_trabajador)

        esta_dentro = False
        fecha_entrada = None

        if ultimo_fichaje and (ultimo_fichaje.tipo or "").strip().upper() == "ENTRADA":
            esta_dentro = True
            fecha_entrada = ultimo_fichaje.fecha_hora.date()

        franjas_hoy = _get_franjas_hoy(trabajador, hoy)

        # A) Está dentro: prioriza detectar olvido de salida (incluye días anteriores)
        if esta_dentro:
            if fecha_entrada < hoy:
                 return _resp(
                    True, "FALTA_SALIDA",
                    "¡Te dejaste el fichaje abierto!",
                    f"Hola {trabajador.nombre}, constas como 'Dentro' desde el día {fecha_entrada.strftime('%d/%m')}. Por favor, ficha la salida."
                )

            if not franjas_hoy:
                return _resp(
                    True, "FALTA_SALIDA",
                    "Fichaje abierto detectado",
                    f"Hola {trabajador.nombre}, figuras como 'Dentro' hoy, pero no tienes horario asignado."
                )

            limite_salida = _hora_limite_salida(franjas_hoy, hoy)

            if limite_salida and now >= limite_salida:
                return _resp(
                    True, "FALTA_SALIDA",
                    "¡Te has olvidado de salir!",
                    f"Hola {trabajador.nombre}, tu turno terminó y sigues fichado."
                )

            return _resp(False, "TRABAJANDO")

        # B) Está fuera: si trabaja hoy y ya pasó el límite de entrada, avisar
        else:
            if not franjas_hoy:
                return _resp(False, "HOY_LIBRA")

            limite_entrada = _hora_limite_entrada(franjas_hoy, hoy)

            if limite_entrada and now >= limite_entrada:
                if _tiene_entrada_hoy(trabajador.id_trabajador, hoy):
                    return _resp(False, "JORNADA_FINALIZADA")

                return _resp(
                    True, "FALTA_ENTRADA",
                    "¡Aviso de Fichaje!",
                    f"Hola {trabajador.nombre}, tu turno ha empezado y no consta tu entrada."
                )

            return _resp(False, "AUN_NO_TOCA")

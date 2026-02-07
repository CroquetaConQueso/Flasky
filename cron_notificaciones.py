from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app import create_app
from models import Trabajador, Dia, Franja, Fichaje
from utils.firebase_sender import enviar_notificacion_push
from extensions import db

# Config
TZ = ZoneInfo("Europe/Madrid")
MARGEN_MINUTOS = 15
MODO_DEBUG = True

DIAS_SEMANA = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo"
}

def _log(msg: str):
    if MODO_DEBUG:
        print(msg)

def comprobar_ausencias():
    app = create_app()

    with app.app_context():
        _log("\n--- CRON: AUSENCIAS ---")

        # Hora local (naive)
        now_local = datetime.now(TZ).replace(tzinfo=None)
        hoy = now_local.date()

        # Rango de hoy
        inicio_dia = datetime.combine(hoy, dtime.min)
        fin_dia = datetime.combine(hoy, dtime.max)

        # Día de la semana (tabla Dia)
        nombre_dia = DIAS_SEMANA[hoy.weekday()]
        _log(f"Fecha: {hoy} ({nombre_dia})")

        # Día configurado en BD
        dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
        if not dia_db:
            _log("INFO: Día no configurado en BD")
            return

        trabajadores = Trabajador.query.all()
        enviados = 0
        evaluados = 0

        for t in trabajadores:
            # Sin horario = no aplica
            if not t.idHorario:
                continue

            # Franjas de hoy
            franjas_hoy = Franja.query.filter_by(id_horario=t.idHorario, id_dia=dia_db.id).all()
            if not franjas_hoy:
                continue

            evaluados += 1

            # Hora límite (entrada mínima + margen)
            hora_entrada_min = min(f.hora_entrada for f in franjas_hoy)
            hora_limite = datetime.combine(hoy, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)

            # Aún no toca avisar
            if now_local < hora_limite:
                _log(f"SKIP: {t.nombre} (límite {hora_limite.time()})")
                continue

            # ¿Tiene ENTRADA hoy?
            fichaje_entrada = Fichaje.query.filter(
                Fichaje.id_trabajador == t.id_trabajador,
                func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
                Fichaje.fecha_hora >= inicio_dia,
                Fichaje.fecha_hora <= fin_dia
            ).first()

            if fichaje_entrada:
                _log(f"OK: {t.nombre} ENTRADA @ {fichaje_entrada.fecha_hora}")
                continue

            # Sin token = no se puede push
            if not t.fcm_token:
                _log(f"NO TOKEN: {t.nombre}")
                continue

            # Enviar push
            try:
                titulo = "Falta de fichaje"
                mensaje = f"Hola {t.nombre}, hoy trabajas y no consta tu entrada. Por favor, registra el fichaje."
                enviar_notificacion_push(t.fcm_token, titulo, mensaje)
                enviados += 1
                _log(f"ENVIADO: {t.nombre}")
            except Exception as e:
                _log(f"ERROR PUSH {t.nombre}: {e}")

        _log(f"--- FIN: evaluados={evaluados} enviados={enviados} ---\n")

if __name__ == "__main__":
    comprobar_ausencias()

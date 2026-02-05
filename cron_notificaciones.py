from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app import create_app
from models import Trabajador, Dia, Franja, Fichaje
from utils.firebase_sender import enviar_notificacion_push
from extensions import db

# --- CONFIG ---
TZ = ZoneInfo("Europe/Madrid")   # Ajusta la zona horaria real
MARGEN_MINUTOS = 15              # Gracia tras la hora de entrada
MODO_DEBUG = True                # True = imprime logs detallados

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
        _log("\n--- CRON: COMPROBACIÓN DE AUSENCIAS ---")

        # Hora actual en Madrid (naive para comparar con DATETIME típico en MySQL)
        now_local = datetime.now(TZ).replace(tzinfo=None)
        hoy = now_local.date()

        inicio_dia = datetime.combine(hoy, dtime.min)
        fin_dia = datetime.combine(hoy, dtime.max)

        nombre_dia = DIAS_SEMANA[hoy.weekday()]
        _log(f"Fecha local: {hoy} ({nombre_dia})")
        _log(f"Rango día: {inicio_dia} -> {fin_dia}")
        _log(f"Ahora: {now_local}")

        # 1) Día en BDD
        dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
        if not dia_db:
            _log("INFO: No existe el día en tabla Dia (o no configurado). Fin.")
            return

        trabajadores = Trabajador.query.all()
        enviados = 0
        evaluados = 0

        for t in trabajadores:
            # Solo trabajadores con horario
            if not t.idHorario:
                continue

            # 2) Franjas de HOY para el horario del trabajador
            franjas_hoy = Franja.query.filter_by(id_horario=t.idHorario, id_dia=dia_db.id).all()
            if not franjas_hoy:
                # Hoy libra
                continue

            evaluados += 1

            # 3) Hora de entrada más temprana de hoy + margen
            hora_entrada_min = min(f.hora_entrada for f in franjas_hoy)
            hora_limite = datetime.combine(hoy, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)

            # Si aún no pasó la hora límite, no avisamos
            if now_local < hora_limite:
                _log(f"SKIP: {t.nombre} aún no toca (límite {hora_limite.time()})")
                continue

            # 4) ¿Existe ENTRADA hoy?
            fichaje_entrada = Fichaje.query.filter(
                Fichaje.id_trabajador == t.id_trabajador,
                func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
                Fichaje.fecha_hora >= inicio_dia,
                Fichaje.fecha_hora <= fin_dia
            ).first()

            if fichaje_entrada:
                _log(f"OK: {t.nombre} fichó ENTRADA @ {fichaje_entrada.fecha_hora}")
                continue

            # 5) Si no hay ENTRADA hoy y ya pasó hora_limite -> enviar push (si hay token)
            if not t.fcm_token:
                _log(f"NO TOKEN: {t.nombre} (no se puede enviar push)")
                continue

            try:
                titulo = "Falta de fichaje"
                mensaje = f"Hola {t.nombre}, hoy trabajas y no consta tu entrada. Por favor, registra el fichaje."
                enviar_notificacion_push(t.fcm_token, titulo, mensaje)
                enviados += 1
                _log(f"ENVIADO: Push a {t.nombre}")
            except Exception as e:
                _log(f"ERROR PUSH {t.nombre}: {e}")

        _log(f"--- FIN CRON: evaluados={evaluados} enviados={enviados} ---\n")

if __name__ == "__main__":
    comprobar_ausencias()

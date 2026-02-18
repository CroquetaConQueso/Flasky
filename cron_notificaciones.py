from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app import create_app
from models import Trabajador, Dia, Franja, Fichaje, Incidencia
from utils.firebase_sender import enviar_notificacion_push

TZ = ZoneInfo("Europe/Madrid")
MARGEN_MINUTOS = 15
VENTANA_ENVIO_MINUTOS = 60
MODO_DEBUG = True

DIAS_SEMANA = {
    0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
    4: "viernes", 5: "sabado", 6: "domingo"
}

TIPOS_AUSENCIA = {"VACACIONES", "BAJA", "ASUNTOS_PROPIOS"}


def _log(msg: str):
    if MODO_DEBUG:
        print(msg)


def _now_local_naive():
    # Hora Madrid sin tzinfo para comparar con datetimes de BD (naive).
    return datetime.now(TZ).replace(tzinfo=None)


def _rango_hoy(hoy_date):
    # Rango completo del día.
    inicio_dia = datetime.combine(hoy_date, dtime.min)
    fin_dia = datetime.combine(hoy_date, dtime.max)
    return inicio_dia, fin_dia


def _en_ausencia_aprobada(trabajador_id: int, hoy_date):
    # Ausencias aprobadas que justifican no fichar.
    inc = Incidencia.query.filter(
        Incidencia.id_trabajador == trabajador_id,
        Incidencia.estado == "APROBADA",
        Incidencia.tipo.in_(TIPOS_AUSENCIA),
        Incidencia.fecha_inicio <= hoy_date,
        Incidencia.fecha_fin >= hoy_date
    ).first()
    return inc is not None


def _tiene_entrada_hoy(trabajador_id: int, inicio_dia, fin_dia):
    # ENTRADA registrada dentro del día.
    return (
        Fichaje.query.filter(
            Fichaje.id_trabajador == trabajador_id,
            func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
            Fichaje.fecha_hora >= inicio_dia,
            Fichaje.fecha_hora <= fin_dia
        ).first()
        is not None
    )


def _ultimo_fichaje_absoluto(trabajador_id):
    # Último fichaje histórico (para detectar “zombies” de días anteriores).
    return (
        Fichaje.query.filter(
            Fichaje.id_trabajador == trabajador_id
        )
        .order_by(Fichaje.fecha_hora.desc())
        .first()
    )


def _dentro_ventana(now_local, limite, nombre_check=""):
    # Ventana [limite, limite + VENTANA_ENVIO_MINUTOS).
    limite_fin = limite + timedelta(minutes=VENTANA_ENVIO_MINUTOS)
    esta_dentro = limite <= now_local < limite_fin

    if MODO_DEBUG and not esta_dentro:
        diferencia = (now_local - limite).total_seconds() / 60
        if -120 < diferencia < 120:
            _log(
                f"   [DEBUG {nombre_check}] Fuera de ventana. "
                f"Hora: {now_local.strftime('%H:%M')} | "
                f"Ventana: {limite.strftime('%H:%M')} - {limite_fin.strftime('%H:%M')}"
            )

    return esta_dentro


def comprobar_fichajes_entrada_salida():
    app = create_app()
    with app.app_context():
        _log("\n=============================================")
        _log("   CRON: CONTROL DE PRESENCIA (ABSOLUTO)   ")
        _log("=============================================")

        now_local = _now_local_naive()
        hoy = now_local.date()
        inicio_dia, fin_dia = _rango_hoy(hoy)

        nombre_dia = DIAS_SEMANA[hoy.weekday()]
        _log(f"Fecha sistema (Madrid): {now_local} ({nombre_dia})")

        dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
        if not dia_db:
            _log("ERROR: El día actual no existe en la tabla 'Dia' de la BD.")
            return

        trabajadores = Trabajador.query.all()
        enviados = 0

        for t in trabajadores:
            _log(f"\n--- Evaluando a: {t.nombre} ---")

            if not t.idHorario:
                _log("   -> Sin horario asignado. Skip.")
                continue

            if _en_ausencia_aprobada(t.id_trabajador, hoy):
                _log("   -> Ausencia aprobada. Skip.")
                continue

            #Zombie: última acción es ENTRADA y es de antes de hoy
            ultimo = _ultimo_fichaje_absoluto(t.id_trabajador)
            if ultimo and (ultimo.tipo or "").strip().upper() == "ENTRADA":
                if ultimo.fecha_hora.date() < hoy:
                    _log(
                        f"   [ALERTA] Fichaje abierto de {ultimo.fecha_hora} "
                        f"(posible olvido de salida)."
                    )
                    if t.fcm_token:
                        try:
                            enviar_notificacion_push(
                                t.fcm_token,
                                "¡Olvido de Salida!",
                                f"Hola {t.nombre}, detectamos una entrada del día "
                                f"{ultimo.fecha_hora.strftime('%d/%m')} sin cerrar."
                            )
                            enviados += 1
                            _log("   [OK] Push ZOMBIE enviado")
                        except Exception as e:
                            _log(f"   [ERROR] Push ZOMBIE falló: {e}")
                    else:
                        _log("   [SIMULACIÓN] Push ZOMBIE (sin token)")
                    continue

            #Franjas de hoy (si no hay, libra)
            franjas_hoy = Franja.query.filter_by(id_horario=t.idHorario, id_dia=dia_db.id).all()
            if not franjas_hoy:
                _log(f"   -> Sin franjas hoy ({nombre_dia}). Libra.")
                continue

            hora_entrada_min = min(f.hora_entrada for f in franjas_hoy)
            hora_salida_max = max(f.hora_salida for f in franjas_hoy)

            limite_entrada = datetime.combine(hoy, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)
            limite_salida = datetime.combine(hoy, hora_salida_max) + timedelta(minutes=MARGEN_MINUTOS)

            _log(f"   Horario: {hora_entrada_min} - {hora_salida_max}")
            _log(
                f"   Ventana ENTRADA: {limite_entrada.strftime('%H:%M')} - "
                f"{(limite_entrada + timedelta(minutes=VENTANA_ENVIO_MINUTOS)).strftime('%H:%M')}"
            )
            _log(f"   Check SALIDA desde: {limite_salida.strftime('%H:%M')}")

            if not t.fcm_token:
                _log("   -> Sin token FCM (no se puede notificar).")

            #Aviso ENTRADA: solo dentro de ventana
            if _dentro_ventana(now_local, limite_entrada, "ENTRADA"):
                if not _tiene_entrada_hoy(t.id_trabajador, inicio_dia, fin_dia):
                    if t.fcm_token:
                        try:
                            enviar_notificacion_push(
                                t.fcm_token,
                                "Falta fichaje",
                                f"Hola {t.nombre}, no consta tu entrada."
                            )
                            enviados += 1
                            _log("   [OK] Push ENTRADA enviado")
                        except Exception as e:
                            _log(f"   [ERROR] Push ENTRADA falló: {e}")
                    else:
                        _log("   [SIMULACIÓN] Push ENTRADA (sin token)")
                else:
                    _log("   [OK] Ya tiene ENTRADA hoy.")

            #Aviso SALIDA: persistente a partir del límite
            if now_local >= limite_salida:
                if ultimo:
                    estado_ultimo = (ultimo.tipo or "").strip().upper()
                    if estado_ultimo == "ENTRADA" and ultimo.fecha_hora.date() == hoy:
                        _log(f"   Último fichaje: ENTRADA ({ultimo.fecha_hora}). Falta SALIDA.")
                        if t.fcm_token:
                            try:
                                enviar_notificacion_push(
                                    t.fcm_token,
                                    "Falta fichaje",
                                    f"Hola {t.nombre}, no has fichado la salida."
                                )
                                enviados += 1
                                _log("   [OK] Push SALIDA enviado")
                            except Exception as e:
                                _log(f"   [ERROR] Push SALIDA falló: {e}")
                        else:
                            _log("   [SIMULACIÓN] Push SALIDA (sin token)")
                    elif estado_ultimo == "SALIDA":
                        _log("   [OK] El usuario ya salió.")
                    else:
                        pass
                else:
                    _log("   [INFO] Sin fichajes registrados y ya pasó la hora de salida.")
            else:
                pass

        _log(f"\n--- FIN PROCESO: Notificaciones reales enviadas = {enviados} ---")


if __name__ == "__main__":
    comprobar_fichajes_entrada_salida()

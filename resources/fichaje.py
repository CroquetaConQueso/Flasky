import math
import calendar
import re
from datetime import datetime, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Trabajador, Fichaje, Empresa, Incidencia, Dia, Franja
from schemas import (
    FichajeInputSchema,
    FichajeOutputSchema,
    ResumenMensualQuerySchema,
    ResumenMensualOutputSchema,
    FichajeNFCInputSchema
)

blp = Blueprint("fichajes", __name__, description="Fichajes y control de presencia")

# Este módulo agrupa endpoints de presencia: fichar (GPS/NFC), consultar historial, y calcular resumen mensual.
# La idea es que la app móvil consuma una API estable para registrar ENTRADA/SALIDA con validaciones de empresa.

def normalizar_rol(raw: str) -> str:
    if not raw:
        return "SIN_ROL"
    return re.sub(r"[^A-Z]", "", raw.strip().upper())


def es_admin_robusto(trabajador):
    if not trabajador or not getattr(trabajador, "rol", None) or not getattr(trabajador.rol, "nombre_rol", None):
        return False, "SIN_ROL"
    rol_norm = normalizar_rol(trabajador.rol.nombre_rol)
    claves = ["ADMIN", "RESPONSABLE", "SUPER", "RRHH", "GERENTE", "JEFE", "ENCARGADO", "DIREC"]
    return any(k in rol_norm for k in claves), rol_norm


def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _normalizar_uid(uid: str) -> str:
    if not uid:
        return ""
    return uid.strip().upper().replace(":", "").replace("-", "").replace(" ", "")


def _uid_invertido(uid_hex: str) -> str:
    uid_hex = _normalizar_uid(uid_hex)
    if len(uid_hex) < 2:
        return uid_hex
    pares = [uid_hex[i:i + 2] for i in range(0, len(uid_hex), 2)]
    pares.reverse()
    return "".join(pares)


def _validar_distancia_empresa(empresa: Empresa, lat: float, lon: float):
    if not empresa:
        return
    if empresa.latitud is not None and empresa.longitud is not None:
        distancia = calcular_distancia(lat, lon, empresa.latitud, empresa.longitud)
        radio_permitido = (empresa.radio or 100) + 50
        if distancia > radio_permitido:
            abort(403, message=f"Lejos de la empresa ({int(distancia)}m).")


def _crear_fichaje(trabajador: Trabajador, lat: float, lon: float):
    ultimo = (
        Fichaje.query.filter_by(id_trabajador=trabajador.id_trabajador)
        .order_by(Fichaje.fecha_hora.desc())
        .first()
    )

    tipo_nuevo = "ENTRADA"

    if ultimo:
        segundos = (datetime.now() - ultimo.fecha_hora).total_seconds()

        if segundos < 60:
            abort(429, message="Espera un minuto para volver a fichar.")

        if (ultimo.tipo or "").strip().upper() == "ENTRADA":
            horas = segundos / 3600
            if horas > 16:
                inc = Incidencia(
                    id_trabajador=trabajador.id_trabajador,
                    tipo="OLVIDO",
                    fecha_inicio=ultimo.fecha_hora.date(),
                    fecha_fin=ultimo.fecha_hora.date(),
                    comentario_trabajador=f"Autogenerada: Turno abierto de {int(horas)}h.",
                    estado="PENDIENTE",
                    comentario_admin="Cierre automático."
                )
                db.session.add(inc)
                tipo_nuevo = "ENTRADA"
            else:
                tipo_nuevo = "SALIDA"

    nuevo = Fichaje(
        id_trabajador=trabajador.id_trabajador,
        latitud=lat,
        longitud=lon,
        tipo=tipo_nuevo,
        fecha_hora=datetime.now()
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def _procesar_fichaje_comun(user_id, lat, lon, nfc_data_raw=None):
    # Unificamos la lógica para evitar duplicar validaciones entre /fichar y /fichar-nfc.
    # Así cualquier cambio de reglas (GPS, NFC oficina, NFC personal) se toca en un solo sitio.
    trabajador = Trabajador.query.get_or_404(user_id)
    empresa = trabajador.empresa

    nfc_oficina_requerido = _normalizar_uid(getattr(empresa, "codigo_nfc_oficina", None))

    if nfc_oficina_requerido:
        # Si existe NFC “oficina”, lo usamos como torno: obliga a escanear esa etiqueta para fichar.
        nfc_recibido = _normalizar_uid(nfc_data_raw)

        if not nfc_recibido:
            abort(400, message="Fichaje restringido: Debes escanear el punto NFC de la entrada.")

        uid_inv = _uid_invertido(nfc_recibido)

        if nfc_recibido != nfc_oficina_requerido and uid_inv != nfc_oficina_requerido:
            abort(403, message="NFC Incorrecto. Escanea la etiqueta oficial de la entrada.")
    else:
        # Si no hay NFC “oficina”, permitimos modo NFC personal: valida contra el UID asignado al trabajador.
        nfc_recibido = _normalizar_uid(nfc_data_raw)
        if nfc_recibido:
            uid_guardado = _normalizar_uid(getattr(trabajador, "codigo_nfc", None))
            uid_inv = _uid_invertido(nfc_recibido)

            if not uid_guardado or (nfc_recibido != uid_guardado and uid_inv != uid_guardado):
                abort(403, message="Código NFC no válido o no asignado a este usuario.")

    _validar_distancia_empresa(empresa, lat, lon)

    return _crear_fichaje(trabajador, lat, lon)


@blp.route("/resumen")
class ResumenMensual(MethodView):
    # Endpoint para la pantalla de resumen de horas: teóricas vs trabajadas por mes y año.
    # Se usa para mostrar saldo y controlar si el empleado va en positivo/negativo según su horario asignado.
    @jwt_required()
    @blp.arguments(ResumenMensualQuerySchema, location="query")
    @blp.response(200, ResumenMensualOutputSchema)
    def get(self, args):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)

        now = datetime.now()
        mes = args.get("mes") or now.month
        anio = args.get("anio") or now.year

        if not trabajador.idHorario:
            return {"mes": f"{mes}/{anio}", "teoricas": 0.0, "trabajadas": 0.0, "saldo": 0.0}

        _, num_days = calendar.monthrange(anio, mes)
        start_date = datetime(anio, mes, 1)
        end_date = datetime(anio, mes, num_days, 23, 59, 59)

        dias_semana = {
            0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
            4: "viernes", 5: "sabado", 6: "domingo"
        }

        horas_por_weekday = {}
        for wd, nombre in dias_semana.items():
            dia_db = Dia.query.filter_by(nombre=nombre).first()
            if not dia_db:
                horas_por_weekday[wd] = 0
                continue

            franjas = Franja.query.filter_by(id_horario=trabajador.idHorario, id_dia=dia_db.id).all()
            sec = 0
            for f in franjas:
                if not f.hora_entrada or not f.hora_salida:
                    continue
                t_in = timedelta(hours=f.hora_entrada.hour, minutes=f.hora_entrada.minute)
                t_out = timedelta(hours=f.hora_salida.hour, minutes=f.hora_salida.minute)
                sec += (t_out - t_in).total_seconds()

            horas_por_weekday[wd] = sec

        total_teorico = 0
        for d in range(1, num_days + 1):
            total_teorico += horas_por_weekday.get(datetime(anio, mes, d).weekday(), 0)

        fichajes = Fichaje.query.filter(
            Fichaje.id_trabajador == user_id,
            Fichaje.fecha_hora >= start_date,
            Fichaje.fecha_hora <= end_date
        ).order_by(Fichaje.fecha_hora).all()

        total_trabajado = 0
        pendientes = []
        for f in fichajes:
            if (f.tipo or "").strip().upper() == "ENTRADA":
                pendientes.append(f)
            elif (f.tipo or "").strip().upper() == "SALIDA" and pendientes:
                ent = pendientes.pop()
                total_trabajado += (f.fecha_hora - ent.fecha_hora).total_seconds()

        return {
            "mes": start_date.strftime("%B %Y"),
            "teoricas": round(total_teorico / 3600, 2),
            "trabajadas": round(total_trabajado / 3600, 2),
            "saldo": round((total_trabajado - total_teorico) / 3600, 2)
        }


@blp.route("/fichar")
class Fichar(MethodView):
    # Endpoint “normal” de fichaje: la app lo usa cuando registra presencia con GPS (y opcionalmente NFC).
    # Existe para mantener compatibilidad con flujo antiguo y permitir fichaje aunque no se use NFC obligatorio.
    @jwt_required()
    @blp.arguments(FichajeInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, data):
        user_id = get_jwt_identity()
        return _procesar_fichaje_comun(
            user_id,
            data.get("latitud"),
            data.get("longitud"),
            data.get("nfc_data")
        )


@blp.route("/fichar-nfc")
class FicharNFC(MethodView):
    # Endpoint dedicado NFC: la app lo usa cuando el flujo de fichaje viene explícitamente de un escaneo.
    # Existe para separar claramente el caso “NFC obligatorio” y poder endurecer validaciones sin romper /fichar.
    @jwt_required()
    @blp.arguments(FichajeNFCInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, data):
        user_id = get_jwt_identity()
        return _procesar_fichaje_comun(
            user_id,
            data.get("latitud"),
            data.get("longitud"),
            data.get("nfc_data")
        )


@blp.route("/mis-fichajes")
class MisFichajes(MethodView):
    # Endpoint para la pantalla de historial del trabajador (solo los suyos).
    # Se limita en cantidad para no cargar la app ni saturar red; para rangos grandes se haría otro endpoint.
    @jwt_required()
    @blp.response(200, FichajeOutputSchema(many=True))
    def get(self):
        user_id = get_jwt_identity()
        return (
            Fichaje.query
            .filter_by(id_trabajador=user_id)
            .order_by(Fichaje.fecha_hora.desc())
            .limit(50)
            .all()
        )


@blp.route("/fichajes-empleado/<int:empleado_id>")
class FichajesEmpleado(MethodView):
    # Endpoint de administración: permite a un admin consultar fichajes de un empleado concreto.
    # Se usa en panel RRHH/app admin para auditoría y control; restringimos por empresa para evitar fuga de datos.
    @jwt_required()
    @blp.response(200, FichajeOutputSchema(many=True))
    def get(self, empleado_id):
        yo = Trabajador.query.get_or_404(get_jwt_identity())

        ok, rol = es_admin_robusto(yo)
        if not ok:
            abort(403, message="No eres admin.")

        target = Trabajador.query.get_or_404(empleado_id)

        if target.idEmpresa != yo.idEmpresa and "SUPER" not in rol:
            abort(404, message="Empleado no encontrado.")

        return (
            Fichaje.query
            .filter_by(id_trabajador=empleado_id)
            .order_by(Fichaje.fecha_hora.desc())
            .limit(100)
            .all()
        )

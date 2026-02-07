import math
import calendar
import re
from datetime import datetime, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc

from extensions import db
from models import Trabajador, Fichaje, Empresa, Incidencia, Dia, Franja
from schemas import (
    FichajeInputSchema,
    FichajeOutputSchema,
    ResumenMensualQuerySchema,
    ResumenMensualOutputSchema,
    FichajeSchema,
    FichajeNFCInputSchema
)

blp = Blueprint("fichajes", __name__, description="Fichajes y Control de Presencia")


# =========================================================
# HELPERS
# =========================================================
def normalizar_rol(raw: str) -> str:
    """Elimina todo lo que no sea letra A-Z y pasa a mayúsculas."""
    if not raw:
        return "SIN_ROL"
    return re.sub(r'[^A-Z]', '', raw.strip().upper())


def es_admin_robusto(trabajador):
    if not trabajador or not getattr(trabajador, "rol", None) or not getattr(trabajador.rol, "nombre_rol", None):
        return False, "SIN_ROL"

    rol_norm = normalizar_rol(trabajador.rol.nombre_rol)
    claves = ["ADMIN", "RESPONSABLE", "SUPER", "RRHH", "GERENTE", "JEFE", "ENCARGADO", "DIREC"]
    tiene_poder = any(k in rol_norm for k in claves)
    return tiene_poder, rol_norm


def calcular_distancia(lat1, lon1, lat2, lon2):
    """Haversine."""
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


def _normalizar_uid(uid: str) -> str:
    if not uid:
        return ""
    return uid.strip().upper()


def _uid_invertido(uid_hex: str) -> str:
    """Invierte por pares hex (A1B2C3 -> C3B2A1)."""
    uid_hex = _normalizar_uid(uid_hex)
    if len(uid_hex) < 2:
        return uid_hex
    pares = [uid_hex[i:i + 2] for i in range(0, len(uid_hex), 2)]
    pares.reverse()
    return "".join(pares)


def _validar_distancia_empresa(empresa: Empresa, lat: float, lon: float):
    if not empresa:
        abort(400, message="El trabajador no tiene empresa asignada.")

    # ✅ No uses truthy-check (0.0 rompería el control)
    if empresa.latitud is not None and empresa.longitud is not None:
        distancia = calcular_distancia(lat, lon, empresa.latitud, empresa.longitud)
        radio_permitido = (empresa.radio or 100) + 10

        if distancia > radio_permitido:
            abort(403, message=f"Estás demasiado lejos de la empresa ({int(distancia)}m). Acércate para fichar.")


def _crear_fichaje(trabajador: Trabajador, lat: float, lon: float):
    """
    Lógica única para generar fichaje ENTRADA/SALIDA con:
    - Anti doble toque 60s
    - Zombie (>16h)
    - Guarda en DB
    """
    ultimo_fichaje = (
        Fichaje.query.filter_by(id_trabajador=trabajador.id_trabajador)
        .order_by(Fichaje.fecha_hora.desc())
        .first()
    )

    tipo_nuevo = "ENTRADA"

    if ultimo_fichaje:
        segundos = (datetime.now() - ultimo_fichaje.fecha_hora).total_seconds()

        if segundos < 60:
            abort(429, message="Ya has fichado hace un momento. Espera un minuto.")

        if (ultimo_fichaje.tipo or "").strip().upper() == "ENTRADA":
            horas = segundos / 3600

            if horas > 16:
                inc = Incidencia(
                    id_trabajador=trabajador.id_trabajador,
                    tipo="OLVIDO",
                    fecha_inicio=ultimo_fichaje.fecha_hora.date(),
                    fecha_fin=ultimo_fichaje.fecha_hora.date(),
                    comentario_trabajador=f"Autogenerada: Se detectó un turno abierto de {int(horas)} horas.",
                    estado="PENDIENTE",
                    comentario_admin="Detectado por el sistema al fichar al día siguiente."
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


# =========================================================
# ENDPOINTS
# =========================================================
@blp.route("/resumen")
class ResumenMensual(MethodView):
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

        dias_semana = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}
        horas_por_weekday = {}

        for wd, nombre_dia in dias_semana.items():
            dia_bd = Dia.query.filter_by(nombre=nombre_dia).first()
            if dia_bd:
                franjas = Franja.query.filter_by(id_horario=trabajador.idHorario, id_dia=dia_bd.id).all()
                total_seconds = 0
                for f in franjas:
                    t_in = timedelta(hours=f.hora_entrada.hour, minutes=f.hora_entrada.minute)
                    t_out = timedelta(hours=f.hora_salida.hour, minutes=f.hora_salida.minute)
                    total_seconds += (t_out - t_in).total_seconds()
                horas_por_weekday[wd] = total_seconds
            else:
                horas_por_weekday[wd] = 0

        total_teorico_sec = 0
        for day in range(1, num_days + 1):
            current_dt = datetime(anio, mes, day)
            total_teorico_sec += horas_por_weekday.get(current_dt.weekday(), 0)

        fichajes = Fichaje.query.filter(
            Fichaje.id_trabajador == user_id,
            Fichaje.fecha_hora >= start_date,
            Fichaje.fecha_hora <= end_date
        ).order_by(Fichaje.fecha_hora).all()

        total_trabajado_sec = 0
        pendientes = []

        for f in fichajes:
            if (f.tipo or "").strip().upper() == 'ENTRADA':
                pendientes.append(f)
            elif (f.tipo or "").strip().upper() == 'SALIDA' and pendientes:
                ent = pendientes.pop()
                total_trabajado_sec += (f.fecha_hora - ent.fecha_hora).total_seconds()

        horas_teoricas = round(total_teorico_sec / 3600, 2)
        horas_trabajadas = round(total_trabajado_sec / 3600, 2)
        saldo = round(horas_trabajadas - horas_teoricas, 2)

        return {
            "mes": start_date.strftime('%B %Y'),
            "teoricas": horas_teoricas,
            "trabajadas": horas_trabajadas,
            "saldo": saldo
        }


@blp.route("/fichar")
class Fichar(MethodView):
    @jwt_required()
    @blp.arguments(FichajeInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, fichaje_data):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)
        empresa = trabajador.empresa

        lat = fichaje_data.get("latitud")
        lon = fichaje_data.get("longitud")
        if lat is None or lon is None:
            abort(400, message="Faltan latitud/longitud.")

        _validar_distancia_empresa(empresa, lat, lon)
        return _crear_fichaje(trabajador, lat, lon)


@blp.route("/fichar-nfc")
class FicharNFC(MethodView):
    @jwt_required()
    @blp.arguments(FichajeNFCInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, nfc_data):
        """
        Fichaje NFC para app logueada:
        - Requiere JWT
        - Verifica UID con trabajador.codigo_nfc
        - Aplica misma lógica que /fichar
        """
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)
        empresa = trabajador.empresa

        uid_leido = _normalizar_uid(nfc_data.get("nfc_data"))
        lat = nfc_data.get("latitud")
        lon = nfc_data.get("longitud")

        if not uid_leido:
            abort(400, message="No se ha recibido nfc_data.")
        if lat is None or lon is None:
            abort(400, message="Faltan latitud/longitud.")

        uid_guardado = _normalizar_uid(getattr(trabajador, "codigo_nfc", None))
        if not uid_guardado:
            abort(400, message="No tienes NFC asignado. Contacta con RRHH.")

        uid_inv = _uid_invertido(uid_leido)
        if uid_leido != uid_guardado and uid_inv != uid_guardado:
            abort(403, message="NFC no coincide con tu usuario.")

        _validar_distancia_empresa(empresa, lat, lon)
        return _crear_fichaje(trabajador, lat, lon)


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


@blp.route("/fichajes-empleado/<int:empleado_id>")
class FichajesEmpleado(MethodView):
    @jwt_required()
    @blp.response(200, FichajeOutputSchema(many=True))
    def get(self, empleado_id):
        yo_id = get_jwt_identity()
        admin = Trabajador.query.get_or_404(yo_id)

        tiene_permiso, rol_detectado = es_admin_robusto(admin)

        print(
            f"DEBUG: /fichajes-empleado -> ID:{yo_id} Nombre:{admin.nombre} "
            f"RolRAW:'{admin.rol.nombre_rol if admin.rol else 'None'}' RolNORM:'{rol_detectado}' Acceso:{tiene_permiso}"
        )

        if not tiene_permiso:
            abort(403, message=f"Acceso denegado. Rol detectado: '{rol_detectado}'")

        if "SUPER" not in rol_detectado:
            empleado_objetivo = Trabajador.query.get_or_404(empleado_id)
            if empleado_objetivo.idEmpresa != admin.idEmpresa:
                abort(404, message="Empleado no encontrado en tu empresa.")

        return (
            Fichaje.query.filter_by(id_trabajador=empleado_id)
            .order_by(Fichaje.fecha_hora.desc())
            .limit(100)
            .all()
        )


@blp.route("/historial-admin/<int:id_trabajador>")
class HistorialAdmin(MethodView):
    @jwt_required()
    @blp.response(200, FichajeSchema(many=True))
    def get(self, id_trabajador):
        yo_id = get_jwt_identity()
        yo = Trabajador.query.get_or_404(yo_id)

        tiene_permiso, rol_detectado = es_admin_robusto(yo)

        print(
            f"DEBUG: /historial-admin -> ID:{yo_id} "
            f"RolRAW:'{yo.rol.nombre_rol if yo.rol else 'None'}' RolNORM:'{rol_detectado}'"
        )

        if not tiene_permiso:
            abort(403, message=f"Acceso denegado. Rol '{rol_detectado}' no autorizado.")

        return (
            Fichaje.query.filter_by(id_trabajador=id_trabajador)
            .order_by(desc(Fichaje.fecha_hora))
            .all()
        )

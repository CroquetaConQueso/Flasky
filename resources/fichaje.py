import math
import re
from datetime import datetime, timedelta, date

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

# Blueprint del módulo: controla fichajes (manual/NFC), resumen mensual y consultas.
blp = Blueprint("fichajes", __name__, description="Fichajes y control de presencia")

# Regex defensiva para validar UIDs en HEX puro.
_UID_RE = re.compile(r"^[0-9A-F]+$")


# ---------------------------------------------------------------------
# ROLES / PERMISOS
# ---------------------------------------------------------------------

def normalizar_rol(raw: str) -> str:
    """
    Normaliza el nombre de rol:
    - uppercase
    - elimina todo lo que no sea A-Z
    Ej: "Admin (RRHH)" -> "ADMINRRHH"
    """
    if not raw:
        return "SIN_ROL"
    return re.sub(r"[^A-Z]", "", raw.strip().upper())


def es_admin_robusto(trabajador):
    """
    Determina si un trabajador debe considerarse "admin" de forma robusta:
    - Evita None
    - Normaliza el rol
    - Busca palabras clave (ADMIN, JEFE, RRHH, etc.)
    Devuelve (is_admin: bool, rol_normalizado: str)
    """
    if not trabajador or not getattr(trabajador, "rol", None) or not getattr(trabajador.rol, "nombre_rol", None):
        return False, "SIN_ROL"
    rol_norm = normalizar_rol(trabajador.rol.nombre_rol)
    claves = ["ADMIN", "RESPONSABLE", "SUPER", "RRHH", "GERENTE", "JEFE", "ENCARGADO", "DIREC"]
    return any(k in rol_norm for k in claves), rol_norm


# ---------------------------------------------------------------------
# GEO / DISTANCIA
# ---------------------------------------------------------------------

def calcular_distancia(lat1, lon1, lat2, lon2):
    """
    Calcula distancia en metros entre dos coordenadas (Haversine).
    """
    R = 6371000  # radio medio tierra (m)
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


def _validar_distancia_empresa(empresa: Empresa, lat: float, lon: float):
    """
    Valida que el fichaje se hace dentro de un radio razonable.
    - Si la empresa no tiene lat/lon, no se aplica control.
    - Se usa (empresa.radio or 100) + 50 como tolerancia (m).
    """
    if not empresa:
        return

    # Si la empresa tiene coordenadas, exigimos coords del cliente.
    if empresa.latitud is not None and empresa.longitud is not None:
        if lat is None or lon is None:
            abort(400, message="Faltan coordenadas GPS para validar el fichaje.")

        distancia = calcular_distancia(lat, lon, empresa.latitud, empresa.longitud)
        radio_permitido = (empresa.radio or 100) + 50  # margen extra
        if distancia > radio_permitido:
            abort(403, message=f"Lejos de la empresa ({int(distancia)}m).")


# ---------------------------------------------------------------------
# NFC (UIDs)
# ---------------------------------------------------------------------

def _normalizar_uid(uid: str) -> str:
    """
    Convierte cualquier UID recibido a un formato canónico:
    - Uppercase
    - Sin 0x
    - Sin separadores (: - espacios)
    - Solo HEX (0-9A-F)
    """
    if not uid:
        return ""
    cleaned = re.sub(r"[^0-9A-F]", "", uid.strip().upper())
    if len(cleaned) % 2 == 1:
        cleaned = "0" + cleaned
    return cleaned


def _uid_es_valido(uid_hex: str) -> bool:
    """
    UID válido = HEX puro y no vacío.
    """
    return bool(uid_hex) and bool(_UID_RE.fullmatch(uid_hex))


def _uid_invertido(uid_hex: str) -> str:
    """
    Invierte el UID por bytes (endianness), por si el lector devuelve orden inverso.
    Ej: A1B2C3D4 -> D4C3B2A1
    """
    uid_hex = _normalizar_uid(uid_hex)
    if len(uid_hex) < 2:
        return uid_hex

    # Asegura longitud par (por seguridad, aunque _normalizar_uid ya lo hace)
    if len(uid_hex) % 2 == 1:
        uid_hex = "0" + uid_hex

    pares = [uid_hex[i:i + 2] for i in range(0, len(uid_hex), 2)]
    pares.reverse()
    return "".join(pares)



def _uids_equivalentes(uid_recibido_raw: str, uid_guardado_raw: str) -> bool:
    """
    Decide si el UID recibido equivale al guardado, tolerando:
    - separadores / 0x / mayúsculas
    - inversión por bytes (endianness)
    - ceros a la izquierda (dependiendo del lector)
    """
    recibido = _normalizar_uid(uid_recibido_raw)
    guardado = _normalizar_uid(uid_guardado_raw)

    if not _uid_es_valido(recibido) or not _uid_es_valido(guardado):
        return False

    # igualdad directa
    if recibido == guardado:
        return True

    # tolera ceros a la izquierda
    r0 = recibido.lstrip("0")
    g0 = guardado.lstrip("0")
    if r0 and g0 and r0 == g0:
        return True

    # inversión del recibido
    if _uid_invertido(recibido) == guardado:
        return True

    # por si el admin guardó invertido y el lector manda normal
    if recibido == _uid_invertido(guardado):
        return True

    return False


# ---------------------------------------------------------------------
# CÁLCULO DE HORARIO (resumen mensual)
# ---------------------------------------------------------------------

def _get_duration_seg(entrada, salida) -> int:
    """
    Duración en segundos entre dos horas (time).
    - Si cruza medianoche, suma 24h.
    """
    if not entrada or not salida:
        return 0
    d_entrada = datetime.combine(date.min, entrada)
    d_salida = datetime.combine(date.min, salida)
    diff = (d_salida - d_entrada).total_seconds()
    if diff < 0:
        diff += 86400
    return int(diff)


def _pair_punches_day(fichajes_day):
    """
    Empareja fichajes ENTRADA/SALIDA en un día para calcular segundos trabajados.
    Devuelve (worked_seconds, incomplete_flag).

    Regla:
    - Ignora tipos inválidos marcando el día como incompleto.
    - Si hay dos ENTRADA seguidas o dos SALIDA seguidas -> incompleto.
    - Si hay una SALIDA sin ENTRADA previa -> incompleto.
    - Si queda una ENTRADA abierta al final -> incompleto.
    """
    fichajes_day = sorted(fichajes_day, key=lambda f: f.fecha_hora)
    worked = 0
    incomplete = False
    last_in = None
    last_type = None

    for f in fichajes_day:
        t = (f.tipo or "").strip().upper()
        if t not in ("ENTRADA", "SALIDA"):
            incomplete = True
            continue

        if last_type == t:
            incomplete = True

        if t == "ENTRADA":
            last_in = f.fecha_hora
        else:
            if last_in is None:
                incomplete = True
            else:
                delta = int((f.fecha_hora - last_in).total_seconds())
                if delta <= 0:
                    incomplete = True
                else:
                    worked += delta
                last_in = None
        last_type = t

    if last_in is not None:
        incomplete = True

    return worked, incomplete


# ---------------------------------------------------------------------
# CREACIÓN DE FICHAJE (ENTRADA/SALIDA)
# ---------------------------------------------------------------------

def _crear_fichaje(trabajador: Trabajador, lat: float, lon: float):
    """
    Crea un fichaje alternando ENTRADA/SALIDA según el último fichaje.
    Controles:
    - Anti-doble click: si el último fichaje fue hace < 60s -> 429.
    - Si el último fue ENTRADA y han pasado > 16h -> genera incidencia OLVIDO (cierre automático)
      y abre una nueva ENTRADA (para no encadenar SALIDAS absurdas).
    """
    ultimo = (
        Fichaje.query.filter_by(id_trabajador=trabajador.id_trabajador)
        .order_by(Fichaje.fecha_hora.desc())
        .first()
    )

    tipo_nuevo = "ENTRADA"
    now = datetime.now()

    if ultimo:
        segundos = (now - ultimo.fecha_hora).total_seconds()

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
        fecha_hora=now
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def _procesar_fichaje_comun(user_id, lat, lon, nfc_data_raw=None):
    """
    Punto único de entrada para fichar (manual o NFC).

    Responsabilidades:
    1) Cargar trabajador + empresa.
    2) Validar NFC según política:
       - Si la empresa tiene NFC de oficina -> OBLIGATORIO y debe coincidir.
       - Si la empresa NO tiene NFC de oficina -> si llega NFC, se valida contra el NFC del trabajador (si existe).
    3) Validar distancia GPS respecto a la empresa.
    4) (Extra) Anti-doble lectura NFC: evita 2 requests seguidas al acercar la tarjeta.
    5) Crear el fichaje (ENTRADA/SALIDA) aplicando las reglas de _crear_fichaje().
    """
    trabajador = Trabajador.query.get_or_404(user_id)
    empresa = trabajador.empresa

    # --- 1) Validación NFC (modo "NFC de oficina" vs "NFC personal") ---

    # NFC de oficina guardado por el admin (si existe, será obligatorio para fichar desde app móvil)
    nfc_oficina_requerido = _normalizar_uid(getattr(empresa, "codigo_nfc_oficina", None))

    if nfc_oficina_requerido:
        # En modo "oficina": el cliente DEBE enviar un NFC y debe coincidir con el oficial.
        nfc_recibido = _normalizar_uid(nfc_data_raw)
        if not nfc_recibido:
            abort(400, message="Fichaje restringido: Debes escanear el punto NFC de la entrada.")

        # Algunos lectores devuelven el UID por bytes invertidos, por eso aceptamos ambas variantes.
        uid_inv = _uid_invertido(nfc_recibido)

        if nfc_recibido != nfc_oficina_requerido and uid_inv != nfc_oficina_requerido:
            abort(403, message="NFC Incorrecto. Escanea la etiqueta oficial de la entrada.")
    else:
        # En modo "personal": el NFC es opcional. Si llega, se valida contra el del trabajador.
        nfc_recibido = _normalizar_uid(nfc_data_raw)
        if nfc_recibido:
            uid_guardado = _normalizar_uid(getattr(trabajador, "codigo_nfc", None))
            uid_inv = _uid_invertido(nfc_recibido)

            # Si el trabajador no tiene NFC asignado, o no coincide (normal o invertido) => prohibido
            if not uid_guardado or (nfc_recibido != uid_guardado and uid_inv != uid_guardado):
                abort(403, message="Código NFC no válido o no asignado a este usuario.")

    # --- 2) Validación GPS (radio empresa) ---
    _validar_distancia_empresa(empresa, lat, lon)

    # --- 3) Extra: Anti-doble lectura NFC (evita 429 por acercar tarjeta y disparar 2 requests) ---
    # Solo aplica si la llamada viene con NFC (manual no se toca).
    if nfc_data_raw:
        ultimo = (
            Fichaje.query.filter_by(id_trabajador=trabajador.id_trabajador)
            .order_by(Fichaje.fecha_hora.desc())
            .first()
        )
        if ultimo:
            segundos = (datetime.now() - ultimo.fecha_hora).total_seconds()
            # Ventana pequeña: suficiente para rebotes NFC, sin molestar al usuario
            if segundos < 8:
                abort(429, message="Lectura repetida NFC. Espera un momento y vuelve a acercar la tarjeta.")

    # --- 4) Crear fichaje (ENTRADA/SALIDA) ---
    return _crear_fichaje(trabajador, lat, lon)


# ---------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------

@blp.route("/resumen")
class ResumenMensual(MethodView):
    """
    Resumen mensual:
    - horas teóricas según horario (Franja + Dia)
    - horas trabajadas emparejando ENTRADA/SALIDA
    - saldo = trabajadas - teóricas
    - marca días incompletos
    """
    @jwt_required()
    @blp.arguments(ResumenMensualQuerySchema, location="query")
    @blp.response(200, ResumenMensualOutputSchema)
    def get(self, args):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)

        now = datetime.now()
        mes = args.get("mes") or now.month
        anio = args.get("anio") or now.year

        # Sin horario asignado => no se puede computar teóricas.
        if not trabajador.idHorario:
            return {
                "mes": f"{mes:02d}/{anio}",
                "teoricas": 0.0,
                "trabajadas": 0.0,
                "saldo": 0.0,
                "teoricas_seg": 0,
                "trabajadas_seg": 0,
                "saldo_seg": 0,
                "dias_incompletos": [],
                "num_dias_incompletos": 0,
                "calculo_confiable": True
            }

        # Rango del mes [start_dt, end_dt)
        start_dt = datetime(anio, mes, 1)
        end_dt = datetime(anio + 1, 1, 1) if mes == 12 else datetime(anio, mes + 1, 1)

        # Incidencias aprobadas de ausencia que "anulan" las horas teóricas de esos días.
        TIPOS_AUSENCIA = {"VACACIONES", "BAJA", "ASUNTOS_PROPIOS"}
        incidencias_aprobadas = Incidencia.query.filter(
            Incidencia.id_trabajador == user_id,
            Incidencia.estado == "APROBADA",
            Incidencia.tipo.in_(TIPOS_AUSENCIA),
            Incidencia.fecha_inicio < end_dt.date(),
            Incidencia.fecha_fin >= start_dt.date()
        ).all()

        # Mapeo nombres de día a weekday (0=lunes..6=domingo)
        dias_semana = {
            0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
            4: "viernes", 5: "sabado", 6: "domingo"
        }
        nombre_to_weekday = {v: k for k, v in dias_semana.items()}
        dia_id_to_weekday = {}

        # Construye diccionario: idDia (DB) -> weekday (int)
        for d in Dia.query.all():
            key = (d.nombre or "").strip().lower()
            wd = nombre_to_weekday.get(key)
            if wd is not None:
                dia_id_to_weekday[d.id] = wd

        # Segundos teóricos por weekday, sumando las franjas del horario del trabajador
        segundos_teoricos_dia = {i: 0 for i in range(7)}
        for f in Franja.query.filter_by(id_horario=trabajador.idHorario).all():
            wd = dia_id_to_weekday.get(f.id_dia)
            if wd is not None:
                segundos_teoricos_dia[wd] += _get_duration_seg(f.hora_entrada, f.hora_salida)

        # Fichajes reales del mes
        fichajes = Fichaje.query.filter(
            Fichaje.id_trabajador == user_id,
            Fichaje.fecha_hora >= start_dt,
            Fichaje.fecha_hora < end_dt
        ).order_by(Fichaje.fecha_hora.asc()).all()

        # Agrupa fichajes por fecha
        fichajes_por_dia = {}
        for f in fichajes:
            fichajes_por_dia.setdefault(f.fecha_hora.date(), []).append(f)

        total_teorico_seg = 0
        total_trabajado_seg = 0
        dias_incompletos = []

        # Recorre día a día para computar teóricas y trabajadas
        curr = start_dt.date()
        while curr < end_dt.date():
            # Si hay ausencia aprobada, no suma horas teóricas ese día
            es_ausencia = any(inc.fecha_inicio <= curr <= inc.fecha_fin for inc in incidencias_aprobadas)
            if not es_ausencia:
                total_teorico_seg += segundos_teoricos_dia.get(curr.weekday(), 0)

            # Si hay fichajes, empareja ENTRADA/SALIDA
            punches = fichajes_por_dia.get(curr, [])
            if punches:
                worked, incomplete = _pair_punches_day(punches)
                total_trabajado_seg += worked
                if incomplete:
                    dias_incompletos.append(curr.isoformat())

            curr += timedelta(days=1)

        balance_seg = total_trabajado_seg - total_teorico_seg

        return {
            "mes": f"{mes:02d}/{anio}",
            "teoricas": round(total_teorico_seg / 3600, 2),
            "trabajadas": round(total_trabajado_seg / 3600, 2),
            "saldo": round(balance_seg / 3600, 2),

            # Extra: útil para app móvil (debug/fiabilidad/UX)
            "teoricas_seg": total_teorico_seg,
            "trabajadas_seg": total_trabajado_seg,
            "saldo_seg": balance_seg,
            "dias_incompletos": dias_incompletos,
            "num_dias_incompletos": len(dias_incompletos),
            "calculo_confiable": len(dias_incompletos) == 0
        }


@blp.route("/fichar")
class Fichar(MethodView):
    """
    Fichaje normal.
    Si la empresa exige NFC de oficina, este endpoint también lo validará si mandas nfc_data.
    (En tu app móvil, normalmente el fichaje manual manda nfc_data = null.)
    """
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
    """
    Fichaje vía NFC (mismo flujo, pero schema separado si lo necesitas en cliente).
    """
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
    """
    Devuelve los últimos 50 fichajes del usuario logueado.
    """
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
    """
    Consulta de fichajes de un empleado (admin).
    - Admin normal: solo empleados de su empresa
    - SUPER: puede consultar cross-empresa
    """
    @jwt_required()
    @blp.response(200, FichajeOutputSchema(many=True))
    def get(self, empleado_id):
        yo = Trabajador.query.get_or_404(get_jwt_identity())

        ok, rol = es_admin_robusto(yo)
        if not ok:
            abort(403, message="No eres admin.")

        target = Trabajador.query.get_or_404(empleado_id)

        # Si no es de la misma empresa y no es SUPER, se camufla como 404 (no filtra existencia)
        if target.idEmpresa != yo.idEmpresa and "SUPER" not in rol:
            abort(404, message="Empleado no encontrado.")

        return (
            Fichaje.query
            .filter_by(id_trabajador=empleado_id)
            .order_by(Fichaje.fecha_hora.desc())
            .limit(100)
            .all()
        )

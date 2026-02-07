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
    FichajeNFCInputSchema
)

blp = Blueprint("fichajes", __name__, description="Fichajes y Control de Presencia")

# =========================================================
# HELPERS (Lógica Pura)
# =========================================================

def normalizar_rol(raw: str) -> str:
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
    return uid.strip().upper().replace(":", "").replace("-", "").replace(" ", "")

def _uid_invertido(uid_hex: str) -> str:
    uid_hex = _normalizar_uid(uid_hex)
    if len(uid_hex) < 2:
        return uid_hex
    pares = [uid_hex[i:i+2] for i in range(0, len(uid_hex), 2)]
    pares.reverse()
    return "".join(pares)

def _validar_distancia_empresa(empresa: Empresa, lat: float, lon: float):
    if not empresa:
        return
    if empresa.latitud and empresa.longitud:
        distancia = calcular_distancia(lat, lon, empresa.latitud, empresa.longitud)
        radio_permitido = (empresa.radio or 100) + 50 # Margen extra GPS
        if distancia > radio_permitido:
            abort(403, message=f"Lejos de la empresa ({int(distancia)}m).")

def _crear_fichaje(trabajador: Trabajador, lat: float, lon: float):
    ultimo_fichaje = (
        Fichaje.query.filter_by(id_trabajador=trabajador.id_trabajador)
        .order_by(Fichaje.fecha_hora.desc())
        .first()
    )

    tipo_nuevo = "ENTRADA"

    if ultimo_fichaje:
        segundos = (datetime.now() - ultimo_fichaje.fecha_hora).total_seconds()
        if segundos < 60:
            abort(429, message="Espera un minuto para volver a fichar.")

        if (ultimo_fichaje.tipo or "").strip().upper() == "ENTRADA":
            horas = segundos / 3600
            if horas > 16:
                # Incidencia automática por olvido
                inc = Incidencia(
                    id_trabajador=trabajador.id_trabajador,
                    tipo='OLVIDO',
                    fecha_inicio=ultimo_fichaje.fecha_hora.date(),
                    fecha_fin=ultimo_fichaje.fecha_hora.date(),
                    comentario_trabajador=f"Autogenerada: Turno abierto de {int(horas)}h.",
                    estado='PENDIENTE',
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

# --- LÓGICA CENTRAL DE FICHAJE (NUEVA) ---
def _procesar_fichaje_comun(user_id, lat, lon, nfc_data_raw=None):
    """
    Función helper que contiene toda la lógica de validación y creación,
    pero SIN decoradores web para evitar conflictos.
    """
    trabajador = Trabajador.query.get_or_404(user_id)
    empresa = trabajador.empresa

    # Validación NFC si se proporciona
    nfc_recibido = _normalizar_uid(nfc_data_raw)
    if nfc_recibido:
        # Recuperamos el UID de la base de datos de forma segura
        uid_guardado = _normalizar_uid(getattr(trabajador, "codigo_nfc", None))
        
        # Generamos la versión invertida por si el lector lee little-endian
        uid_inv = _uid_invertido(nfc_recibido)

        # Si el usuario no tiene tarjeta asignada O no coincide ninguna versión
        if not uid_guardado or (nfc_recibido != uid_guardado and uid_inv != uid_guardado):
            abort(403, message="Código NFC no válido o no asignado a este usuario.")

    # Validaciones comunes
    _validar_distancia_empresa(empresa, lat, lon)
    return _crear_fichaje(trabajador, lat, lon)

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

        # 1. Calcular teóricas
        dias_semana = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}
        horas_por_weekday = {}
        for wd, nombre in dias_semana.items():
            dia_db = Dia.query.filter_by(nombre=nombre).first()
            if dia_db:
                franjas = Franja.query.filter_by(id_horario=trabajador.idHorario, id_dia=dia_db.id).all()
                sec = sum([(timedelta(hours=f.hora_salida.hour, minutes=f.hora_salida.minute) - 
                            timedelta(hours=f.hora_entrada.hour, minutes=f.hora_entrada.minute)).total_seconds() for f in franjas])
                horas_por_weekday[wd] = sec
            else:
                horas_por_weekday[wd] = 0

        total_teorico = sum([horas_por_weekday.get(datetime(anio, mes, d).weekday(), 0) for d in range(1, num_days+1)])

        # 2. Calcular reales
        fichajes = Fichaje.query.filter(
            Fichaje.id_trabajador == user_id,
            Fichaje.fecha_hora >= start_date,
            Fichaje.fecha_hora <= end_date
        ).order_by(Fichaje.fecha_hora).all()

        total_trabajado = 0
        pendientes = []
        for f in fichajes:
            if f.tipo == 'ENTRADA':
                pendientes.append(f)
            elif f.tipo == 'SALIDA' and pendientes:
                ent = pendientes.pop()
                total_trabajado += (f.fecha_hora - ent.fecha_hora).total_seconds()

        return {
            "mes": start_date.strftime('%B %Y'),
            "teoricas": round(total_teorico / 3600, 2),
            "trabajadas": round(total_trabajado / 3600, 2),
            "saldo": round((total_trabajado - total_teorico) / 3600, 2)
        }

@blp.route("/fichar")
class Fichar(MethodView):
    @jwt_required()
    @blp.arguments(FichajeInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, data):
        """Fichaje manual (GPS)"""
        user_id = get_jwt_identity()
        return _procesar_fichaje_comun(
            user_id,
            data.get("latitud"),
            data.get("longitud"),
            data.get("nfc_data") # Opcional aquí
        )

@blp.route("/fichar-nfc")
class FicharNFC(MethodView):
    @jwt_required()
    @blp.arguments(FichajeNFCInputSchema)
    @blp.response(201, FichajeOutputSchema)
    def post(self, data):
        """Fichaje exclusivo NFC"""
        user_id = get_jwt_identity()
        # Llamamos a la lógica compartida, NO al endpoint decorado
        return _procesar_fichaje_comun(
            user_id,
            data.get("latitud"),
            data.get("longitud"),
            data.get("nfc_data") # Obligatorio por schema, se pasa a la lógica
        )

@blp.route("/mis-fichajes")
class MisFichajes(MethodView):
    @jwt_required()
    @blp.response(200, FichajeOutputSchema(many=True))
    def get(self):
        user_id = get_jwt_identity()
        return Fichaje.query.filter_by(id_trabajador=user_id).order_by(Fichaje.fecha_hora.desc()).limit(50).all()

@blp.route("/fichajes-empleado/<int:empleado_id>")
class FichajesEmpleado(MethodView):
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
            
        return Fichaje.query.filter_by(id_trabajador=empleado_id).order_by(Fichaje.fecha_hora.desc()).limit(100).all()
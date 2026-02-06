import math
import calendar
import re
from datetime import datetime, timedelta
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc

from extensions import db
from models import Trabajador, Fichaje, Empresa, Incidencia, Dia, Franja, Rol
from schemas import FichajeInputSchema, FichajeOutputSchema, ResumenMensualQuerySchema, ResumenMensualOutputSchema, FichajeSchema

blp = Blueprint("fichajes", __name__, description="Fichajes y Control de Presencia")

# --- FUNCIONES AUXILIARES ROBUSTAS ---

def normalizar_rol(raw: str) -> str:
    """Elimina todo lo que no sea letra A-Z y pasa a mayúsculas."""
    if not raw:
        return "SIN_ROL"
    # mayúsculas + quitar espacios + quitar puntos/guiones/etc (solo letras A-Z)
    return re.sub(r'[^A-Z]', '', raw.strip().upper())

def es_admin_robusto(trabajador):
    """
    Analiza el rol del trabajador y devuelve (TienePermiso, RolDetectado).
    Acepta variaciones como 'RR.HH.', 'Admin ', 'Jefe-Tienda'.
    """
    if not trabajador or not getattr(trabajador, "rol", None) or not getattr(trabajador.rol, "nombre_rol", None):
        return False, "SIN_ROL"

    rol_norm = normalizar_rol(trabajador.rol.nombre_rol)

    # Lista de palabras clave que otorgan poder
    claves = ["ADMIN", "RESPONSABLE", "SUPER", "RRHH", "GERENTE", "JEFE", "ENCARGADO", "DIREC"]
    
    # Si el rol normalizado contiene alguna de las claves, tiene permiso
    tiene_poder = any(k in rol_norm for k in claves)

    return tiene_poder, rol_norm

def calcular_distancia(lat1, lon1, lat2, lon2):
    # Fórmula de Haversine para calcular distancia entre coordenadas
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

# --- ENDPOINTS ---

@blp.route("/resumen")
class ResumenMensual(MethodView):
    @jwt_required()
    @blp.arguments(ResumenMensualQuerySchema, location="query")
    @blp.response(200, ResumenMensualOutputSchema)
    def get(self, args):
        """Obtener resumen de horas (Teóricas vs Reales) del mes."""
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)

        # Determinar mes y año (por defecto, los actuales)
        now = datetime.now()
        mes = args.get("mes") or now.month
        anio = args.get("anio") or now.year

        if not trabajador.idHorario:
            # Si no tiene horario, devolvemos 0 en todo para evitar errores
            return {
                "mes": f"{mes}/{anio}",
                "teoricas": 0.0,
                "trabajadas": 0.0,
                "saldo": 0.0
            }

        # 1. Definir rango del mes
        _, num_days = calendar.monthrange(anio, mes)
        start_date = datetime(anio, mes, 1)
        end_date = datetime(anio, mes, num_days, 23, 59, 59)

        # 2. Calcular Horas Teóricas
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
            wd = current_dt.weekday()
            total_teorico_sec += horas_por_weekday.get(wd, 0)

        # 3. Calcular Horas Reales (Fichajes)
        fichajes = Fichaje.query.filter(
            Fichaje.id_trabajador == user_id,
            Fichaje.fecha_hora >= start_date,
            Fichaje.fecha_hora <= end_date
        ).order_by(Fichaje.fecha_hora).all()

        total_trabajado_sec = 0
        pendientes = []

        for f in fichajes:
            if f.tipo == 'ENTRADA':
                pendientes.append(f)
            elif f.tipo == 'SALIDA':
                if pendientes:
                    ent = pendientes.pop()
                    delta = (f.fecha_hora - ent.fecha_hora).total_seconds()
                    total_trabajado_sec += delta

        # 4. Formatear respuesta
        horas_teoricas = round(total_teorico_sec / 3600, 2)
        horas_trabajadas = round(total_trabajado_sec / 3600, 2)
        saldo = round(horas_trabajadas - horas_teoricas, 2)
        nombre_mes = start_date.strftime('%B %Y')

        return {
            "mes": nombre_mes,
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

        if not empresa:
            abort(400, message="El trabajador no tiene empresa asignada.")

        if empresa.latitud and empresa.longitud:
            distancia = calcular_distancia(
                fichaje_data["latitud"],
                fichaje_data["longitud"],
                empresa.latitud,
                empresa.longitud
            )

            radio_permitido = (empresa.radio or 100) + 10

            if distancia > radio_permitido:
                abort(403, message=f"Estás demasiado lejos de la empresa ({int(distancia)}m). Acércate para fichar.")

        ultimo_fichaje = (
            Fichaje.query.filter_by(id_trabajador=user_id)
            .order_by(Fichaje.fecha_hora.desc())
            .first()
        )

        tipo_nuevo = "ENTRADA"

        if ultimo_fichaje:
            segundos_transcurridos = (datetime.now() - ultimo_fichaje.fecha_hora).total_seconds()

            # Bloqueo para evitar dobles clicks accidentales
            if segundos_transcurridos < 60:
                abort(429, message="Ya has fichado hace un momento. Espera un minuto.")

            if ultimo_fichaje.tipo == "ENTRADA":
                horas_transcurridas = segundos_transcurridos / 3600

                # Detección de olvido de salida del día anterior (Zombie)
                if horas_transcurridas > 16:
                    nueva_incidencia = Incidencia(
                        id_trabajador=user_id,
                        tipo='OLVIDO',
                        fecha_inicio=ultimo_fichaje.fecha_hora.date(),
                        fecha_fin=ultimo_fichaje.fecha_hora.date(),
                        comentario_trabajador=f"Autogenerada: Se detectó un turno abierto de {int(horas_transcurridas)} horas.",
                        estado='PENDIENTE',
                        comentario_admin="Detectado por el sistema al fichar al día siguiente."
                    )
                    db.session.add(nueva_incidencia)
                    # Mantenemos tipo_nuevo = 'ENTRADA' para iniciar el nuevo turno correctamente
                else:
                    tipo_nuevo = "SALIDA"

        nuevo_fichaje = Fichaje(
            id_trabajador=user_id,
            latitud=fichaje_data["latitud"],
            longitud=fichaje_data["longitud"],
            tipo=tipo_nuevo,
            fecha_hora=datetime.now()
        )

        db.session.add(nuevo_fichaje)
        db.session.commit()

        return nuevo_fichaje

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
        """(Admin) Obtener historial de fichajes de otro empleado"""
        yo_id = get_jwt_identity()
        admin = Trabajador.query.get_or_404(yo_id)

        # --- LOGICA ROBUSTA CON TRAZAS ---
        tiene_permiso, rol_detectado = es_admin_robusto(admin)

        print(f"DEBUG: /fichajes-empleado -> ID: {yo_id}, Nombre: {admin.nombre}, Rol RAW: '{admin.rol.nombre_rol if admin.rol else 'None'}', Rol NORM: '{rol_detectado}', Acceso: {tiene_permiso}")

        if not tiene_permiso:
            # Incluimos el rol detectado en el mensaje de error para depurar en el cliente
            abort(403, message=f"Acceso denegado. Se requieren permisos de Admin. Rol detectado: '{rol_detectado}'")

        # Verificar que el empleado objetivo pertenece a la misma empresa
        # Si es SUPER, podría saltarse esta restricción si se desea, pero por seguridad se mantiene
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

        # Usamos la misma lógica robusta aquí también
        tiene_permiso, rol_detectado = es_admin_robusto(yo)

        print(f"DEBUG: /historial-admin -> ID: {yo_id}, Rol RAW: '{yo.rol.nombre_rol if yo.rol else 'None'}', Rol NORM: '{rol_detectado}'")

        if not tiene_permiso:
             abort(403, message=f"Acceso denegado. Tu rol '{rol_detectado}' no tiene permisos suficientes.")

        # Obtener fichajes del empleado solicitado
        fichajes = Fichaje.query.filter_by(id_trabajador=id_trabajador)\
            .order_by(desc(Fichaje.fecha_hora)).all()
            
        return fichajes
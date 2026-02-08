import random
import string
import sys
from datetime import datetime, time as dtime, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import or_, func

from extensions import db
from models import Trabajador, Fichaje, Dia, Franja
from schemas import UserLoginSchema, PasswordResetSchema, ChangePasswordSchema, FcmTokenSchema, ResetPasswordRequestSchema
from utils.email_sender import enviar_correo_password


blp = Blueprint("auth", __name__, description="Autenticacion y Tokens")

# Mapa weekday() -> nombre de día en BD (IMPORTANTE: coincide con tu tabla Dia.nombre)
DIAS_SEMANA = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo"
}

# Margen para no avisar si aún es “temprano” respecto a la hora de entrada
GRACE_MINUTES = 10


# ------------------------------
# HELPERS: Recordatorio de fichaje
# ------------------------------

def _get_franjas_hoy(trabajador: Trabajador, hoy_fecha):
    """Devuelve lista de franjas de HOY para el horario del trabajador."""
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
    """True si existe ENTRADA hoy (rango 00:00:00 - 23:59:59.999999)."""
    inicio_dia = datetime.combine(hoy_fecha, dtime.min)
    fin_dia = datetime.combine(hoy_fecha, dtime.max)

    fichaje_hoy = Fichaje.query.filter(
        Fichaje.id_trabajador == trabajador.id_trabajador,
        func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
        Fichaje.fecha_hora >= inicio_dia,
        Fichaje.fecha_hora <= fin_dia
    ).first()

    return fichaje_hoy is not None


def _debe_avisar_fichaje(trabajador: Trabajador):
    """
    Devuelve (debe_avisar, titulo, mensaje, trabaja_hoy, hora_entrada_str)

    Avisamos si:
      - hoy trabaja (tiene franjas hoy)
      - ya pasó la hora de entrada (+ GRACE_MINUTES)
      - y NO hay ENTRADA hoy

    Nota: Si no hay hora_entrada en BD, NO avisamos (evita falsos positivos).
    """
    ahora = datetime.now()
    hoy_fecha = ahora.date()

    franjas = _get_franjas_hoy(trabajador, hoy_fecha)
    if not franjas:
        return (False, None, None, False, None)

    # Si hay varias franjas, usamos la hora_entrada más temprana
    hora_entrada_min = min((f.hora_entrada for f in franjas if f.hora_entrada), default=None)
    hora_entrada_str = hora_entrada_min.strftime("%H:%M") if hora_entrada_min else None

    if not hora_entrada_min:
        return (False, None, None, True, None)

    limite_aviso = datetime.combine(hoy_fecha, hora_entrada_min) + timedelta(minutes=GRACE_MINUTES)

    # Aún es pronto -> no avisamos
    if ahora < limite_aviso:
        return (False, None, None, True, hora_entrada_str)

    # Si ya fichó entrada -> no avisamos
    if _tiene_entrada_hoy(trabajador, hoy_fecha):
        return (False, None, None, True, hora_entrada_str)

    titulo = "⚠️ ¡No has fichado!"
    mensaje = (
        f"Hola {trabajador.nombre}, hoy trabajas y no consta tu ENTRADA."
        + (f" (Hora entrada: {hora_entrada_str})" if hora_entrada_str else "")
    )
    return (True, titulo, mensaje, True, hora_entrada_str)


# ------------------------------
# ENDPOINT: /login
# ------------------------------

@blp.route("/login")
class Login(MethodView):
    @blp.arguments(UserLoginSchema)
    def post(self, user_data):
        # Log para depuración (en stderr para que lo recoja el server log)
        print(f"[LOGIN] Intento de acceso raw: {user_data.get('nif')}", file=sys.stderr)

        ident_raw = (user_data.get("nif") or "").strip().upper()
        password_raw = user_data.get("password") or ""

        # Respuesta uniforme (no filtramos si existe usuario o no)
        if not ident_raw or not password_raw:
            abort(401, message="Credenciales incorrectas")

        # Login por NIF o Email (case-insensitive + trim)
        trabajador = Trabajador.query.filter(
            or_(
                func.upper(func.trim(Trabajador.nif)) == ident_raw,
                func.upper(func.trim(Trabajador.email)) == ident_raw
            )
        ).first()

        if not trabajador:
            print(f"[LOGIN] Error: Usuario '{ident_raw}' NO encontrado", file=sys.stderr)
            abort(401, message="Credenciales incorrectas")

        if not trabajador.check_password(password_raw):
            print(f"[LOGIN] Error: Password incorrecto para {trabajador.nombre}", file=sys.stderr)
            abort(401, message="Credenciales incorrectas")

        print(f"[LOGIN] Éxito: {trabajador.nombre} ha entrado.", file=sys.stderr)

        # --- Recordatorio al loguear (si hoy trabaja y no tiene ENTRADA, y ya pasó el margen) ---
        recordatorio = {"avisar": False}

        try:
            debe_avisar, titulo, mensaje, _, _ = _debe_avisar_fichaje(trabajador)
            if debe_avisar:
                recordatorio = {
                    "avisar": True,
                    "titulo": titulo,
                    "mensaje": mensaje
                }
                print(f"[LOGIN] ALERTA: {trabajador.nombre} NO tiene ENTRADA hoy.", file=sys.stderr)

                # Si quieres push aquí (opcional):
                # if trabajador.fcm_token:
                #     enviar_notificacion_push(trabajador.fcm_token, titulo, mensaje)

        except Exception as e:
            # No debe romper login por un fallo de recordatorio
            print(f"[LOGIN] Error calculando recordatorio (no crítico): {e}", file=sys.stderr)

        # Token JWT: identidad = id_trabajador
        access_token = create_access_token(identity=str(trabajador.id_trabajador))

        return {
            "access_token": access_token,
            "id_trabajador": trabajador.id_trabajador,
            "nombre": trabajador.nombre,
            "rol": trabajador.rol.nombre_rol if trabajador.rol else "Empleado",
            "id_empresa": trabajador.idEmpresa,
            "recordatorio": recordatorio
        }


# ------------------------------
# ENDPOINT: /reset-password
# ------------------------------

@blp.route("/reset-password")
class PasswordReset(MethodView):
    @blp.arguments(PasswordResetSchema)
    def post(self, user_data):
        # Acepta "identificador" (tu app), pero también soporta "email" o "nif"
        raw_identificador = user_data.get("identificador") or user_data.get("email") or user_data.get("nif")
        if not raw_identificador:
            abort(422, message="Debes proporcionar tu Email o NIF.")

        identificador = raw_identificador.strip()
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.email.in_(posibles_valores),
                Trabajador.nif.in_(posibles_valores)
            )
        ).first()

        # Respuesta “segura”: no confirmamos si existe o no
        if not trabajador:
            return {"message": "Si los datos son correctos, recibirás un correo"}, 200

        if not trabajador.email:
            return {"message": "Este usuario no tiene email configurado"}, 400

        # Generar nueva contraseña simple (8 chars) y enviarla
        caracteres = string.ascii_letters + string.digits
        nueva_pass = ''.join(random.choice(caracteres) for _ in range(8))

        trabajador.set_password(nueva_pass)
        db.session.commit()

        enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)
        return {"message": "Contraseña enviada al correo"}, 200


# ------------------------------
# ENDPOINT: /change-password
# ------------------------------

@blp.route("/change-password")
class ChangePassword(MethodView):
    @jwt_required()
    @blp.arguments(ChangePasswordSchema)
    def post(self, user_data):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if not trabajador:
            abort(404, message="Usuario no encontrado")

        if not trabajador.check_password(user_data["current_password"]):
            abort(401, message="La contraseña actual es incorrecta")

        if len(user_data["new_password"]) < 6:
            abort(400, message="La contraseña nueva es demasiado corta")

        trabajador.set_password(user_data["new_password"])
        db.session.commit()
        return {"message": "Contraseña actualizada correctamente"}, 200


# ------------------------------
# ENDPOINT: /save-fcm-token
# ------------------------------

@blp.route("/save-fcm-token")
class SaveFcmToken(MethodView):
    @jwt_required()
    @blp.arguments(FcmTokenSchema)
    def post(self, token_data):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if trabajador:
            trabajador.fcm_token = token_data["token"]
            db.session.commit()
            return {"message": "Token guardado correctamente"}, 200

        abort(404, message="Usuario no encontrado")

# ENDPOINT REST PASSWORD
@blp.route("/reset-password")
class ResetPassword(MethodView):
    @blp.arguments(ResetPasswordRequestSchema)
    def post(self, user_data):
        """
        Solicita un email de restablecimiento de contraseña (APP).
        """
        email = user_data.get("email")

        # Buscamos al trabajador
        trabajador = Trabajador.query.filter_by(email=email).first()

        # Respuesta neutra por seguridad (si no existe, no damos error, solo decimos OK)
        if not trabajador:
            return {"message": "Si el correo existe, se ha enviado el enlace."}

        try:
            # Genera token
            token = generar_token_reset(trabajador.id_trabajador)

            # Crea link que apunta a la web de la app
            # Usamos _external=True para que ponga https://dominio.com/...
            link = url_for("auth_web.reset_password_confirm", token=token, _external=True)

            # Envia email
            enviado = enviar_correo_password(trabajador.email, trabajador.nombre, link)

            if enviado:
                return {"message": "Correo enviado correctamente."}
            else:
                abort(500, message="Error al enviar el correo electrónico.")

        except Exception as e:
            print(f"Error en API Reset: {e}")
            abort(500, message="Error interno del servidor")

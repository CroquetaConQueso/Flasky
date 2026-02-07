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
from schemas import (
    UserLoginSchema,
    PasswordResetSchema,
    ChangePasswordSchema,
    FcmTokenSchema
)
from utils.email_sender import enviar_correo_password

blp = Blueprint("auth", __name__, description="Autenticacion y Tokens")

DIAS_SEMANA = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo"
}

GRACE_MINUTES = 10


# =========================================================
# HELPERS RECORDATORIO (LOGIN)
# =========================================================
def _get_franjas_hoy(trabajador: Trabajador, hoy_fecha):
    if not trabajador.idHorario:
        return []

    nombre_dia = DIAS_SEMANA.get(hoy_fecha.weekday())
    if not nombre_dia:
        return []

    dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
    if not dia_db:
        return []

    return Franja.query.filter_by(
        id_horario=trabajador.idHorario,
        id_dia=dia_db.id
    ).all()


def _tiene_entrada_hoy(trabajador: Trabajador, hoy_fecha):
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
    ahora = datetime.now()
    hoy_fecha = ahora.date()

    franjas = _get_franjas_hoy(trabajador, hoy_fecha)
    if not franjas:
        return (False, None, None, False, None)

    hora_entrada_min = min((f.hora_entrada for f in franjas if f.hora_entrada), default=None)
    hora_entrada_str = hora_entrada_min.strftime("%H:%M") if hora_entrada_min else None

    if not hora_entrada_min:
        return (False, None, None, True, None)

    limite_aviso = datetime.combine(hoy_fecha, hora_entrada_min) + timedelta(minutes=GRACE_MINUTES)
    if ahora < limite_aviso:
        return (False, None, None, True, hora_entrada_str)

    if _tiene_entrada_hoy(trabajador, hoy_fecha):
        return (False, None, None, True, hora_entrada_str)

    titulo = "⚠️ ¡No has fichado!"
    mensaje = (
        f"Hola {trabajador.nombre}, hoy trabajas y no consta tu ENTRADA."
        + (f" (Hora entrada: {hora_entrada_str})" if hora_entrada_str else "")
    )
    return (True, titulo, mensaje, True, hora_entrada_str)


# =========================================================
# ENDPOINTS AUTH
# =========================================================
@blp.route("/login")
class Login(MethodView):
    @blp.arguments(UserLoginSchema)
    def post(self, user_data):
        print(f"[LOGIN] Intento de acceso raw: {user_data.get('nif')}", file=sys.stderr)

        ident_raw = (user_data.get("nif") or "").strip().upper()
        password_raw = user_data.get("password") or ""

        if not ident_raw or not password_raw:
            abort(401, message="Credenciales incorrectas")

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

        recordatorio = {"avisar": False}
        try:
            debe, titulo, msg, _, _ = _debe_avisar_fichaje(trabajador)
            if debe:
                recordatorio = {"avisar": True, "titulo": titulo, "mensaje": msg}
        except Exception as e:
            print(f"[LOGIN] Error calculando recordatorio (no crítico): {e}", file=sys.stderr)

        # ✅ Identity como INT (evita bugs raros en get_jwt_identity/query.get)
        access_token = create_access_token(identity=trabajador.id_trabajador)

        return {
            "access_token": access_token,
            "id_trabajador": trabajador.id_trabajador,
            "nombre": trabajador.nombre,
            "rol": trabajador.rol.nombre_rol if trabajador.rol else "Empleado",
            "id_empresa": trabajador.idEmpresa,
            "recordatorio": recordatorio
        }


@blp.route("/me")
class Me(MethodView):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)

        return {
            "id_trabajador": trabajador.id_trabajador,
            "nif": trabajador.nif,
            "nombre": trabajador.nombre,
            "apellidos": getattr(trabajador, "apellidos", None),
            "email": trabajador.email,
            "telef": getattr(trabajador, "telef", None),
            "rol": trabajador.rol.nombre_rol if trabajador.rol else "Empleado",
            "id_empresa": trabajador.idEmpresa,
            "id_horario": getattr(trabajador, "idHorario", None),
            "codigo_nfc": getattr(trabajador, "codigo_nfc", None),
        }


@blp.route("/server-time")
class ServerTime(MethodView):
    def get(self):
        now = datetime.now()
        return {
            "iso": now.isoformat(),
            "timestamp": int(now.timestamp())
        }


@blp.route("/reset-password")
class PasswordReset(MethodView):
    @blp.arguments(PasswordResetSchema)
    def post(self, user_data):
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

        if not trabajador:
            return {"message": "Si los datos son correctos, recibirás un correo"}, 200

        if not trabajador.email:
            return {"message": "Este usuario no tiene email configurado"}, 400

        caracteres = string.ascii_letters + string.digits
        nueva_pass = ''.join(random.choice(caracteres) for _ in range(8))

        trabajador.set_password(nueva_pass)
        db.session.commit()

        enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)
        return {"message": "Contraseña enviada al correo"}, 200


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

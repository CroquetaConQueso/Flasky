import random
import string
import sys
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import or_

from extensions import db
from models import Trabajador, Fichaje
from schemas import UserLoginSchema, PasswordResetSchema, ChangePasswordSchema, FcmTokenSchema
from utils.email_sender import enviar_correo_password
from utils.firebase_sender import enviar_notificacion_push

blp = Blueprint("auth", __name__, description="Autenticacion y Tokens")

@blp.route("/login")
class Login(MethodView):
    @blp.arguments(UserLoginSchema)
    def post(self, user_data):
        print(f"[LOGIN] Intento de acceso: {user_data.get('nif')}", file=sys.stderr)

        identificador = user_data["nif"].strip()
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.nif.in_(posibles_valores),
                Trabajador.email.in_(posibles_valores)
            )
        ).first()

        if not trabajador or not trabajador.check_password(user_data["password"]):
            abort(401, message="Credenciales incorrectas")

        print(f"[LOGIN] Éxito: {trabajador.nombre} ha entrado.", file=sys.stderr)

        # --- Calcular recordatorio (para que la APP lo muestre LOCALMENTE) ---
        recordatorio = {"avisar": False}

        try:
            now = datetime.now(TZ).replace(tzinfo=None)
            hoy = now.date()
            nombre_dia = DIAS_SEMANA[hoy.weekday()]

            if trabajador.idHorario:
                dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
                if dia_db:
                    franjas_hoy = Franja.query.filter_by(
                        id_horario=trabajador.idHorario,
                        id_dia=dia_db.id
                    ).all()

                    if franjas_hoy:
                        # Hora de entrada más temprana + margen
                        hora_entrada_min = min(f.hora_entrada for f in franjas_hoy)
                        hora_limite = datetime.combine(hoy, hora_entrada_min) + timedelta(minutes=MARGEN_MINUTOS)

                        # Solo avisar si ya pasó la hora de entrada (+margen)
                        if now >= hora_limite:
                            inicio_dia = datetime.combine(hoy, dtime.min)
                            fin_dia = datetime.combine(hoy, dtime.max)

                            fichaje_hoy = Fichaje.query.filter(
                                Fichaje.id_trabajador == trabajador.id_trabajador,
                                func.upper(func.trim(Fichaje.tipo)) == "ENTRADA",
                                Fichaje.fecha_hora >= inicio_dia,
                                Fichaje.fecha_hora <= fin_dia
                            ).first()

                            if not fichaje_hoy:
                                recordatorio = {
                                    "avisar": True,
                                    "titulo": "⚠️ ¡No has fichado!",
                                    "mensaje": f"Hola {trabajador.nombre}, hoy trabajas y no consta tu entrada. Regístrala cuanto antes."
                                }
                        # else: aún no toca -> no avisar
        except Exception as e:
            print(f"[LOGIN] Recordatorio: error no crítico: {e}", file=sys.stderr)

        access_token = create_access_token(identity=str(trabajador.id_trabajador))

        return {
            "access_token": access_token,
            "id_trabajador": trabajador.id_trabajador,
            "nombre": trabajador.nombre,
            "rol": trabajador.rol.nombre_rol if trabajador.rol else "Empleado",
            "id_empresa": trabajador.idEmpresa,
            "recordatorio": recordatorio
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
        nueva_pass = ''.join(random.choice(caracteres) for i in range(8))

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
import random
import string
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import or_

from extensions import db
from models import Trabajador
# IMPORTANTE: Asegúrate de importar el nuevo esquema aquí
from schemas import UserLoginSchema, PasswordResetSchema, ChangePasswordSchema
from utils.email_sender import enviar_correo_password

blp = Blueprint("auth", __name__, description="Autenticacion y Tokens")

@blp.route("/login")
class Login(MethodView):
    @blp.arguments(UserLoginSchema)
    def post(self, user_data):
        identificador = user_data["nif"].strip()

        # Búsqueda Robusta (Mayúsculas/Minúsculas)
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.nif.in_(posibles_valores),
                Trabajador.email.in_(posibles_valores)
            )
        ).first()

        if trabajador and trabajador.check_password(user_data["password"]):
            # Crear token
            access_token = create_access_token(identity=str(trabajador.id_trabajador))

            # Devolver token y datos básicos del usuario
            return {
                "access_token": access_token,
                "id_trabajador": trabajador.id_trabajador,
                "nombre": trabajador.nombre,
                "rol": trabajador.rol.nombre_rol if trabajador.rol else "Empleado",
                "id_empresa": trabajador.idEmpresa
            }

        abort(401, message="Credenciales incorrectas")

@blp.route("/reset-password")
class PasswordReset(MethodView):
    @blp.arguments(PasswordResetSchema)
    def post(self, user_data):
        # LÓGICA FLEXIBLE: Buscamos el dato en cualquier campo posible
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

        # Mensaje genérico de éxito por seguridad
        if not trabajador:
            return {"message": "Si los datos son correctos, recibirás un correo"}, 200

        if not trabajador.email:
            return {"message": "Este usuario no tiene email configurado"}, 400

        # Generar nueva contraseña aleatoria
        caracteres = string.ascii_letters + string.digits
        nueva_pass = ''.join(random.choice(caracteres) for i in range(8))

        trabajador.set_password(nueva_pass)
        db.session.commit()

        # Enviar correo
        enviado = enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)

        if enviado:
            return {"message": "Contraseña enviada al correo"}, 200
        else:
            return {"message": "Error técnico enviando correo"}, 500

@blp.route("/change-password")
class ChangePassword(MethodView):
    @jwt_required()
    @blp.arguments(ChangePasswordSchema)
    def post(self, user_data):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if not trabajador:
            print(f"DEBUG ERROR: Usuario {user_id} no encontrado en BBDD") # <--- DEBUG
            abort(404, message="Usuario no encontrado")

        # DEBUGGING: Ver qué está llegando
        print(f"--- DEBUG CHANGE PASSWORD ---")
        print(f"Usuario ID: {user_id}")
        print(f"Pass Actual enviada (Android): {user_data['current_password']}")
        # NO imprimas el hash real por seguridad, pero verificamos el check
        check = trabajador.check_password(user_data["current_password"])
        print(f"Resultado del check_password: {check}")
        print(f"-----------------------------")

        if not check:
            # Si entra aquí, es que la contraseña actual no coincide
            abort(401, message="La contraseña actual es incorrecta")

        if len(user_data["new_password"]) < 6:
            abort(400, message="La contraseña nueva es demasiado corta")

        trabajador.set_password(user_data["new_password"])
        db.session.commit()

        return {"message": "Contraseña actualizada correctamente"}, 200
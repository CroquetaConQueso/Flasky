import random
import string
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token
from sqlalchemy import or_

from extensions import db
from models import Trabajador
from schemas import UserLoginSchema, PasswordResetSchema 
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
        # Esto soluciona el error "Verifica los datos" si la app envía 'email' en vez de 'identificador'
        raw_identificador = user_data.get("identificador") or user_data.get("email") or user_data.get("nif")

        if not raw_identificador:
            # Si no llega ninguno de los 3, entonces sí damos error
            abort(422, message="Debes proporcionar tu Email o NIF para recuperar la contraseña.")

        identificador = raw_identificador.strip()
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.email.in_(posibles_valores),
                Trabajador.nif.in_(posibles_valores)
            )
        ).first()

        if not trabajador:
            # Seguridad: No revelamos si el usuario existe o no
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
import random
import string
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token
from sqlalchemy import or_

from extensions import db
from models import Trabajador
# IMPORTANTE: Importamos PasswordResetSchema
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
            
            # --- CAMBIO CRÍTICO PARA LA APP ---
            # Devolvemos el Token Y los datos del usuario.
            # Sin esto, la App no sabe quién ha entrado.
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
    # Usamos el esquema para validar input automáticamente
    @blp.arguments(PasswordResetSchema)
    def post(self, user_data):
        identificador = user_data["identificador"].strip()

        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.email.in_(posibles_valores),
                Trabajador.nif.in_(posibles_valores)
            )
        ).first()

        if not trabajador:
            # No damos pistas de si existe o no por seguridad
            return {"message": "Si los datos son correctos, recibirás un correo"}, 200

        if not trabajador.email:
            return {"message": "Este usuario no tiene email configurado"}, 400

        # Generar contraseña temporal
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
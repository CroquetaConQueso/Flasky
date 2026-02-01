import random
import string
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token
from sqlalchemy import or_

from extensions import db
from models import Trabajador
from schemas import UserLoginSchema
from utils.email_sender import enviar_correo_password

blp = Blueprint("auth", __name__, description="Autenticacion y Tokens")

@blp.route("/login")
class Login(MethodView):
    @blp.arguments(UserLoginSchema)
    def post(self, user_data):
        identificador = user_data["nif"]
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.nif.in_(posibles_valores),
                Trabajador.email.in_(posibles_valores)
            )
        ).first()

        if trabajador and trabajador.check_password(user_data["password"]):
            access_token = create_access_token(identity=str(trabajador.id_trabajador))
            return {"access_token": access_token}

        abort(401, message="Credenciales incorrectas")

@blp.route("/reset-password")
class PasswordReset(MethodView):
    def post(self):
        user_data = request.get_json()
        identificador = user_data.get("identificador")

        if not identificador:
            return {"message": "Introduce tu NIF o Email"}, 400

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
            return {"message": "Usuario sin email asociado"}, 400

        caracteres = string.ascii_letters + string.digits
        nueva_pass = ''.join(random.choice(caracteres) for i in range(8))

        trabajador.set_password(nueva_pass)
        db.session.commit()

        enviado = enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)

        if enviado:
            return {"message": "Contraseña enviada al correo"}, 200
        else:
            return {"message": "Error enviando correo"}, 500
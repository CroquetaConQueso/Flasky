from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import create_access_token
from models import Trabajador
from schemas import UserLoginSchema

blp = Blueprint("auth", __name__, description="Autenticacion y Tokens")

@blp.route("/login")
class Login(MethodView):
    @blp.arguments(UserLoginSchema)
    def post(self, user_data):
        trabajador = Trabajador.query.filter_by(nif=user_data["nif"]).first()

        if trabajador and trabajador.check_password(user_data["password"]):
            access_token = create_access_token(identity=str(trabajador.id_trabajador))
            return {"access_token": access_token}

        abort(401, message="Credenciales incorrectas")
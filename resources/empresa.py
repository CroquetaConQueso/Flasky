from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Empresa
from schemas import EmpresaSchema

blp = Blueprint("empresas", __name__, description="Operaciones sobre empresas")

@blp.route("/empresas")
class EmpresaList(MethodView):
    @jwt_required()
    @blp.response(200, EmpresaSchema(many=True))
    def get(self):
        return Empresa.query.all()

    @jwt_required()
    @blp.arguments(EmpresaSchema)
    @blp.response(201, EmpresaSchema)
    def post(self, empresa_data):
        empresa = Empresa(**empresa_data)
        
        # Validacion manual básica de duplicados antes de intentar guardar
        if Empresa.query.filter_by(nombrecomercial=empresa.nombrecomercial).first():
            abort(400, message="Ya existe una empresa con ese nombre.")
        if Empresa.query.filter_by(cif=empresa.cif).first():
            abort(400, message="Ya existe una empresa con ese CIF.")

        try:
            db.session.add(empresa)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(400, message="Error de integridad al guardar la empresa.")
            
        return empresa

@blp.route("/empresas/<int:id_empresa>")
class EmpresaDetail(MethodView):
    @jwt_required()
    @blp.response(200, EmpresaSchema)
    def get(self, id_empresa):
        empresa = Empresa.query.get_or_404(id_empresa)
        return empresa

    @jwt_required()
    def delete(self, id_empresa):
        empresa = Empresa.query.get_or_404(id_empresa)
        
        if empresa.trabajadores:
            abort(400, message="No se puede eliminar la empresa porque tiene trabajadores asociados.")
            
        db.session.delete(empresa)
        db.session.commit()
        return {"message": "Empresa eliminada correctamente."}
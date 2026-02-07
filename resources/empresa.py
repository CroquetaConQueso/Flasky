import re
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Empresa, Trabajador
# Añadido FichajeNFCInputSchema a los imports
from schemas import EmpresaSchema, TrabajadorSchema, FichajeNFCInputSchema

blp = Blueprint("empresas", __name__, description="Fichajes y control de presencia")

# =========================================================
# HELPERS (Necesarios para que funcionen las validaciones)
# =========================================================

def normalizar_rol(raw: str) -> str:
    if not raw:
        return "SIN_ROL"
    return re.sub(r'[^A-Z]', '', raw.strip().upper())

def es_admin_robusto(trabajador):
    if not trabajador or not getattr(trabajador, "rol", None) or not getattr(trabajador.rol, "nombre_rol", None):
        return False, "SIN_ROL"
    rol_norm = normalizar_rol(trabajador.rol.nombre_rol)
    claves = ["ADMIN", "RESPONSABLE", "SUPER", "RRHH", "GERENTE", "JEFE", "ENCARGADO", "DIREC"]
    tiene_poder = any(k in rol_norm for k in claves)
    return tiene_poder, rol_norm

def _normalizar_uid(uid: str) -> str:
    if not uid:
        return ""
    return uid.strip().upper().replace(":", "").replace("-", "").replace(" ", "")

# =========================================================
# ENDPOINTS
# =========================================================

# --- LISTA DE EMPRESAS (SUPERADMIN) ---
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
        if Empresa.query.filter_by(nombrecomercial=empresa.nombrecomercial).first():
            abort(400, message="Ya existe una empresa con ese nombre.")
        if Empresa.query.filter_by(cif=empresa.cif).first():
            abort(400, message="Ya existe una empresa con ese CIF.")
        try:
            db.session.add(empresa)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(400, message="Error de integridad.")
        return empresa

# --- DETALLE EMPRESA ---
@blp.route("/empresas/<int:id_empresa>")
class EmpresaDetail(MethodView):
    @jwt_required()
    @blp.response(200, EmpresaSchema)
    def get(self, id_empresa):
        return Empresa.query.get_or_404(id_empresa)

    @jwt_required()
    def delete(self, id_empresa):
        empresa = Empresa.query.get_or_404(id_empresa)
        if empresa.trabajadores:
            abort(400, message="No se puede eliminar: tiene trabajadores.")
        db.session.delete(empresa)
        db.session.commit()
        return {"message": "Empresa eliminada correctamente."}

# --- CONFIGURACIÓN DE EMPRESA (MAPA) ---
@blp.route("/empresa/config")
class EmpresaConfig(MethodView):
    @jwt_required()
    @blp.response(200, EmpresaSchema)
    def get(self):
        """Obtener configuración (Lat, Lon, Radio)"""
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)
        if not trabajador or not trabajador.empresa:
            abort(404, message="Empresa no encontrada.")
        return trabajador.empresa

    @jwt_required()
    @blp.arguments(EmpresaSchema(partial=True)) # partial=True allows sending only lat/lon/radio
    @blp.response(200, EmpresaSchema)
    def post(self, empresa_data):
        """Guardar configuración (Lat, Lon, Radio)"""
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if not trabajador or not trabajador.empresa:
            abort(404, message="No tienes empresa asignada.")

        empresa = trabajador.empresa

        # Updating fields using Spanish names from schemas.py
        if 'latitud' in empresa_data:
            empresa.latitud = empresa_data['latitud']
        if 'longitud' in empresa_data:
            empresa.longitud = empresa_data['longitud']
        if 'radio' in empresa_data:
            empresa.radio = empresa_data['radio']

        try:
            db.session.commit()
        except:
            db.session.rollback()
            abort(500, message="Error al guardar configuración.")

        return empresa

# --- LISTA DE EMPLEADOS (PARA LA APP) ---
@blp.route("/empleados")
class EmpleadoList(MethodView):
    @jwt_required()
    @blp.response(200, TrabajadorSchema(many=True))
    def get(self):
        """Obtener lista de empleados de mi empresa"""
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get(user_id)

        if not trabajador or not trabajador.empresa:
             abort(404, message="Usuario sin empresa asignada.")

        # Return all workers from the same company
        return trabajador.empresa.trabajadores

# ---- PARA ESTABLECER EL NFC PRINCIPAL
@blp.route("/config-nfc")
class EmpresaNfcConfig(MethodView):
    @jwt_required()
    @blp.arguments(FichajeNFCInputSchema)
    def post(self, data):
        user_id = get_jwt_identity()
        trabajador = Trabajador.query.get_or_404(user_id)

        # Verificar que es admin
        es_admin, _ = es_admin_robusto(trabajador)
        if not es_admin:
            abort(403, message="Solo administradores pueden configurar el NFC de oficina.")

        empresa = trabajador.empresa
        nfc_limpio = _normalizar_uid(data.get("nfc_data"))

        empresa.codigo_nfc_oficina = nfc_limpio
        db.session.commit()

        return {"message": f"NFC de Oficina actualizado: {nfc_limpio}"}, 200
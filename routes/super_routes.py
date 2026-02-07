from flask import Blueprint, render_template, redirect, url_for, flash, session
from models import Empresa, Rol
from forms import EmpresaForm, RolForm
from utils.decorators import superadmin_required
from extensions import db

super_bp = Blueprint('super_web', __name__)

# -------------------------
# PARTE DE EMPRESAS
# -------------------------

@super_bp.get("/empresas")
@superadmin_required
def empresas_list():
    # Lista todas las empresas existentes (vista de superadmin).
    return render_template("empresas_list.html", empresas=Empresa.query.all())

@super_bp.route("/empresas/nueva", methods=["GET", "POST"])
@superadmin_required
def empresa_new():
    # Crea una empresa nueva con configuración base (gps/radio).
    form = EmpresaForm()
    if form.validate_on_submit():
        empresa = Empresa(
            nombrecomercial=form.nombrecomercial.data,
            cif=form.cif.data,
            latitud=form.latitud.data,
            longitud=form.longitud.data,
            radio=form.radio.data
        )
        db.session.add(empresa)
        db.session.commit()
        flash("Nueva empresa creada con éxito.", "success")
        return redirect(url_for("super_web.empresas_list"))

    return render_template("empresa_form.html", form=form, titulo="Nueva Empresa", is_new=True)

@super_bp.route("/empresas/<int:empresa_id>/editar", methods=["GET", "POST"])
@superadmin_required
def empresa_edit(empresa_id):
    # Edita datos de una empresa existente.
    empresa = Empresa.query.get_or_404(empresa_id)
    form = EmpresaForm(obj=empresa)

    if form.validate_on_submit():
        empresa.nombrecomercial = form.nombrecomercial.data
        empresa.cif = form.cif.data
        empresa.latitud = form.latitud.data
        empresa.longitud = form.longitud.data
        empresa.radio = form.radio.data

        db.session.commit()
        flash("Empresa actualizada correctamente.", "success")
        return redirect(url_for("super_web.empresas_list"))

    return render_template("empresa_form.html", form=form, titulo="Editar Empresa", is_new=False)

@super_bp.post("/empresas/<int:empresa_id>/eliminar")
@superadmin_required
def empresa_delete(empresa_id):
    # Borra una empresa solo si no tiene empleados asociados.
    # Si era la empresa activa en sesión, se cierra sesión por seguridad.
    empresa = Empresa.query.get_or_404(empresa_id)
    empresa_activa_id = session.get("empresa_id")
    es_empresa_activa = (empresa_activa_id == empresa.id_empresa)

    if empresa.trabajadores:
        flash("No puedes eliminar una empresa que tiene empleados activos.", "danger")
    else:
        db.session.delete(empresa)
        db.session.commit()

        if es_empresa_activa:
            session.clear()
            flash("Has eliminado la empresa activa. Sesión cerrada.", "info")
            return redirect(url_for("auth_web.login"))

        flash("Empresa eliminada correctamente.", "success")

    return redirect(url_for("super_web.empresas_list"))

# -------------------------
# PARTE DE ROLES
# -------------------------

@super_bp.get("/roles")
@superadmin_required
def roles_list():
    # Lista roles globales del sistema.
    roles = Rol.query.order_by(Rol.nombre_rol).all()
    return render_template("roles_list.html", roles=roles)

@super_bp.route("/roles/nuevo", methods=["GET", "POST"])
@superadmin_required
def rol_new():
    # Crea un rol nuevo evitando duplicados por nombre.
    form = RolForm()
    if form.validate_on_submit():
        nombre = form.nombre_rol.data.strip()

        if Rol.query.filter_by(nombre_rol=nombre).first():
            flash("Ya existe un rol con ese nombre.", "danger")
        else:
            db.session.add(Rol(nombre_rol=nombre))
            db.session.commit()
            flash("Rol creado.", "success")
            return redirect(url_for("super_web.roles_list"))

    return render_template("rol_form.html", form=form, is_new=True)

@super_bp.route("/roles/<int:rol_id>/editar", methods=["GET", "POST"])
@superadmin_required
def rol_edit(rol_id):
    # Edita el nombre del rol, evitando colisión con otros roles.
    rol = Rol.query.get_or_404(rol_id)
    form = RolForm(obj=rol)

    if form.validate_on_submit():
        nombre = form.nombre_rol.data.strip()

        existente = Rol.query.filter(
            Rol.nombre_rol == nombre,
            Rol.id_rol != rol.id_rol
        ).first()

        if existente:
            flash("Ya existe otro rol con ese nombre.", "danger")
        else:
            rol.nombre_rol = nombre
            db.session.commit()
            flash("Rol actualizado.", "success")
            return redirect(url_for("super_web.roles_list"))

    return render_template("rol_form.html", form=form, is_new=False)

@super_bp.post("/roles/<int:rol_id>/eliminar")
@superadmin_required
def rol_delete(rol_id):
    # Borra un rol solo si no hay empleados asignados a él.
    rol = Rol.query.get_or_404(rol_id)

    if rol.trabajadores:
        flash("No se puede eliminar: Hay empleados asignados a este rol.", "danger")
    else:
        db.session.delete(rol)
        db.session.commit()
        flash("Rol eliminado.", "success")

    return redirect(url_for("super_web.roles_list"))

from flask import Blueprint, render_template, redirect, url_for, flash, session
from models import Trabajador, Empresa, Rol, Horario, Fichaje
from forms import EmpresaForm
from utils.decorators import admin_required
from extensions import db

empresa_bp = Blueprint('empresa_web', __name__)

@empresa_bp.get("/panel")
@admin_required
def panel():
    trabajador = Trabajador.query.get(session.get("user_id"))
    empresa_id = session.get("empresa_id")
    empresa = Empresa.query.get(empresa_id) if empresa_id else None

    stats = { "empleados": 0, "horarios": 0, "roles": 0, "fichajes_total": 0 }

    if empresa_id:
        stats["empleados"] = Trabajador.query.filter_by(idEmpresa=empresa_id).count()
        stats["horarios"] = Horario.query.count()
        stats["roles"] = Rol.query.count()
        ids_empleados = [t.id_trabajador for t in Trabajador.query.filter_by(idEmpresa=empresa_id).all()]
        if ids_empleados:
            stats["fichajes_total"] = Fichaje.query.filter(Fichaje.id_trabajador.in_(ids_empleados)).count()

    return render_template("panel.html", trabajador=trabajador, empresa=empresa, stats=stats)

@empresa_bp.route("/empresa", methods=["GET", "POST"])
@admin_required
def empresa_view():
    empresa_id = session.get("empresa_id")
    if not empresa_id:
        return redirect(url_for("auth_web.login"))

    empresa = Empresa.query.get_or_404(empresa_id)
    form = EmpresaForm(obj=empresa)

    if form.validate_on_submit():
        empresa.nombrecomercial = form.nombrecomercial.data
        empresa.cif = form.cif.data
        empresa.latitud = form.latitud.data
        empresa.longitud = form.longitud.data
        empresa.radio = form.radio.data

        try:
            db.session.commit()
            flash("Datos de la empresa actualizados correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar: {str(e)}", "danger")

        return redirect(url_for("empresa_web.empresa_view"))

    return render_template("empresa.html", form=form)
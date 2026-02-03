from flask import Blueprint, render_template, redirect, url_for, flash, session
from sqlalchemy import or_
from models import Trabajador, Empresa
from forms import LoginForm, RequestPasswordForm, ChangePasswordForm
from utils.email_sender import enviar_correo_password
from extensions import db
import string
import random

auth_bp = Blueprint('auth_web', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    empresas = Empresa.query.order_by(Empresa.nombrecomercial).all()
    form.empresa_id.choices = [(e.id_empresa, e.nombrecomercial) for e in empresas]

    if form.validate_on_submit():
        identificador = form.nif.data.strip()
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.nif.in_(posibles_valores),
                Trabajador.email.in_(posibles_valores)
            )
        ).first()

        if trabajador and trabajador.check_password(form.password.data):
            rol_nombre = trabajador.rol.nombre_rol.lower().strip() if trabajador.rol else ""
            permiso_concedido = False
            roles_super = ["superadministrador", "superadmin", "root"]

            if rol_nombre in roles_super:
                permiso_concedido = True
            elif trabajador.idEmpresa == form.empresa_id.data:
                if rol_nombre == "administrador":
                    permiso_concedido = True
                else:
                    flash("No tienes rol de administrador en esta empresa.", "danger")
            else:
                flash("No perteneces a la empresa seleccionada.", "danger")

            if permiso_concedido:
                session.clear()
                session["user_id"] = trabajador.id_trabajador
                session["empresa_id"] = form.empresa_id.data

                nombre_empresa = dict(form.empresa_id.choices).get(form.empresa_id.data)
                flash(f"Bienvenido al panel de gestión de {nombre_empresa}", "success")
                return redirect(url_for("empresa_web.panel"))
        else:
            flash("Credenciales incorrectas. Verifica NIF/Email y contraseña.", "danger")

    return render_template("login.html", form=form)

@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_web():
    if session.get("user_id"):
        return redirect(url_for("empresa_web.panel"))

    form = RequestPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.strip()
        trabajador = Trabajador.query.filter_by(email=email).first()

        if trabajador:
            caracteres = string.ascii_letters + string.digits
            nueva_pass = ''.join(random.choice(caracteres) for i in range(8))

            trabajador.set_password(nueva_pass)
            db.session.commit()

            enviado = enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)

            if enviado:
                flash("Se ha enviado una nueva contraseña a tu correo.", "success")
                return redirect(url_for("auth_web.login"))
            else:
                flash("Error al enviar el correo. Inténtalo más tarde.", "danger")
        else:
            flash("Si el correo existe, recibirás una nueva contraseña.", "info")
            return redirect(url_for("auth_web.login"))

    return render_template("reset_password.html", form=form)

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("user_id"):
        return redirect(url_for("auth_web.login"))

    trabajador = Trabajador.query.get(session.get("user_id"))
    form = ChangePasswordForm()

    if form.validate_on_submit():
        if trabajador.check_password(form.current_password.data):
            trabajador.set_password(form.new_password.data)
            db.session.commit()
            flash("¡Contraseña actualizada con éxito!", "success")
            return redirect(url_for("empresa_web.panel"))
        else:
            flash("La contraseña actual no es correcta.", "danger")

    return render_template("change_password.html", form=form)

@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("index"))
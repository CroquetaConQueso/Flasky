from flask import Blueprint, render_template, redirect, url_for, flash, session
from sqlalchemy import or_

from models import Trabajador, Empresa
from forms import LoginForm, RequestPasswordForm, ChangePasswordForm, ResetPasswordTokenForm
from utils.email_sender import enviar_correo_password
from utils.reset_tokens import generar_token_reset, validar_token_reset
from itsdangerous import BadSignature, SignatureExpired

from extensions import db


auth_bp = Blueprint("auth_web", __name__)


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
            token = generar_token_reset(trabajador.id_trabajador)
            link = url_for("auth_web.reset_password_confirm", token=token, _external=True)

            enviado = enviar_correo_password(trabajador.email, trabajador.nombre, link)

            if enviado:
                flash("Si el correo existe, recibirás un enlace para restablecer tu contraseña.", "success")
                return redirect(url_for("auth_web.login"))
            else:
                flash("Error al enviar el correo. Inténtalo más tarde.", "danger")
                return redirect(url_for("auth_web.login"))

        flash("Si el correo existe, recibirás un enlace para restablecer tu contraseña.", "info")
        return redirect(url_for("auth_web.login"))

    return render_template("reset_password.html", form=form)


@auth_bp.route("/reset-password/confirm/<token>", methods=["GET", "POST"])
def reset_password_confirm(token):
    if session.get("user_id"):
        return redirect(url_for("empresa_web.panel"))

    form = ResetPasswordTokenForm()

    if form.validate_on_submit():
        try:
            user_id = validar_token_reset(token, max_age_seconds=900)
        except SignatureExpired:
            flash("El enlace ha caducado. Solicita uno nuevo.", "danger")
            return redirect(url_for("auth_web.reset_password_web"))
        except BadSignature:
            flash("El enlace no es válido. Solicita uno nuevo.", "danger")
            return redirect(url_for("auth_web.reset_password_web"))

        trabajador = Trabajador.query.get(user_id)
        if not trabajador:
            flash("Usuario no encontrado. Solicita un nuevo enlace.", "danger")
            return redirect(url_for("auth_web.reset_password_web"))

        trabajador.set_password(form.new_password.data)
        db.session.commit()

        flash("Contraseña actualizada. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth_web.login"))

    return render_template("reset_password_confirm.html", form=form)


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

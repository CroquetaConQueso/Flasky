from flask import Blueprint, render_template, redirect, url_for, flash, session
from sqlalchemy import or_
from models import Trabajador, Empresa
from forms import LoginForm, RequestPasswordForm, ChangePasswordForm
from utils.email_sender import enviar_correo_password
from extensions import db
import string
import random

# Blueprint que concentra el flujo web de autenticación y sesión (login/reset/cambio/logout).
auth_bp = Blueprint('auth_web', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Prepara el formulario y carga el selector de empresa desde base de datos.
    form = LoginForm()
    empresas = Empresa.query.order_by(Empresa.nombrecomercial).all()
    form.empresa_id.choices = [(e.id_empresa, e.nombrecomercial) for e in empresas]

    if form.validate_on_submit():
        # Normaliza el identificador para aceptar NIF o email sin pelearse con mayúsculas.
        identificador = form.nif.data.strip()
        posibles_valores = {identificador, identificador.lower(), identificador.upper()}

        # Busca al trabajador por NIF o email con el mismo valor en distintas variantes.
        trabajador = Trabajador.query.filter(
            or_(
                Trabajador.nif.in_(posibles_valores),
                Trabajador.email.in_(posibles_valores)
            )
        ).first()

        if trabajador and trabajador.check_password(form.password.data):
            # Valida permisos: super roles entran siempre; si no, debe ser admin de la empresa elegida.
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
                # Limpia la sesión anterior y guarda el contexto necesario para navegar por el panel.
                session.clear()
                session["user_id"] = trabajador.id_trabajador
                session["empresa_id"] = form.empresa_id.data

                # Devuelve feedback amigable y redirige al panel.
                nombre_empresa = dict(form.empresa_id.choices).get(form.empresa_id.data)
                flash(f"Bienvenido al panel de gestión de {nombre_empresa}", "success")
                return redirect(url_for("empresa_web.panel"))
        else:
            flash("Credenciales incorrectas. Verifica NIF/Email y contraseña.", "danger")

    return render_template("login.html", form=form)

@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_web():
    # Si ya hay sesión, no tiene sentido recuperar contraseña desde aquí.
    if session.get("user_id"):
        return redirect(url_for("empresa_web.panel"))

    form = RequestPasswordForm()

    if form.validate_on_submit():
        # Toma el email y busca al usuario asociado.
        email = form.email.data.strip()
        trabajador = Trabajador.query.filter_by(email=email).first()

        if trabajador:
            # Genera una contraseña nueva corta y la guarda en base de datos.
            caracteres = string.ascii_letters + string.digits
            nueva_pass = ''.join(random.choice(caracteres) for i in range(8))

            trabajador.set_password(nueva_pass)
            db.session.commit()

            # Intenta enviar el correo con la nueva contraseña.
            enviado = enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)

            if enviado:
                flash("Se ha enviado una nueva contraseña a tu correo.", "success")
                return redirect(url_for("auth_web.login"))
            else:
                flash("Error al enviar el correo. Inténtalo más tarde.", "danger")
        else:
            # Respuesta neutra para no revelar si el email existe o no.
            flash("Si el correo existe, recibirás una nueva contraseña.", "info")
            return redirect(url_for("auth_web.login"))

    return render_template("reset_password.html", form=form)

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    # Protege la ruta: sin sesión, vuelve al login.
    if not session.get("user_id"):
        return redirect(url_for("auth_web.login"))

    # Carga el usuario de la sesión y muestra el formulario.
    trabajador = Trabajador.query.get(session.get("user_id"))
    form = ChangePasswordForm()

    if form.validate_on_submit():
        # Comprueba la contraseña actual antes de permitir el cambio.
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
    # Borra la sesión y devuelve al inicio con un aviso.
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("index"))

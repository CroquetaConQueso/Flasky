from functools import wraps
from flask import session, redirect, url_for, flash
from sqlalchemy.exc import OperationalError
from extensions import db
from models import Trabajador

def admin_required(view):
    """Permite acceso a Administradores y Superadministradores."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth.login")) # Nota: auth.login será el nuevo nombre de la ruta

        try:
            trabajador = Trabajador.query.get(user_id)
        except OperationalError:
            db.session.remove()
            session.clear()
            flash("Error de conexión. Por favor, identifícate de nuevo.", "danger")
            return redirect(url_for("auth.login"))

        if not trabajador or not trabajador.rol:
            flash("Acceso denegado: Usuario no válido o sin rol.", "danger")
            return redirect(url_for("auth.login"))

        rol_actual = trabajador.rol.nombre_rol.lower().strip()
        if rol_actual not in ("administrador", "superadministrador", "superadmin"):
            flash("Necesitas permisos de Administrador para acceder aquí.", "danger")
            return redirect(url_for("auth.login"))

        return view(*args, **kwargs)
    return wrapped

def superadmin_required(view):
    """Permite acceso EXCLUSIVO a Superadministradores (Gestión Global)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth.login"))

        trabajador = Trabajador.query.get(user_id)

        if not trabajador or not trabajador.rol:
            flash("Error de integridad: Usuario sin rol asignado.", "danger")
            return redirect(url_for("empresa.panel")) # Nota: empresa.panel será la nueva ruta

        if trabajador.rol.nombre_rol.lower() not in ("superadministrador", "superadmin", "root"):
            flash("Acceso restringido exclusivamente a Superadministradores.", "danger")
            return redirect(url_for("empresa.panel"))

        return view(*args, **kwargs)
    return wrapped
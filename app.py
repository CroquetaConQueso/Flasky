# app.py
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, session, request
from sqlalchemy.exc import OperationalError

from config import Config
from extensions import db, migrate
from models import Trabajador, Empresa, Rol, Horario, Dia, Franja
from forms import (
    LoginForm,
    EmpresaForm,
    RolForm,
    TrabajadorForm,
    HorarioForm,
    FranjaForm,
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # ----------------- DECORADOR DE ADMIN ----------------- #
    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return redirect(url_for("login"))

            try:
                trabajador = Trabajador.query.get(user_id)
            except OperationalError:
                db.session.remove()
                session.clear()
                flash("Error de conexión. Vuelve a iniciar sesión.", "danger")
                return redirect(url_for("login"))

            if not trabajador or not trabajador.rol:
                flash("Debe iniciar sesión.", "danger")
                return redirect(url_for("login"))

            nombre_rol = trabajador.rol.nombre_rol.lower()
            if nombre_rol not in ("administrador", "superadministrador"):
                flash("Debe tener rol de administrador.", "danger")
                return redirect(url_for("login"))

            return view(*args, **kwargs)

        return wrapped

    # ----------------- PÁGINA INICIAL ----------------- #
    @app.get("/")
    def index():
        return render_template("index.html")

    # ----------------- LOGIN ----------------- #
    @app.route("/login", methods=["GET", "POST"])
    def login():
        form = LoginForm()
        empresas = Empresa.query.order_by(Empresa.nombrecomercial).all()
        form.empresa_id.choices = [
            (e.id_empresa, e.nombrecomercial) for e in empresas
        ]

        if form.validate_on_submit():
            trabajador = Trabajador.query.filter_by(nif=form.nif.data).first()

            # CAMBIO DE SEGURIDAD: Usamos check_password
            if trabajador and trabajador.check_password(form.password.data):
                if trabajador.idEmpresa != form.empresa_id.data:
                    flash("El trabajador no pertenece a esa empresa.", "danger")
                elif not trabajador.rol or trabajador.rol.nombre_rol.lower() not in (
                    "administrador",
                    "superadministrador",
                ):
                    flash("No tiene rol de administrador.", "danger")
                else:
                    session.clear()
                    session["user_id"] = trabajador.id_trabajador
                    session["empresa_id"] = form.empresa_id.data
                    flash("Sesión iniciada.", "success")
                    return redirect(url_for("panel"))
            else:
                flash("Credenciales incorrectas.", "danger")

        return render_template("login.html", form=form)

    @app.get("/logout")
    def logout():
        session.clear()
        flash("Sesión cerrada.", "info")
        return redirect(url_for("index"))

    # ----------------- PANEL ----------------- #
    @app.get("/panel")
    @admin_required
    def panel():
        trabajador = Trabajador.query.get(session.get("user_id"))
        empresa = None
        empresa_id = session.get("empresa_id")
        if empresa_id:
            empresa = Empresa.query.get(empresa_id)

        return render_template("panel.html", trabajador=trabajador, empresa=empresa)

    # ----------------- EMPRESA (NIVEL BÁSICO) ----------------- #
    @app.route("/empresa", methods=["GET", "POST"])
    @admin_required
    def empresa_view():
        empresa_id = session.get("empresa_id")
        if not empresa_id:
            flash("No hay empresa seleccionada.", "danger")
            return redirect(url_for("login"))

        empresa = Empresa.query.get_or_404(empresa_id)
        form = EmpresaForm(obj=empresa)

        if form.validate_on_submit():
            empresa.nombrecomercial = form.nombrecomercial.data
            empresa.cif = form.cif.data
            empresa.latitud = form.latitud.data
            empresa.longitud = form.longitud.data
            empresa.radio = form.radio.data
            
            db.session.commit()
            flash("Datos de empresa actualizados.", "success")
            return redirect(url_for("empresa_view"))

        return render_template("empresa.html", form=form)

    # ----------------- ROLES ----------------- #
    @app.get("/roles")
    @admin_required
    def roles_list():
        roles = Rol.query.order_by(Rol.nombre_rol).all()
        return render_template("roles_list.html", roles=roles)

    @app.route("/roles/nuevo", methods=["GET", "POST"])
    @admin_required
    def rol_new():
        form = RolForm()
        if form.validate_on_submit():
            nombre = form.nombre_rol.data.strip()
            existente = Rol.query.filter(Rol.nombre_rol == nombre).first()
            if existente:
                flash("Ya existe un rol con ese nombre.", "danger")
            else:
                rol = Rol(nombre_rol=nombre)
                db.session.add(rol)
                db.session.commit()
                flash("Rol creado.", "success")
                return redirect(url_for("roles_list"))
        return render_template("rol_form.html", form=form, titulo="Nuevo rol")

    @app.route("/roles/<int:rol_id>/editar", methods=["GET", "POST"])
    @admin_required
    def rol_edit(rol_id):
        rol = Rol.query.get_or_404(rol_id)
        form = RolForm(obj=rol)
        if form.validate_on_submit():
            nombre = form.nombre_rol.data.strip()
            existente = Rol.query.filter(
                Rol.nombre_rol == nombre, Rol.id_rol != rol.id_rol
            ).first()
            if existente:
                flash("Ya existe un rol con ese nombre.", "danger")
            else:
                rol.nombre_rol = nombre
                db.session.commit()
                flash("Rol actualizado.", "success")
                return redirect(url_for("roles_list"))
        return render_template("rol_form.html", form=form, titulo="Editar rol")

    @app.post("/roles/<int:rol_id>/eliminar")
    @admin_required
    def rol_delete(rol_id):
        rol = Rol.query.get_or_404(rol_id)
        if rol.trabajadores:
            flash("No se puede eliminar un rol con empleados asociados.", "danger")
        else:
            db.session.delete(rol)
            db.session.commit()
            flash("Rol eliminado.", "success")
        return redirect(url_for("roles_list"))

    # ----------------- EMPLEADOS ----------------- #
    @app.get("/empleados")
    @admin_required
    def empleados_list():
        empresa_id = session.get("empresa_id")
        if not empresa_id:
            flash("No hay empresa seleccionada.", "danger")
            return redirect(url_for("login"))

        empleados = (
            Trabajador.query.filter_by(idEmpresa=empresa_id)
            .order_by(Trabajador.apellidos, Trabajador.nombre)
            .all()
        )
        return render_template("empleados_list.html", empleados=empleados)

    @app.route("/empleados/nuevo", methods=["GET", "POST"])
    @admin_required
    def empleado_new():
        empresa_id = session.get("empresa_id")
        if not empresa_id:
            flash("No hay empresa seleccionada.", "danger")
            return redirect(url_for("login"))

        form = TrabajadorForm()

        roles = Rol.query.order_by(Rol.nombre_rol).all()
        form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in roles]

        horarios = Horario.query.order_by(Horario.nombre_horario).all()
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in horarios]

        if form.validate_on_submit():
            nif_limpio = form.nif.data.strip().upper()
            existente = Trabajador.query.filter_by(nif=nif_limpio).first()

            if existente:
                flash(f"Error: Ya existe un empleado con el NIF {nif_limpio}.", "danger")
            else:
                trabajador = Trabajador(
                    nif=nif_limpio,
                    nombre=form.nombre.data,
                    apellidos=form.apellidos.data,
                    # NO PASAMOS PASSW AQUÍ, USAMOS SET_PASSWORD
                    email=form.email.data,
                    telef=form.telef.data,
                    idEmpresa=empresa_id,
                    idHorario=form.horario_id.data,
                    idRol=form.rol_id.data,
                )
                # CAMBIO DE SEGURIDAD: Encriptamos la contraseña
                trabajador.set_password(form.passw.data)
                
                db.session.add(trabajador)
                db.session.commit()
                flash("Empleado creado.", "success")
                return redirect(url_for("empleados_list"))

        return render_template(
            "empleados_form.html",
            form=form,
            titulo="Nuevo empleado",
        )

    @app.route("/empleados/<int:emp_id>/editar", methods=["GET", "POST"])
    @admin_required
    def empleado_edit(emp_id):
        empresa_id = session.get("empresa_id")
        if not empresa_id:
            flash("No hay empresa seleccionada.", "danger")
            return redirect(url_for("login"))

        trabajador = Trabajador.query.get_or_404(emp_id)
        if trabajador.idEmpresa != empresa_id:
            flash("Empleado de otra empresa.", "danger")
            return redirect(url_for("empleados_list"))

        form = TrabajadorForm(obj=trabajador)

        roles = Rol.query.order_by(Rol.nombre_rol).all()
        form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in roles]

        horarios = Horario.query.order_by(Horario.nombre_horario).all()
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in horarios]

        # CAMBIO DE SEGURIDAD: NO rellenamos el campo password en el GET 
        # para no mostrar el hash al usuario.
        if request.method == 'GET':
            form.horario_id.data = trabajador.idHorario
            # form.passw.data NO SE ASIGNA

        if form.validate_on_submit():
            trabajador.nif = form.nif.data
            trabajador.nombre = form.nombre.data
            trabajador.apellidos = form.apellidos.data
            trabajador.email = form.email.data
            trabajador.telef = form.telef.data
            trabajador.idRol = form.rol_id.data
            trabajador.idHorario = form.horario_id.data
            
            # CAMBIO DE SEGURIDAD: Solo si se envía contraseña, la actualizamos encriptada
            if form.passw.data:
                trabajador.set_password(form.passw.data)

            db.session.commit()
            flash("Empleado actualizado.", "success")
            return redirect(url_for("empleados_list"))

        return render_template(
            "empleados_form.html",
            form=form,
            titulo="Editar empleado",
        )

    @app.post("/empleados/<int:emp_id>/eliminar")
    @admin_required
    def empleado_delete(emp_id):
        empresa_id = session.get("empresa_id")
        trabajador = Trabajador.query.get_or_404(emp_id)
        if trabajador.idEmpresa != empresa_id:
            flash("Empleado de otra empresa.", "danger")
        else:
            db.session.delete(trabajador)
            db.session.commit()
            flash("Empleado eliminado.", "success")
        return redirect(url_for("empleados_list"))

    # ----------------- HORARIOS ----------------- #
    @app.get("/horarios")
    @admin_required
    def horarios_list():
        horarios = Horario.query.order_by(Horario.nombre_horario).all()
        return render_template("horarios_list.html", horarios=horarios)

    @app.route("/horarios/nuevo", methods=["GET", "POST"])
    @admin_required
    def horario_new():
        form = HorarioForm()
        if form.validate_on_submit():
            nombre = form.nombre_horario.data.strip()
            existente = Horario.query.filter_by(nombre_horario=nombre).first()

            if existente:
                flash(f"Error: Ya existe un horario con el nombre '{nombre}'.", "danger")
            else:
                horario = Horario(
                    nombre_horario=nombre,
                    descripcion=form.descripcion.data,
                )
                db.session.add(horario)
                db.session.commit()
                flash("Horario creado.", "success")
                return redirect(url_for("horarios_list"))

        return render_template(
            "horario_form.html", form=form, titulo="Nuevo horario"
        )

    @app.route("/horarios/<int:horario_id>/editar", methods=["GET", "POST"])
    @admin_required
    def horario_edit(horario_id):
        horario = Horario.query.get_or_404(horario_id)
        form = HorarioForm(obj=horario)
        if form.validate_on_submit():
            horario.nombre_horario = form.nombre_horario.data.strip()
            horario.descripcion = form.descripcion.data
            db.session.commit()
            flash("Horario actualizado.", "success")
            return redirect(url_for("horarios_list"))
        return render_template(
            "horario_form.html", form=form, titulo="Editar horario"
        )

    @app.post("/horarios/<int:horario_id>/eliminar")
    @admin_required
    def horario_delete(horario_id):
        horario = Horario.query.get_or_404(horario_id)
        if horario.trabajadores:
            flash(
                "No se puede eliminar un horario con trabajadores asociados.",
                "danger",
            )
        else:
            db.session.delete(horario)
            db.session.commit()
            flash("Horario eliminado.", "success")
        return redirect(url_for("horarios_list"))

    @app.route("/horarios/<int:horario_id>/franjas", methods=["GET", "POST"])
    @admin_required
    def horario_franjas(horario_id):
        horario = Horario.query.get_or_404(horario_id)
        form = FranjaForm()

        dias = Dia.query.order_by(Dia.id).all()
        form.dia_id.choices = [(d.id, d.nombre) for d in dias]

        if form.validate_on_submit():
            dia_id = form.dia_id.data
            hora_entrada = form.hora_entrada.data
            hora_salida = form.hora_salida.data

            if hora_entrada >= hora_salida:
                flash(
                    "La hora de entrada debe ser anterior a la de salida.",
                    "danger",
                )
            else:
                existentes = Franja.query.filter_by(
                    id_horario=horario.id_horario, id_dia=dia_id
                ).all()
                solapa = False
                for f in existentes:
                    if (
                        hora_entrada < f.hora_salida
                        and hora_salida > f.hora_entrada
                    ):
                        solapa = True
                        break

                if solapa:
                    flash(
                        "La franja se solapa con otra ya definida para ese día.",
                        "danger",
                    )
                else:
                    franja = Franja(
                        id_dia=dia_id,
                        id_horario=horario.id_horario,
                        hora_entrada=hora_entrada,
                        hora_salida=hora_salida,
                    )
                    db.session.add(franja)
                    db.session.commit()
                    flash("Franja creada.", "success")
                    return redirect(
                        url_for("horario_franjas", horario_id=horario.id_horario)
                    )

        franjas = (
            Franja.query.filter_by(id_horario=horario.id_horario)
            .join(Dia, Franja.id_dia == Dia.id)
            .order_by(Dia.id, Franja.hora_entrada)
            .all()
        )

        return render_template(
            "horario_franjas.html",
            horario=horario,
            franjas=franjas,
            form=form,
        )

    # ----------------- GESTIÓN DE EMPRESAS (NIVEL EXPERTO) ----------------- #

    @app.get("/empresas")
    @admin_required
    def empresas_list():
        user_id = session.get("user_id")
        trabajador = Trabajador.query.get(user_id)

        if not trabajador.rol or trabajador.rol.nombre_rol.lower() != "superadministrador":
            flash("Acceso restringido a Superadministradores.", "danger")
            return redirect(url_for("panel"))

        empresas = Empresa.query.order_by(Empresa.nombrecomercial).all()
        return render_template("empresas_list.html", empresas=empresas)

    @app.route("/empresas/nueva", methods=["GET", "POST"])
    @admin_required
    def empresa_new():
        user_id = session.get("user_id")
        trabajador = Trabajador.query.get(user_id)
        if not trabajador.rol or trabajador.rol.nombre_rol.lower() != "superadministrador":
            flash("Acceso restringido a Superadministradores.", "danger")
            return redirect(url_for("panel"))

        form = EmpresaForm()
        if form.validate_on_submit():
            nombre = form.nombrecomercial.data.strip()
            cif = form.cif.data.strip().upper()

            existe_nombre = Empresa.query.filter_by(nombrecomercial=nombre).first()
            existe_cif = Empresa.query.filter_by(cif=cif).first()

            if existe_nombre:
                flash(f"Error: Ya existe una empresa llamada '{nombre}'.", "danger")
            elif existe_cif:
                flash(f"Error: Ya existe una empresa con CIF '{cif}'.", "danger")
            else:
                empresa = Empresa(
                    nombrecomercial=nombre,
                    cif=cif,
                    latitud=form.latitud.data,
                    longitud=form.longitud.data,
                    radio=form.radio.data
                )
                db.session.add(empresa)
                db.session.commit()
                flash("Empresa creada correctamente.", "success")
                return redirect(url_for("empresas_list"))

        return render_template("empresa_form.html", form=form, titulo="Nueva Empresa")

    @app.post("/empresas/<int:empresa_id>/eliminar")
    @admin_required
    def empresa_delete(empresa_id):
        user_id = session.get("user_id")
        trabajador = Trabajador.query.get(user_id)
        if not trabajador.rol or trabajador.rol.nombre_rol.lower() != "superadministrador":
            flash("No tienes permisos para esto.", "danger")
            return redirect(url_for("panel"))

        empresa = Empresa.query.get_or_404(empresa_id)

        if empresa.trabajadores:
            flash("No se puede eliminar la empresa porque tiene empleados asociados.", "danger")
        else:
            db.session.delete(empresa)
            db.session.commit()
            flash("Empresa eliminada.", "success")

        return redirect(url_for("empresas_list"))

    return app


app = create_app()
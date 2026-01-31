from functools import wraps
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, flash, session, request
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from config import Config
from extensions import db, migrate, jwt, api
from models import Trabajador, Empresa, Rol, Horario, Dia, Franja, Incidencia, Fichaje
from forms import (
    LoginForm,
    EmpresaForm,
    RolForm,
    TrabajadorForm,
    HorarioForm,
    FranjaForm,
    IncidenciaAdminForm,
    IncidenciaCrearForm,
    FichajeManualForm
)
from resources.auth import blp as AuthBlueprint
from resources.empresa import blp as EmpresaBlueprint
from resources.fichaje import blp as FichajeBlueprint


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    api.init_app(app)

    # REGISTRO DE BLUEPRINTS
    api.register_blueprint(AuthBlueprint, url_prefix="/api")
    api.register_blueprint(EmpresaBlueprint, url_prefix="/api")
    api.register_blueprint(FichajeBlueprint, url_prefix="/api")

    # --- DECORADOR DE SEGURIDAD ---
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
                flash("Se ha perdido la conexión. Vuelve a iniciar sesión.", "danger")
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

    # --- RUTAS PÚBLICAS ---
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        form = LoginForm()
        empresas = Empresa.query.order_by(Empresa.nombrecomercial).all()
        form.empresa_id.choices = [(e.id_empresa, e.nombrecomercial) for e in empresas]

        if form.validate_on_submit():
            trabajador = Trabajador.query.filter_by(nif=form.nif.data).first()

            if trabajador and trabajador.check_password(form.password.data):
                if trabajador.idEmpresa != form.empresa_id.data:
                    flash("El trabajador no pertenece a esa empresa.", "danger")
                elif not trabajador.rol or trabajador.rol.nombre_rol.lower() not in ("administrador", "superadministrador"):
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

    # --- RUTAS PRIVADAS (PANEL Y EMPRESA) ---
    @app.get("/panel")
    @admin_required
    def panel():
        trabajador = Trabajador.query.get(session.get("user_id"))
        empresa_id = session.get("empresa_id")
        empresa = Empresa.query.get(empresa_id) if empresa_id else None

        from models import Fichaje
        stats = {
            "empleados": 0, "horarios": 0, "roles": 0, "fichajes_total": 0
        }

        if empresa_id:
            stats["empleados"] = Trabajador.query.filter_by(idEmpresa=empresa_id).count()
            stats["horarios"] = Horario.query.count()
            stats["roles"] = Rol.query.count()
            ids_empleados = [t.id_trabajador for t in Trabajador.query.filter_by(idEmpresa=empresa_id).all()]
            if ids_empleados:
                stats["fichajes_total"] = Fichaje.query.filter(Fichaje.id_trabajador.in_(ids_empleados)).count()

        return render_template("panel.html", trabajador=trabajador, empresa=empresa, stats=stats)

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

    # --- GESTIÓN DE ROLES ---
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
            if Rol.query.filter_by(nombre_rol=nombre).first():
                flash("Ya existe un rol con ese nombre.", "danger")
            else:
                db.session.add(Rol(nombre_rol=nombre))
                db.session.commit()
                flash("Rol creado.", "success")
                return redirect(url_for("roles_list"))
        return render_template("rol_form.html", form=form, is_new=True)

    @app.route("/roles/<int:rol_id>/editar", methods=["GET", "POST"])
    @admin_required
    def rol_edit(rol_id):
        rol = Rol.query.get_or_404(rol_id)
        form = RolForm(obj=rol)
        if form.validate_on_submit():
            nombre = form.nombre_rol.data.strip()
            existente = Rol.query.filter(Rol.nombre_rol == nombre, Rol.id_rol != rol.id_rol).first()
            if existente:
                flash("Ya existe otro rol con ese nombre.", "danger")
            else:
                rol.nombre_rol = nombre
                db.session.commit()
                flash("Rol actualizado.", "success")
                return redirect(url_for("roles_list"))
        return render_template("rol_form.html", form=form, is_new=False)

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

    # --- GESTIÓN DE EMPLEADOS ---
    @app.get("/empleados")
    @admin_required
    def empleados_list():
        empresa_id = session.get("empresa_id")
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.apellidos).all()
        return render_template("empleados_list.html", empleados=empleados)

    @app.route("/empleados/nuevo", methods=["GET", "POST"])
    @admin_required
    def empleado_new():
        empresa_id = session.get("empresa_id")
        form = TrabajadorForm()
        form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in Rol.query.all()]
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.all()]

        if form.validate_on_submit():
            nif = form.nif.data.strip().upper()
            if Trabajador.query.filter_by(nif=nif).first():
                flash("Ya existe un empleado con ese NIF.", "danger")
            else:
                nuevo = Trabajador(
                    nif=nif, nombre=form.nombre.data, apellidos=form.apellidos.data,
                    email=form.email.data, telef=form.telef.data, idEmpresa=empresa_id,
                    idHorario=form.horario_id.data, idRol=form.rol_id.data
                )
                nuevo.set_password(form.passw.data)
                db.session.add(nuevo)
                db.session.commit()
                flash("Empleado creado.", "success")
                return redirect(url_for("empleados_list"))
        return render_template("empleados_form.html", form=form, is_new=True)

    @app.route("/empleados/<int:emp_id>/editar", methods=["GET", "POST"])
    @admin_required
    def empleado_edit(emp_id):
        empresa_id = session.get("empresa_id")
        empleado = Trabajador.query.get_or_404(emp_id)

        if empleado.idEmpresa != empresa_id:
            flash("Acceso denegado.", "danger")
            return redirect(url_for("empleados_list"))

        form = TrabajadorForm(obj=empleado)
        form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in Rol.query.all()]
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.all()]

        # Preseleccionar horario en GET
        if request.method == 'GET':
            form.horario_id.data = empleado.idHorario

        if form.validate_on_submit():
            empleado.nif = form.nif.data
            empleado.nombre = form.nombre.data
            empleado.apellidos = form.apellidos.data
            empleado.email = form.email.data
            empleado.telef = form.telef.data
            empleado.idRol = form.rol_id.data
            empleado.idHorario = form.horario_id.data

            if form.passw.data:
                empleado.set_password(form.passw.data)

            db.session.commit()
            flash("Empleado actualizado.", "success")
            return redirect(url_for("empleados_list"))

        return render_template("empleados_form.html", form=form, titulo="Editar Empleado", is_new=False)

    @app.post("/empleados/<int:emp_id>/eliminar")
    @admin_required
    def empleado_delete(emp_id):
        empleado = Trabajador.query.get_or_404(emp_id)
        db.session.delete(empleado)
        db.session.commit()
        flash("Empleado eliminado.", "success")
        return redirect(url_for("empleados_list"))

    # --- GESTIÓN DE HORARIOS Y FRANJAS ---
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
            if Horario.query.filter_by(nombre_horario=nombre).first():
                flash("Ya existe un horario con ese nombre.", "danger")
            else:
                db.session.add(Horario(nombre_horario=nombre, descripcion=form.descripcion.data))
                db.session.commit()
                flash("Horario creado.", "success")
                return redirect(url_for("horarios_list"))
        return render_template("horario_form.html", form=form, titulo="Nuevo horario", is_new=True)

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
        return render_template("horario_form.html", form=form, titulo="Editar horario", is_new=False)

    @app.post("/horarios/<int:horario_id>/eliminar")
    @admin_required
    def horario_delete(horario_id):
        horario = Horario.query.get_or_404(horario_id)
        if horario.trabajadores:
            flash("No se puede eliminar un horario con empleados.", "danger")
        else:
            db.session.delete(horario)
            db.session.commit()
            flash("Horario eliminado.", "success")
        return redirect(url_for("horarios_list"))

    @app.route("/horarios/<int:horario_id>/franjas", methods=["GET", "POST"])
    @admin_required
    def horario_franjas(horario_id):
        horario = Horario.query.get_or_404(horario_id)

        if request.method == "POST":
            # Redirección si se usan los checkboxes de días aquí por error
            if "lunes" in request.form or "martes" in request.form:
                 return redirect(url_for("horario_franjas", horario_id=horario_id))

            h_inicio = request.form.get("hora_inicio")
            h_fin = request.form.get("hora_fin")

            if h_inicio and h_fin:
                try:
                    nueva = Franja(
                        id_horario=horario_id,
                        id_dia=1,
                        hora_entrada=datetime.strptime(h_inicio, "%H:%M").time(),
                        hora_salida=datetime.strptime(h_fin, "%H:%M").time()
                    )
                    db.session.add(nueva)
                    db.session.commit()
                    flash("Franja añadida.", "success")
                except ValueError:
                    flash("Formato de hora inválido.", "danger")

            return redirect(url_for("horario_franjas", horario_id=horario_id))

        franjas = Franja.query.filter_by(id_horario=horario_id).order_by(Franja.hora_entrada).all()
        return render_template("horario_franjas.html", horario=horario, franjas=franjas)

    @app.post("/horarios/<int:horario_id>/dias")
    @admin_required
    def horario_update_dias(horario_id):
        horario = Horario.query.get_or_404(horario_id)
        horario.lunes = True if request.form.get("lunes") else False
        horario.martes = True if request.form.get("martes") else False
        horario.miercoles = True if request.form.get("miercoles") else False
        horario.jueves = True if request.form.get("jueves") else False
        horario.viernes = True if request.form.get("viernes") else False
        horario.sabado = True if request.form.get("sabado") else False
        horario.domingo = True if request.form.get("domingo") else False

        db.session.commit()
        flash("Días laborables actualizados.", "success")
        return redirect(url_for("horario_franjas", horario_id=horario_id))

    @app.post("/franjas/delete/<int:franja_id>")
    @admin_required
    def franja_delete(franja_id):
        franja = Franja.query.get_or_404(franja_id)
        h_id = franja.id_horario
        db.session.delete(franja)
        db.session.commit()
        flash("Franja eliminada.", "success")
        return redirect(url_for("horario_franjas", horario_id=h_id))

    # --- GESTIÓN DE INCIDENCIAS ---

    @app.get("/incidencias")
    @admin_required
    def incidencias_list():
        empresa_id = session.get("empresa_id")
        incidencias = (
            Incidencia.query.join(Trabajador)
            .filter(Trabajador.idEmpresa == empresa_id)
            .order_by(Incidencia.fecha_solicitud.desc())
            .all()
        )
        return render_template("incidencias_list.html", incidencias=incidencias)

    # CREAR INCIDENCIA (ADMIN)
    @app.route("/incidencias/nueva", methods=["GET", "POST"])
    @admin_required
    def incidencia_nueva():
        empresa_id = session.get("empresa_id")
        form = IncidenciaCrearForm()

        # Cargar el selector de empleados SOLO con los de mi empresa
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()
        form.trabajador_id.choices = [(t.id_trabajador, f"{t.nombre} {t.apellidos}") for t in empleados]

        if form.validate_on_submit():
            # Crear la incidencia
            nueva_incidencia = Incidencia(
                id_trabajador=form.trabajador_id.data,
                tipo=form.tipo.data,
                fecha_inicio=form.fecha_inicio.data,
                fecha_fin=form.fecha_fin.data,
                comentario_trabajador=form.comentario.data, # Nota inicial del admin
                estado='APROBADA', # Nace aprobada
                comentario_admin="Creada manualmente por Administración."
            )

            db.session.add(nueva_incidencia)
            db.session.commit()

            flash("Incidencia creada y aprobada correctamente.", "success")
            return redirect(url_for("incidencias_list"))

        return render_template("incidencia_crear.html", form=form)

    @app.route("/incidencias/<int:incidencia_id>/resolver", methods=["GET", "POST"])
    @admin_required
    def incidencia_resolver(incidencia_id):
        incidencia = Incidencia.query.get_or_404(incidencia_id)
        empresa_id = session.get("empresa_id")

        if incidencia.trabajador.idEmpresa != empresa_id:
            flash("No tienes permiso.", "danger")
            return redirect(url_for("incidencias_list"))

        form = IncidenciaAdminForm(obj=incidencia)

        if form.validate_on_submit():
            incidencia.estado = form.estado.data
            incidencia.comentario_admin = form.comentario_admin.data
            db.session.commit()

            if incidencia.estado == 'APROBADA':
                flash("Incidencia aprobada.", "success")
            elif incidencia.estado == 'RECHAZADA':
                flash("Incidencia rechazada.", "warning")
            else:
                flash("Incidencia actualizada.", "info")

            return redirect(url_for("incidencias_list"))

        return render_template("incidencia_resolver.html", form=form, incidencia=incidencia)

    # --- VISUALIZACIÓN DE FICHAJES (Agrupado y Limpio) ---
    @app.get("/fichajes")
    @admin_required
    def fichajes_list():
        empresa_id = session.get("empresa_id")

        # 1. Filtros
        filtro_empleado = request.args.get('empleado_id', type=int)
        filtro_fecha = request.args.get('fecha')

        # 2. Query Base
        query = Fichaje.query.join(Trabajador).filter(Trabajador.idEmpresa == empresa_id)

        if filtro_empleado:
            query = query.filter(Trabajador.id_trabajador == filtro_empleado)

        if filtro_fecha:
            query = query.filter(db.func.date(Fichaje.fecha_hora) == filtro_fecha)

        # 3. Obtener datos (Importante: Orden ascendente para procesar cronológicamente)
        # Limitamos a 500 para no saturar si no hay filtros
        fichajes_raw = query.order_by(Fichaje.fecha_hora.asc()).limit(500).all()

        # 4. ALGORITMO DE AGRUPACIÓN
        jornadas = []
        pendientes = {} # {id_trabajador: objeto_fichaje_entrada}

        for f in fichajes_raw:
            emp_id = f.id_trabajador

            if f.tipo == 'ENTRADA':
                # Si ya hay una entrada pendiente -> Error Zombie (Entrada sin salida previa)
                if emp_id in pendientes:
                    entrada_previa = pendientes[emp_id]
                    jornadas.append({
                        'trabajador': entrada_previa.trabajador,
                        'entrada': entrada_previa,
                        'salida': None,
                        'duracion': "Sin cierre",
                        'status': 'error', # Para CSS
                        'is_zombie': True, # Flag para icono
                        'fecha_ref': entrada_previa.fecha_hora
                    })

                # Guardamos la nueva entrada
                pendientes[emp_id] = f

            elif f.tipo == 'SALIDA':
                if emp_id in pendientes:
                    # Cierre de ciclo correcto
                    entrada = pendientes.pop(emp_id)
                    delta = f.fecha_hora - entrada.fecha_hora
                    horas = delta.total_seconds() / 3600

                    # Formato legible: "8h 30m"
                    duracion_txt = f"{int(horas)}h {int((horas*60)%60)}m"
                    status = 'closed'
                    is_long = False

                    if horas > 12: # Turno sospechosamente largo
                        status = 'warning'
                        is_long = True

                    jornadas.append({
                        'trabajador': entrada.trabajador,
                        'entrada': entrada,
                        'salida': f,
                        'duracion': duracion_txt,
                        'status': status,
                        'is_long': is_long,
                        'fecha_ref': entrada.fecha_hora
                    })
                else:
                    # Salida huérfana (Sin entrada registrada)
                    jornadas.append({
                        'trabajador': f.trabajador,
                        'entrada': None,
                        'salida': f,
                        'duracion': "Registro huérfano",
                        'status': 'error',
                        'is_orphan': True,
                        'fecha_ref': f.fecha_hora
                    })

        # 5. Procesar los que siguen trabajando (Pendientes al final)
        for emp_id, entrada in pendientes.items():
            delta = datetime.now() - entrada.fecha_hora
            horas = delta.total_seconds() / 3600

            status = 'active'
            is_long = False

            if horas > 16: # Olvido probable (más de 16h abierto)
                status = 'error'
                is_long = True

            jornadas.append({
                'trabajador': entrada.trabajador,
                'entrada': entrada,
                'salida': None,
                'duracion': f"En curso ({int(horas)}h)",
                'status': status,
                'is_active': (status == 'active'),
                'is_long': is_long,
                'fecha_ref': entrada.fecha_hora
            })

        # Ordenar del más reciente al más antiguo para la vista
        jornadas.sort(key=lambda x: x['fecha_ref'], reverse=True)

        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()

        return render_template("fichajes_list.html",
                               jornadas=jornadas,
                               empleados=empleados,
                               filtro_empleado=filtro_empleado,
                               filtro_fecha=filtro_fecha)

    # NUEVA RUTA: FICHAJE MANUAL (ADMIN)
    @app.route("/fichajes/nuevo", methods=["GET", "POST"])
    @admin_required
    def fichaje_nuevo():
        empresa_id = session.get("empresa_id")
        empresa = Empresa.query.get(empresa_id)

        form = FichajeManualForm()
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()
        form.trabajador_id.choices = [(t.id_trabajador, f"{t.nombre} {t.apellidos}") for t in empleados]

        if form.validate_on_submit():
            # --- NUEVO: VALIDACIÓN DE FECHA ---
            if form.fecha_hora.data > datetime.now():
                flash("No puedes registrar fichajes en el futuro.", "danger")
                return render_template("fichaje_manual.html", form=form)
            # ----------------------------------

            lat = empresa.latitud if empresa.latitud else 0.0
            lon = empresa.longitud if empresa.longitud else 0.0

            nuevo_fichaje = Fichaje(
                id_trabajador=form.trabajador_id.data,
                tipo=form.tipo.data,
                fecha_hora=form.fecha_hora.data,
                latitud=lat,
                longitud=lon
            )

            db.session.add(nuevo_fichaje)
            db.session.commit()

            flash("Fichaje manual registrado correctamente.", "success")
            return redirect(url_for("fichajes_list"))

        return render_template("fichaje_manual.html", form=form)

    # --- GESTIÓN DE EMPRESAS (SUPERADMIN) ---
    @app.get("/empresas")
    @admin_required
    def empresas_list():
        return render_template("empresas_list.html", empresas=Empresa.query.all())

    @app.route("/empresas/nueva", methods=["GET", "POST"])
    @admin_required
    def empresa_new():
        form = EmpresaForm()
        if form.validate_on_submit():
            empresa = Empresa(
                nombrecomercial=form.nombrecomercial.data,
                cif=form.cif.data,
                latitud=form.latitud.data, longitud=form.longitud.data, radio=form.radio.data
            )
            db.session.add(empresa)
            db.session.commit()
            flash("Empresa creada.", "success")
            return redirect(url_for("empresas_list"))
        return render_template("empresa_form.html", form=form, titulo="Nueva Empresa")

    @app.post("/empresas/<int:empresa_id>/eliminar")
    @admin_required
    def empresa_delete(empresa_id):
        empresa = Empresa.query.get_or_404(empresa_id)
        if empresa.trabajadores:
            flash("No se puede eliminar, tiene empleados.", "danger")
        else:
            db.session.delete(empresa)
            db.session.commit()
            flash("Empresa eliminada.", "success")
        return redirect(url_for("empresas_list"))

    return app

app = create_app()
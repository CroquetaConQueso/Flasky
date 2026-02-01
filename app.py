import string
import random
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, flash, session, request
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from config import Config
from extensions import db, migrate, jwt, api
from models import Trabajador, Empresa, Rol, Horario, Dia, Franja, Incidencia, Fichaje


from utils.email_sender import enviar_correo_password

# Importamos los formularios
from forms import (
    LoginForm, EmpresaForm, RolForm, TrabajadorForm, HorarioForm,
    FranjaForm, IncidenciaAdminForm, IncidenciaCrearForm, FichajeManualForm,
    RequestPasswordForm
)

# Blueprints de la API
from resources.auth import blp as AuthBlueprint
from resources.empresa import blp as EmpresaBlueprint
from resources.fichaje import blp as FichajeBlueprint


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicialización de Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    api.init_app(app)

    # Registro de Blueprints (API)
    api.register_blueprint(AuthBlueprint, url_prefix="/api")
    api.register_blueprint(EmpresaBlueprint, url_prefix="/api")
    api.register_blueprint(FichajeBlueprint, url_prefix="/api")

    # ==========================================
    #      DECORADORES DE SEGURIDAD (BLINDADOS)
    # ==========================================

    def admin_required(view):
        """Permite acceso a Administradores y Superadministradores."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return redirect(url_for("login"))

            try:
                trabajador = Trabajador.query.get(user_id)
            except OperationalError:
                # Si se pierde la conexión con la BBDD, limpiamos sesión para evitar bucles
                db.session.remove()
                session.clear()
                flash("Error de conexión. Por favor, identifícate de nuevo.", "danger")
                return redirect(url_for("login"))

            # Verificación estricta de existencia y rol
            if not trabajador or not trabajador.rol:
                flash("Acceso denegado: Usuario no válido o sin rol.", "danger")
                return redirect(url_for("login"))

            # Permitimos tanto 'administrador' como 'superadministrador'
            rol_actual = trabajador.rol.nombre_rol.lower().strip()
            if rol_actual not in ("administrador", "superadministrador", "superadmin"):
                flash("Necesitas permisos de Administrador para acceder aquí.", "danger")
                return redirect(url_for("login"))

            return view(*args, **kwargs)
        return wrapped

    def superadmin_required(view):
        """Permite acceso EXCLUSIVO a Superadministradores (Gestión Global)."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return redirect(url_for("login"))

            trabajador = Trabajador.query.get(user_id)

            # BLINDAJE: Verificamos que 'rol' exista antes de acceder a 'nombre_rol'
            # Esto evita el error "Something went wrong" si un usuario pierde su rol en la BBDD
            if not trabajador or not trabajador.rol:
                flash("Error de integridad: Usuario sin rol asignado.", "danger")
                return redirect(url_for("panel"))

            if trabajador.rol.nombre_rol.lower() not in ("superadministrador", "superadmin", "root"):
                flash("Acceso restringido exclusivamente a Superadministradores.", "danger")
                return redirect(url_for("panel"))

            return view(*args, **kwargs)
        return wrapped


    # ==========================================
    #            RUTAS PÚBLICAS Y LOGIN
    # ==========================================

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        form = LoginForm()
        # Cargamos empresas para el selector
        empresas = Empresa.query.order_by(Empresa.nombrecomercial).all()
        form.empresa_id.choices = [(e.id_empresa, e.nombrecomercial) for e in empresas]

        if form.validate_on_submit():
            identificador = form.nif.data.strip()
            # Búsqueda Robusta: Probamos original, minúsculas y mayúsculas
            posibles_valores = {identificador, identificador.lower(), identificador.upper()}

            # Buscamos por NIF o EMAIL
            trabajador = Trabajador.query.filter(
                or_(
                    Trabajador.nif.in_(posibles_valores),
                    Trabajador.email.in_(posibles_valores)
                )
            ).first()
            if trabajador and trabajador.check_password(form.password.data):
                # Extracción segura del nombre del rol
                rol_nombre = trabajador.rol.nombre_rol.lower().strip() if trabajador.rol else ""

                permiso_concedido = False
                roles_super = ["superadministrador", "superadmin", "root"]

                # Lógica de Permisos:
                # 1. Superadmin entra a cualquier sitio.
                # 2. Admin normal solo entra si selecciona SU empresa.
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
                    return redirect(url_for("panel"))
            else:
                flash("Credenciales incorrectas. Verifica NIF/Email y contraseña.", "danger")

        return render_template("login.html", form=form)

    # --- RECUPERACIÓN DE CONTRASEÑA (WEB) ---
    @app.route("/reset-password", methods=["GET", "POST"])
    def reset_password_web():
        if session.get("user_id"):
            return redirect(url_for("panel"))

        form = RequestPasswordForm()

        if form.validate_on_submit():
            email = form.email.data.strip()
            # Buscamos al trabajador por email
            trabajador = Trabajador.query.filter_by(email=email).first()

            if trabajador:
                # Generar contraseña aleatoria de 8 caracteres
                caracteres = string.ascii_letters + string.digits
                nueva_pass = ''.join(random.choice(caracteres) for i in range(8))

                # Guardar en BBDD
                trabajador.set_password(nueva_pass)
                db.session.commit()

                # Enviar correo
                enviado = enviar_correo_password(trabajador.email, trabajador.nombre, nueva_pass)

                if enviado:
                    flash("Se ha enviado una nueva contraseña a tu correo.", "success")
                    return redirect(url_for("login"))
                else:
                    flash("Error al enviar el correo. Inténtalo más tarde.", "danger")
            else:
                # Por seguridad, no decimos si el email existe o no, pero mostramos éxito visual
                flash("Si el correo existe, recibirás una nueva contraseña.", "info")
                return redirect(url_for("login"))

        return render_template("reset_password.html", form=form)

    @app.get("/logout")
    def logout():
        session.clear()
        flash("Sesión cerrada correctamente.", "info")
        return redirect(url_for("index"))


    # ==========================================
    #             PANEL DE CONTROL
    # ==========================================

    @app.get("/panel")
    @admin_required
    def panel():
        trabajador = Trabajador.query.get(session.get("user_id"))
        empresa_id = session.get("empresa_id")
        empresa = Empresa.query.get(empresa_id) if empresa_id else None

        stats = { "empleados": 0, "horarios": 0, "roles": 0, "fichajes_total": 0 }

        if empresa_id:
            stats["empleados"] = Trabajador.query.filter_by(idEmpresa=empresa_id).count()
            stats["horarios"] = Horario.query.count() # Los horarios suelen ser globales o compartidos
            stats["roles"] = Rol.query.count()

            # Contamos fichajes solo de empleados de esta empresa
            ids_empleados = [t.id_trabajador for t in Trabajador.query.filter_by(idEmpresa=empresa_id).all()]
            if ids_empleados:
                stats["fichajes_total"] = Fichaje.query.filter(Fichaje.id_trabajador.in_(ids_empleados)).count()

        return render_template("panel.html", trabajador=trabajador, empresa=empresa, stats=stats)


    # ==========================================
    #       GESTIÓN DE EMPRESA (ADMIN)
    # ==========================================

    @app.route("/empresa", methods=["GET", "POST"])
    @admin_required
    def empresa_view():
        empresa_id = session.get("empresa_id")
        if not empresa_id:
            return redirect(url_for("login"))

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

            return redirect(url_for("empresa_view"))

        return render_template("empresa.html", form=form)


    # ==========================================
    #    GESTIÓN GLOBAL EMPRESAS (SUPERADMIN)
    # ==========================================

    @app.get("/empresas")
    @superadmin_required
    def empresas_list():
        return render_template("empresas_list.html", empresas=Empresa.query.all())

    @app.route("/empresas/nueva", methods=["GET", "POST"])
    @superadmin_required
    def empresa_new():
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
            return redirect(url_for("empresas_list"))
        return render_template("empresa_form.html", form=form, titulo="Nueva Empresa")

    @app.post("/empresas/<int:empresa_id>/eliminar")
    @superadmin_required
    def empresa_delete(empresa_id):
        empresa = Empresa.query.get_or_404(empresa_id)

        # Comprobar si estamos borrando la empresa en la que estamos logueados
        empresa_activa_id = session.get("empresa_id")
        es_empresa_activa = (empresa_activa_id == empresa.id_empresa)

        if empresa.trabajadores:
            flash("No puedes eliminar una empresa que tiene empleados activos. Borra o mueve a los empleados primero.", "danger")
        else:
            db.session.delete(empresa)
            db.session.commit()

            if es_empresa_activa:
                session.clear()
                flash("Has eliminado la empresa activa. Se ha cerrado la sesión por seguridad.", "info")
                return redirect(url_for("login"))

            flash("Empresa eliminada correctamente.", "success")

        return redirect(url_for("empresas_list"))


    # ==========================================
    #      GESTIÓN GLOBAL ROLES (SUPERADMIN)
    # ==========================================

    @app.get("/roles")
    @superadmin_required
    def roles_list():
        roles = Rol.query.order_by(Rol.nombre_rol).all()
        return render_template("roles_list.html", roles=roles)

    @app.route("/roles/nuevo", methods=["GET", "POST"])
    @superadmin_required
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
    @superadmin_required
    def rol_edit(rol_id):
        rol = Rol.query.get_or_404(rol_id)
        form = RolForm(obj=rol)
        if form.validate_on_submit():
            nombre = form.nombre_rol.data.strip()
            # Comprobar duplicados excluyendo el actual
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
    @superadmin_required
    def rol_delete(rol_id):
        rol = Rol.query.get_or_404(rol_id)
        if rol.trabajadores:
            flash("No se puede eliminar: Hay empleados asignados a este rol.", "danger")
        else:
            db.session.delete(rol)
            db.session.commit()
            flash("Rol eliminado.", "success")
        return redirect(url_for("roles_list"))


    # ==========================================
    #          GESTIÓN DE EMPLEADOS
    # ==========================================

    @app.get("/empleados")
    @admin_required
    def empleados_list():
        empresa_id = session.get("empresa_id")
        # Solo listamos empleados de la empresa actual
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.apellidos).all()
        return render_template("empleados_list.html", empleados=empleados)

    @app.route("/empleados/nuevo", methods=["GET", "POST"])
    @admin_required
    def empleado_new():
        empresa_id = session.get("empresa_id")
        form = TrabajadorForm()

        # Cargar opciones de selects
        form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in Rol.query.all()]
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.all()]

        if form.validate_on_submit():
            nif = form.nif.data.strip().upper()
            if Trabajador.query.filter_by(nif=nif).first():
                flash("El NIF introducido ya está registrado en el sistema.", "danger")
            else:
                nuevo = Trabajador(
                    nif=nif,
                    nombre=form.nombre.data,
                    apellidos=form.apellidos.data,
                    email=form.email.data,
                    telef=form.telef.data,
                    idEmpresa=empresa_id,
                    idHorario=form.horario_id.data,
                    idRol=form.rol_id.data
                )
                # La contraseña es opcional, pero si la ponen, la hasheamos
                if form.passw.data:
                    nuevo.set_password(form.passw.data)

                db.session.add(nuevo)
                db.session.commit()
                flash("Empleado creado correctamente.", "success")
                return redirect(url_for("empleados_list"))
        return render_template("empleados_form.html", form=form, is_new=True)

    @app.route("/empleados/<int:emp_id>/editar", methods=["GET", "POST"])
    @admin_required
    def empleado_edit(emp_id):
        empresa_id = session.get("empresa_id")
        empleado = Trabajador.query.get_or_404(emp_id)

        # Seguridad: No editar empleados de otras empresas
        if empleado.idEmpresa != empresa_id:
            flash("Acceso denegado: Este empleado no pertenece a tu empresa.", "danger")
            return redirect(url_for("empleados_list"))

        form = TrabajadorForm(obj=empleado)
        form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in Rol.query.all()]
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.all()]

        # Precarga del select de horario
        if request.method == 'GET':
            form.horario_id.data = empleado.idHorario

        if form.validate_on_submit():
            # Actualizamos campos
            form.populate_obj(empleado)

            # Solo actualizamos contraseña si el campo no está vacío
            if form.passw.data:
                empleado.set_password(form.passw.data)

            db.session.commit()
            flash("Datos del empleado actualizados.", "success")
            return redirect(url_for("empleados_list"))

        return render_template("empleados_form.html", form=form, titulo="Editar Empleado", is_new=False)

    @app.post("/empleados/<int:emp_id>/eliminar")
    @admin_required
    def empleado_delete(emp_id):
        empleado = Trabajador.query.get_or_404(emp_id)
        if empleado.idEmpresa != session.get("empresa_id"):
             flash("Error de seguridad: Intento de borrar empleado externo.", "danger")
             return redirect(url_for("empleados_list"))

        db.session.delete(empleado)
        db.session.commit()
        flash("Empleado eliminado del sistema.", "success")
        return redirect(url_for("empleados_list"))


    # ==========================================
    #           GESTIÓN DE HORARIOS
    # ==========================================

    @app.get("/horarios")
    @admin_required
    def horarios_list():
        # Los horarios son globales para simplificar, o se podrían filtrar por empresa si se añade idEmpresa a Horario
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
            flash("No se puede eliminar: Hay empleados usando este horario.", "danger")
        else:
            db.session.delete(horario)
            db.session.commit()
            flash("Horario eliminado.", "success")
        return redirect(url_for("horarios_list"))

    @app.route("/horarios/<int:horario_id>/franjas", methods=["GET", "POST"])
    @admin_required
    def horario_franjas(horario_id):
        """Gestión de franjas horarias y días activos."""
        horario = Horario.query.get_or_404(horario_id)

        if request.method == "POST":
            # Si el POST viene de los checkboxes de días (contiene 'lunes', 'martes'...)
            # Redirigimos al handler específico o lo procesamos si no hay form separado
            # Aquí asumimos que el form de añadir franja tiene campos 'hora_inicio'

            if "lunes" in request.form or "martes" in request.form:
                 # Es un update de días, lo dejamos pasar al endpoint específico o lo manejamos aquí
                 # Para limpieza, mejor redirigir si se usa htmx o similar, pero aquí lo procesamos abajo
                 pass

            h_inicio = request.form.get("hora_inicio")
            h_fin = request.form.get("hora_fin")

            # Lógica para AÑADIR FRANJA
            if h_inicio and h_fin:
                try:
                    nueva = Franja(
                        id_horario=horario_id,
                        id_dia=1, # Por defecto asignamos a un día genérico o todos
                        hora_entrada=datetime.strptime(h_inicio, "%H:%M").time(),
                        hora_salida=datetime.strptime(h_fin, "%H:%M").time()
                    )
                    db.session.add(nueva)
                    db.session.commit()
                    flash("Franja horaria añadida.", "success")
                except ValueError:
                    flash("Formato de hora inválido.", "danger")

            return redirect(url_for("horario_franjas", horario_id=horario_id))

        franjas = Franja.query.filter_by(id_horario=horario_id).order_by(Franja.hora_entrada).all()
        return render_template("horario_franjas.html", horario=horario, franjas=franjas)

    @app.post("/horarios/<int:horario_id>/dias")
    @admin_required
    def horario_update_dias(horario_id):
        """Actualiza qué días de la semana aplica el horario."""
        horario = Horario.query.get_or_404(horario_id)
        dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

        for dia in dias:
            # Checkbox HTML: Si está marcado envía 'on', si no, no envía nada.
            valor = True if request.form.get(dia) else False
            setattr(horario, dia, valor)

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


    # ==========================================
    #          GESTIÓN DE INCIDENCIAS
    # ==========================================

    @app.get("/incidencias")
    @admin_required
    def incidencias_list():
        empresa_id = session.get("empresa_id")
        # Mostrar incidencias de los empleados de mi empresa, ordenadas por fecha reciente
        incidencias = (
            Incidencia.query.join(Trabajador)
            .filter(Trabajador.idEmpresa == empresa_id)
            .order_by(Incidencia.fecha_solicitud.desc())
            .all()
        )
        return render_template("incidencias_list.html", incidencias=incidencias)

    @app.route("/incidencias/nueva", methods=["GET", "POST"])
    @admin_required
    def incidencia_nueva():
        empresa_id = session.get("empresa_id")
        form = IncidenciaCrearForm()
        # Llenar select con empleados de la empresa
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()
        form.trabajador_id.choices = [(t.id_trabajador, f"{t.nombre} {t.apellidos}") for t in empleados]

        if form.validate_on_submit():
            nueva_incidencia = Incidencia(
                id_trabajador=form.trabajador_id.data,
                tipo=form.tipo.data,
                fecha_inicio=form.fecha_inicio.data,
                fecha_fin=form.fecha_fin.data,
                comentario_trabajador=form.comentario.data,
                estado='APROBADA', # Si la crea el admin, nace aprobada
                comentario_admin="Creada manualmente por Administración."
            )
            db.session.add(nueva_incidencia)
            db.session.commit()
            flash("Incidencia registrada y aprobada.", "success")
            return redirect(url_for("incidencias_list"))

        return render_template("incidencia_crear.html", form=form)

    @app.route("/incidencias/<int:incidencia_id>/resolver", methods=["GET", "POST"])
    @admin_required
    def incidencia_resolver(incidencia_id):
        incidencia = Incidencia.query.get_or_404(incidencia_id)
        empresa_id = session.get("empresa_id")

        if incidencia.trabajador.idEmpresa != empresa_id:
            flash("No tienes permiso para gestionar esta incidencia.", "danger")
            return redirect(url_for("incidencias_list"))

        form = IncidenciaAdminForm(obj=incidencia)

        if form.validate_on_submit():
            incidencia.estado = form.estado.data
            incidencia.comentario_admin = form.comentario_admin.data
            db.session.commit()
            flash(f"Incidencia {incidencia.estado.lower()}.", "success")
            return redirect(url_for("incidencias_list"))

        return render_template("incidencia_resolver.html", form=form, incidencia=incidencia)


    # ==========================================
    #      GESTIÓN AVANZADA DE FICHAJES
    # ==========================================

    @app.get("/fichajes")
    @admin_required
    def fichajes_list():
        empresa_id = session.get("empresa_id")

        # Filtros
        filtro_empleado = request.args.get('empleado_id', type=int)
        filtro_fecha = request.args.get('fecha')

        query = Fichaje.query.join(Trabajador).filter(Trabajador.idEmpresa == empresa_id)

        if filtro_empleado:
            query = query.filter(Trabajador.id_trabajador == filtro_empleado)
        if filtro_fecha:
            query = query.filter(db.func.date(Fichaje.fecha_hora) == filtro_fecha)

        # Obtenemos TODOS los fichajes ordenados cronológicamente
        # Limitamos a 1000 para no saturar la vista si no hay filtros
        fichajes_raw = query.order_by(Fichaje.fecha_hora.asc()).limit(1000).all()

        jornadas = []
        pendientes = {} # Diccionario para guardar entradas abiertas: {id_trabajador: objeto_fichaje_entrada}

        # ALGORITMO DE EMPAREJAMIENTO (Reconstruido)
        for f in fichajes_raw:
            emp_id = f.id_trabajador

            if f.tipo == 'ENTRADA':
                if emp_id in pendientes:
                    # ERROR: Ya tenía una entrada sin cerrar -> La anterior es "Zombie"
                    prev = pendientes[emp_id]
                    jornadas.append({
                        'trabajador': prev.trabajador,
                        'entrada': prev,
                        'salida': None,
                        'duracion': "Error: Sin salida",
                        'status': 'error',
                        'is_zombie': True,
                        'fecha_ref': prev.fecha_hora
                    })
                # Registramos la nueva entrada como pendiente
                pendientes[emp_id] = f

            elif f.tipo == 'SALIDA':
                if emp_id in pendientes:
                    # CORRECTO: Cerramos la jornada
                    ent = pendientes.pop(emp_id)
                    delta = f.fecha_hora - ent.fecha_hora
                    horas = delta.total_seconds() / 3600

                    # Detectar jornadas sospechosamente largas (>12h)
                    status = 'warning' if horas > 12 else 'closed'
                    duracion_txt = f"{int(horas)}h {int((horas*60)%60)}m"

                    jornadas.append({
                        'trabajador': ent.trabajador,
                        'entrada': ent,
                        'salida': f,
                        'duracion': duracion_txt,
                        'status': status,
                        'is_long': (status=='warning'),
                        'fecha_ref': ent.fecha_hora
                    })
                else:
                    # ERROR: Salida sin entrada previa -> "Huérfana"
                    jornadas.append({
                        'trabajador': f.trabajador,
                        'entrada': None,
                        'salida': f,
                        'duracion': "Error: Sin entrada",
                        'status': 'error',
                        'is_orphan': True,
                        'fecha_ref': f.fecha_hora
                    })

        # Procesar las que quedaron pendientes al final del bucle (Jornadas en curso)
        for emp_id, ent in pendientes.items():
            delta = datetime.now() - ent.fecha_hora
            horas = delta.total_seconds() / 3600

            # Si lleva abierta más de 16h, probablemente se olvidó fichar salida
            status = 'error' if horas > 16 else 'active'
            duracion_txt = f"En curso ({int(horas)}h)"

            jornadas.append({
                'trabajador': ent.trabajador,
                'entrada': ent,
                'salida': None,
                'duracion': duracion_txt,
                'status': status,
                'is_active': (status=='active'),
                'fecha_ref': ent.fecha_hora
            })

        # Ordenar para mostrar lo más reciente primero
        jornadas.sort(key=lambda x: x['fecha_ref'], reverse=True)

        # Cargar empleados para el filtro del select
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()

        return render_template("fichajes_list.html",
                               jornadas=jornadas,
                               empleados=empleados,
                               filtro_empleado=filtro_empleado,
                               filtro_fecha=filtro_fecha)

    @app.route("/fichajes/nuevo", methods=["GET", "POST"])
    @admin_required
    def fichaje_nuevo():
        empresa_id = session.get("empresa_id")
        empresa = Empresa.query.get(empresa_id)
        form = FichajeManualForm()

        # Select con empleados
        empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()
        form.trabajador_id.choices = [(t.id_trabajador, f"{t.nombre} {t.apellidos}") for t in empleados]

        if form.validate_on_submit():
            # Validación extra: No permitir futuro
            if form.fecha_hora.data > datetime.now():
                flash("No puedes registrar fichajes con fecha futura.", "danger")
                return render_template("fichaje_manual.html", form=form)

            nuevo_fichaje = Fichaje(
                id_trabajador=form.trabajador_id.data,
                tipo=form.tipo.data,
                fecha_hora=form.fecha_hora.data,
                latitud=empresa.latitud or 0.0,
                longitud=empresa.longitud or 0.0
            )
            db.session.add(nuevo_fichaje)
            db.session.commit()
            flash("Fichaje manual registrado correctamente.", "success")
            return redirect(url_for("fichajes_list"))

        return render_template("fichaje_manual.html", form=form)

    return app

# Punto de entrada para Gunicorn/WSGI
app = create_app()
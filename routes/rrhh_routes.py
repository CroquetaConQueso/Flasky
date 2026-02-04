from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from models import Trabajador, Rol, Horario, Franja, Fichaje, Empresa, Incidencia, Dia
from forms import TrabajadorForm, HorarioForm, FichajeManualForm, IncidenciaCrearForm, IncidenciaAdminForm
from utils.decorators import admin_required
from utils.email_sender import enviar_correo_resolucion, enviar_correo_ausencia
from extensions import db
from datetime import datetime, timedelta, date, time
import calendar

rrhh_bp = Blueprint('rrhh_web', __name__)

# --- HELPER: CÁLCULO DE HORAS POR RANGO ---
def calcular_resumen_rango(empleado_id, start_date, end_date):
    """
    Calcula horas teóricas vs reales en un rango de fechas flexible.
    start_date y end_date deben ser objetos datetime (o date).
    """
    trabajador = Trabajador.query.get(empleado_id)
    if not trabajador or not trabajador.idHorario:
        return None

    # Asegurar que tenemos datetime para comparar con fichajes
    if isinstance(start_date, date):
        start_date = datetime.combine(start_date, time.min)
    if isinstance(end_date, date):
        end_date = datetime.combine(end_date, time.max)

    # 1. Calcular Horas Teóricas (Según Horario y Franjas)
    dias_semana = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes', 5: 'sabado', 6: 'domingo'}
    horas_por_weekday = {}

    # Pre-calcular horas por día de la semana
    for wd, nombre_dia in dias_semana.items():
        dia_bd = Dia.query.filter_by(nombre=nombre_dia).first()
        if dia_bd:
            franjas = Franja.query.filter_by(id_horario=trabajador.idHorario, id_dia=dia_bd.id).all()
            total_seconds = 0
            for f in franjas:
                t_in = timedelta(hours=f.hora_entrada.hour, minutes=f.hora_entrada.minute)
                t_out = timedelta(hours=f.hora_salida.hour, minutes=f.hora_salida.minute)
                total_seconds += (t_out - t_in).total_seconds()
            horas_por_weekday[wd] = total_seconds
        else:
            horas_por_weekday[wd] = 0

    # Sumar teóricas día a día dentro del rango
    total_teorico_sec = 0
    delta_days = (end_date - start_date).days + 1

    for i in range(delta_days):
        current_day = start_date + timedelta(days=i)
        wd = current_day.weekday()
        total_teorico_sec += horas_por_weekday.get(wd, 0)

    # 2. Calcular Horas Trabajadas (Reales)
    fichajes = Fichaje.query.filter(
        Fichaje.id_trabajador == empleado_id,
        Fichaje.fecha_hora >= start_date,
        Fichaje.fecha_hora <= end_date
    ).order_by(Fichaje.fecha_hora).all()

    total_trabajado_sec = 0
    pendientes = []

    for f in fichajes:
        if f.tipo == 'ENTRADA':
            pendientes.append(f)
        elif f.tipo == 'SALIDA':
            if pendientes:
                ent = pendientes.pop()
                delta = (f.fecha_hora - ent.fecha_hora).total_seconds()
                total_trabajado_sec += delta

    # 3. Resultados finales
    horas_teoricas = total_teorico_sec / 3600
    horas_trabajadas = total_trabajado_sec / 3600
    saldo = horas_trabajadas - horas_teoricas

    return {
        'rango': f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}",
        'teoricas': round(horas_teoricas, 2),
        'trabajadas': round(horas_trabajadas, 2),
        'saldo': round(saldo, 2)
    }

# --- GESTIÓN DE EMPLEADOS ---

@rrhh_bp.get("/empleados")
@admin_required
def empleados_list():
    empresa_id = session.get("empresa_id")
    empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.apellidos).all()
    return render_template("empleados_list.html", empleados=empleados)

@rrhh_bp.route("/empleados/nuevo", methods=["GET", "POST"])
@admin_required
def empleado_new():
    empresa_id = session.get("empresa_id")
    form = TrabajadorForm()
    form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in Rol.query.all()]

    if hasattr(Horario, 'empresa_id'):
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.filter_by(empresa_id=empresa_id).all()]
    else:
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.all()]

    if form.validate_on_submit():
        nif = form.nif.data.strip().upper()
        if Trabajador.query.filter_by(nif=nif).first():
            flash("El NIF introducido ya está registrado.", "danger")
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
            if form.passw.data:
                nuevo.set_password(form.passw.data)

            db.session.add(nuevo)
            db.session.commit()
            flash("Empleado creado correctamente.", "success")
            return redirect(url_for("rrhh_web.empleados_list"))
    return render_template("empleados_form.html", form=form, is_new=True)

@rrhh_bp.route("/empleados/<int:emp_id>/editar", methods=["GET", "POST"])
@admin_required
def empleado_edit(emp_id):
    empresa_id = session.get("empresa_id")
    empleado = Trabajador.query.get_or_404(emp_id)

    if empleado.idEmpresa != empresa_id:
        flash("Acceso denegado: Empleado externo.", "danger")
        return redirect(url_for("rrhh_web.empleados_list"))

    form = TrabajadorForm(obj=empleado)
    form.rol_id.choices = [(r.id_rol, r.nombre_rol) for r in Rol.query.all()]

    if hasattr(Horario, 'empresa_id'):
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.filter_by(empresa_id=empresa_id).all()]
    else:
        form.horario_id.choices = [(h.id_horario, h.nombre_horario) for h in Horario.query.all()]

    if request.method == 'GET':
        form.horario_id.data = empleado.idHorario

    if form.validate_on_submit():
        form.populate_obj(empleado)
        if form.passw.data:
            empleado.set_password(form.passw.data)
        db.session.commit()
        flash("Datos actualizados.", "success")
        return redirect(url_for("rrhh_web.empleados_list"))

    return render_template("empleados_form.html", form=form, titulo="Editar Empleado", is_new=False)

@rrhh_bp.post("/empleados/<int:emp_id>/eliminar")
@admin_required
def empleado_delete(emp_id):
    empleado = Trabajador.query.get_or_404(emp_id)
    if empleado.idEmpresa != session.get("empresa_id"):
            flash("Error de seguridad.", "danger")
            return redirect(url_for("rrhh_web.empleados_list"))

    db.session.delete(empleado)
    db.session.commit()
    flash("Empleado eliminado.", "success")
    return redirect(url_for("rrhh_web.empleados_list"))

# --- GESTIÓN DE HORARIOS ---

@rrhh_bp.get("/horarios")
@admin_required
def horarios_list():
    empresa_id = session.get("empresa_id")
    try:
        if hasattr(Horario, 'empresa_id'):
            horarios = Horario.query.filter_by(empresa_id=empresa_id).order_by(Horario.nombre_horario).all()
        else:
            horarios = Horario.query.order_by(Horario.nombre_horario).all()
    except:
        horarios = Horario.query.order_by(Horario.nombre_horario).all()
    return render_template("horarios_list.html", horarios=horarios)

@rrhh_bp.route("/horarios/nuevo", methods=["GET", "POST"])
@admin_required
def horario_new():
    empresa_id = session.get("empresa_id")
    form = HorarioForm()
    if form.validate_on_submit():
        nombre = form.nombre_horario.data.strip()

        if hasattr(Horario, 'empresa_id'):
            existe = Horario.query.filter_by(nombre_horario=nombre, empresa_id=empresa_id).first()
        else:
            existe = Horario.query.filter_by(nombre_horario=nombre).first()

        if existe:
            flash("Ya existe un horario con ese nombre.", "danger")
        else:
            nuevo_horario = Horario(
                nombre_horario=nombre,
                descripcion=form.descripcion.data
            )
            if hasattr(nuevo_horario, 'empresa_id'):
                nuevo_horario.empresa_id = empresa_id

            db.session.add(nuevo_horario)
            db.session.commit()
            flash("Horario creado.", "success")
            return redirect(url_for("rrhh_web.horarios_list"))
    return render_template("horario_form.html", form=form, titulo="Nuevo horario", is_new=True)

@rrhh_bp.route("/horarios/<int:horario_id>/editar", methods=["GET", "POST"])
@admin_required
def horario_edit(horario_id):
    horario = Horario.query.get_or_404(horario_id)
    if hasattr(horario, 'empresa_id') and horario.empresa_id != session.get("empresa_id"):
        flash("No tienes permiso.", "danger")
        return redirect(url_for("rrhh_web.horarios_list"))

    form = HorarioForm(obj=horario)
    if form.validate_on_submit():
        horario.nombre_horario = form.nombre_horario.data.strip()
        horario.descripcion = form.descripcion.data
        db.session.commit()
        flash("Horario actualizado.", "success")
        return redirect(url_for("rrhh_web.horarios_list"))

    return render_template("horario_form.html", form=form, titulo="Editar Horario")

@rrhh_bp.post("/horarios/<int:horario_id>/eliminar")
@admin_required
def horario_delete(horario_id):
    horario = Horario.query.get_or_404(horario_id)
    if hasattr(horario, 'empresa_id') and horario.empresa_id != session.get("empresa_id"):
        return redirect(url_for("rrhh_web.horarios_list"))

    if horario.trabajadores:
        flash("No se puede eliminar: Hay empleados usando este horario.", "danger")
    else:
        try:
            Franja.query.filter_by(id_horario=horario_id).delete()
        except:
            pass

        db.session.delete(horario)
        db.session.commit()
        flash("Horario eliminado.", "success")
    return redirect(url_for("rrhh_web.horarios_list"))

# --- GESTIÓN DE FRANJAS ---

@rrhh_bp.route("/horarios/<int:horario_id>/franjas", methods=["GET", "POST"])
@admin_required
def horario_franjas(horario_id):
    horario = Horario.query.get_or_404(horario_id)
    if hasattr(horario, 'empresa_id') and horario.empresa_id != session.get("empresa_id"):
        return redirect(url_for("rrhh_web.horarios_list"))

    dias_disponibles = Dia.query.order_by(Dia.id).all()

    if request.method == "POST":
        if any(dia in request.form for dia in ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]):
             return redirect(url_for("rrhh_web.horario_franjas", horario_id=horario_id))

        h_inicio = request.form.get("hora_inicio")
        h_fin = request.form.get("hora_fin")
        dia_seleccionado = request.form.get("dia_id")

        if h_inicio and h_fin and dia_seleccionado:
            try:
                existe = Franja.query.filter_by(id_horario=horario_id, id_dia=dia_seleccionado).first()
                if existe:
                    flash("Ya existe una franja para ese día. Bórrala antes de crear una nueva.", "warning")
                else:
                    nueva = Franja(
                        id_horario=horario_id,
                        id_dia=int(dia_seleccionado),
                        hora_entrada=datetime.strptime(h_inicio, "%H:%M").time(),
                        hora_salida=datetime.strptime(h_fin, "%H:%M").time()
                    )
                    db.session.add(nueva)
                    db.session.commit()
                    flash("Franja horaria añadida.", "success")
            except ValueError:
                flash("Formato de hora inválido.", "danger")
            except Exception as e:
                db.session.rollback()
                flash(f"Error base de datos: {str(e)}", "danger")
        else:
            flash("Faltan datos obligatorios (Hora o Día).", "warning")

        return redirect(url_for("rrhh_web.horario_franjas", horario_id=horario_id))

    franjas = Franja.query.filter_by(id_horario=horario_id).join(Dia).order_by(Dia.id).all()
    return render_template("horario_franjas.html", horario=horario, franjas=franjas, dias=dias_disponibles)

@rrhh_bp.post("/horarios/<int:horario_id>/dias")
@admin_required
def horario_update_dias(horario_id):
    horario = Horario.query.get_or_404(horario_id)
    if hasattr(horario, 'empresa_id') and horario.empresa_id != session.get("empresa_id"):
        return redirect(url_for("rrhh_web.horarios_list"))

    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    for dia in dias:
        valor = True if request.form.get(dia) else False
        if hasattr(horario, dia):
            setattr(horario, dia, valor)

    db.session.commit()
    flash("Días laborables actualizados.", "success")
    return redirect(url_for("rrhh_web.horario_franjas", horario_id=horario_id))

@rrhh_bp.post("/horarios/<int:horario_id>/franjas/delete/<int:dia_id>")
@admin_required
def franja_delete(horario_id, dia_id):
    franja = Franja.query.get_or_404((dia_id, horario_id))

    if hasattr(franja.horario, 'empresa_id') and franja.horario.empresa_id != session.get("empresa_id"):
        return redirect(url_for("rrhh_web.horarios_list"))

    db.session.delete(franja)
    db.session.commit()
    flash("Franja eliminada.", "success")
    return redirect(url_for("rrhh_web.horario_franjas", horario_id=horario_id))

# --- FICHAJES E INCIDENCIAS (MODIFICADO RANGOS) ---

@rrhh_bp.get("/fichajes")
@admin_required
def fichajes_list():
    empresa_id = session.get("empresa_id")

    # Recogida de filtros (RANGO DE FECHAS)
    filtro_empleado = request.args.get('empleado_id', type=int)
    filtro_desde = request.args.get('fecha_desde')
    filtro_hasta = request.args.get('fecha_hasta')

    query = Fichaje.query.join(Trabajador).filter(Trabajador.idEmpresa == empresa_id)

    if filtro_empleado:
        query = query.filter(Trabajador.id_trabajador == filtro_empleado)

    if filtro_desde:
        query = query.filter(db.func.date(Fichaje.fecha_hora) >= filtro_desde)

    if filtro_hasta:
        query = query.filter(db.func.date(Fichaje.fecha_hora) <= filtro_hasta)

    fichajes_raw = query.order_by(Fichaje.fecha_hora.asc()).limit(2000).all()

    # Procesado de jornadas para la tabla
    jornadas = []
    pendientes = {}

    for f in fichajes_raw:
        emp_id = f.id_trabajador

        if f.tipo == 'ENTRADA':
            if emp_id in pendientes:
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
            pendientes[emp_id] = f

        elif f.tipo == 'SALIDA':
            if emp_id in pendientes:
                ent = pendientes.pop(emp_id)
                delta = f.fecha_hora - ent.fecha_hora
                horas = delta.total_seconds() / 3600
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
                jornadas.append({
                    'trabajador': f.trabajador,
                    'entrada': None,
                    'salida': f,
                    'duracion': "Error: Sin entrada",
                    'status': 'error',
                    'is_orphan': True,
                    'fecha_ref': f.fecha_hora
                })

    # Procesar entradas activas (sin salida aún)
    for emp_id, ent in pendientes.items():
        delta = datetime.now() - ent.fecha_hora
        horas = delta.total_seconds() / 3600
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

    jornadas.sort(key=lambda x: x['fecha_ref'], reverse=True)
    empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()

    # --- CÁLCULO DE RESUMEN POR RANGO ---
    resumen = None
    if filtro_empleado:
        # Si no hay fechas, por defecto mes actual
        if not filtro_desde or not filtro_hasta:
            today = date.today()
            start_date = date(today.year, today.month, 1)
            _, num_days = calendar.monthrange(today.year, today.month)
            end_date = date(today.year, today.month, num_days)
        else:
            # Parsear fechas del filtro
            try:
                start_date = datetime.strptime(filtro_desde, '%Y-%m-%d').date()
                end_date = datetime.strptime(filtro_hasta, '%Y-%m-%d').date()
            except:
                # Fallback a hoy si error
                start_date = date.today()
                end_date = date.today()

        # Llamamos al helper con el rango
        resumen = calcular_resumen_rango(filtro_empleado, start_date, end_date)

    return render_template("fichajes_list.html",
                           jornadas=jornadas,
                           empleados=empleados,
                           filtro_empleado=filtro_empleado,
                           filtro_desde=filtro_desde,
                           filtro_hasta=filtro_hasta,
                           resumen=resumen)

@rrhh_bp.route("/fichajes/nuevo", methods=["GET", "POST"])
@admin_required
def fichaje_nuevo():
    empresa_id = session.get("empresa_id")
    empresa = Empresa.query.get(empresa_id)
    form = FichajeManualForm()
    empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()
    form.trabajador_id.choices = [(t.id_trabajador, f"{t.nombre} {t.apellidos}") for t in empleados]

    if form.validate_on_submit():
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
        return redirect(url_for("rrhh_web.fichajes_list"))

    return render_template("fichaje_manual.html", form=form)

@rrhh_bp.get("/incidencias")
@admin_required
def incidencias_list():
    empresa_id = session.get("empresa_id")

    # Recogida de filtros de la URL
    filtro_empleado = request.args.get('empleado_id', type=int)
    filtro_inicio = request.args.get('fecha_inicio')
    filtro_fin = request.args.get('fecha_fin')

    # Query base filtrada por empresa
    query = Incidencia.query.join(Trabajador).filter(Trabajador.idEmpresa == empresa_id)

    # Aplicación de filtros dinámicos
    if filtro_empleado:
        query = query.filter(Incidencia.id_trabajador == filtro_empleado)

    if filtro_inicio:
        query = query.filter(Incidencia.fecha_inicio >= filtro_inicio)

    if filtro_fin:
        query = query.filter(Incidencia.fecha_fin <= filtro_fin)

    incidencias = query.order_by(Incidencia.fecha_solicitud.desc()).all()

    # Lista de empleados para poblar el select del filtro
    empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()

    return render_template("incidencias_list.html",
                           incidencias=incidencias,
                           empleados=empleados,
                           filtro_empleado=filtro_empleado,
                           filtro_inicio=filtro_inicio,
                           filtro_fin=filtro_fin)

@rrhh_bp.route("/incidencias/nueva", methods=["GET", "POST"])
@admin_required
def incidencia_nueva():
    empresa_id = session.get("empresa_id")
    form = IncidenciaCrearForm()
    empleados = Trabajador.query.filter_by(idEmpresa=empresa_id).order_by(Trabajador.nombre).all()
    form.trabajador_id.choices = [(t.id_trabajador, f"{t.nombre} {t.apellidos}") for t in empleados]

    if form.validate_on_submit():
        nueva_incidencia = Incidencia(
            id_trabajador=form.trabajador_id.data,
            tipo=form.tipo.data,
            fecha_inicio=form.fecha_inicio.data,
            fecha_fin=form.fecha_fin.data,
            comentario_trabajador=form.comentario.data,
            estado='APROBADA',
            comentario_admin="Creada manualmente por Administración."
        )
        db.session.add(nueva_incidencia)
        db.session.commit()
        flash("Incidencia registrada y aprobada.", "success")
        return redirect(url_for("rrhh_web.incidencias_list"))

    return render_template("incidencia_crear.html", form=form)

@rrhh_bp.route("/incidencias/<int:incidencia_id>/resolver", methods=["GET", "POST"])
@admin_required
def incidencia_resolver(incidencia_id):
    incidencia = Incidencia.query.get_or_404(incidencia_id)
    empresa_id = session.get("empresa_id")

    if incidencia.trabajador.idEmpresa != empresa_id:
        flash("No tienes permiso para gestionar esta incidencia.", "danger")
        return redirect(url_for("rrhh_web.incidencias_list"))

    form = IncidenciaAdminForm(obj=incidencia)

    if form.validate_on_submit():
        incidencia.estado = form.estado.data
        incidencia.comentario_admin = form.comentario_admin.data
        db.session.commit()

        enviar_correo_resolucion(
            destinatario=incidencia.trabajador.email,
            nombre=incidencia.trabajador.nombre,
            tipo_incidencia=incidencia.tipo,
            estado=incidencia.estado,
            comentario_admin=incidencia.comentario_admin,
            f_inicio=incidencia.fecha_inicio,
            f_fin=incidencia.fecha_fin
        )

        flash(f"Incidencia {incidencia.estado.lower()} y empleado notificado.", "success")
        return redirect(url_for("rrhh_web.incidencias_list"))

    return render_template("incidencias_resolver.html", form=form, incidencia=incidencia)

@rrhh_bp.post("/incidencias/<int:incidencia_id>/eliminar")
@admin_required
def incidencia_delete(incidencia_id):
    incidencia = Incidencia.query.get_or_404(incidencia_id)
    empresa_id = session.get("empresa_id")

    if incidencia.trabajador.idEmpresa != empresa_id:
        flash("No tienes permiso para eliminar esta incidencia.", "danger")
        return redirect(url_for("rrhh_web.incidencias_list"))

    try:
        db.session.delete(incidencia)
        db.session.commit()
        flash("Incidencia eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar: {str(e)}", "danger")

    return redirect(url_for("rrhh_web.incidencias_list"))

@rrhh_bp.post("/fichajes/<int:fichaje_id>/eliminar")
@admin_required
def fichaje_delete(fichaje_id):
    fichaje = Fichaje.query.get_or_404(fichaje_id)
    # Seguridad: Verificar que pertenece a la empresa del admin
    if fichaje.trabajador.idEmpresa != session.get("empresa_id"):
        flash("No tienes permiso para eliminar este fichaje.", "danger")
        return redirect(url_for("rrhh_web.fichajes_list"))

    try:
        db.session.delete(fichaje)
        db.session.commit()
        flash("Registro de fichaje eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar: {str(e)}", "danger")

    return redirect(url_for("rrhh_web.fichajes_list"))

# --- BOTON MANUAL DE NOTIFICACIONES ---
@rrhh_bp.post("/notificaciones/ejecutar-ausencias")
@admin_required
def ejecutar_notificaciones_ausencia():
    """Ejecuta la comprobación de ausencias manualmente desde la web."""
    print("--- EJECUTANDO NOTIFICACIONES MANUALMENTE ---")

    # 1. Configuración de días
    DIAS_SEMANA = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo"}
    hoy = date.today()
    nombre_dia = DIAS_SEMANA[hoy.weekday()]

    # 2. Buscar día en BD
    dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
    if not dia_db:
        flash(f"Error: No existe el día '{nombre_dia}' en la base de datos.", "danger")
        return redirect(url_for('rrhh_web.fichajes_list'))

    trabajadores = Trabajador.query.all()
    enviados = 0
    detectados = 0

    for t in trabajadores:
        # A. Tiene horario y trabaja hoy?
        if not t.idHorario: continue

        franja_hoy = Franja.query.filter_by(id_horario=t.idHorario, id_dia=dia_db.id).first()
        if not franja_hoy: continue # Libra hoy

        # B. Ha fichado entrada?
        fichaje = Fichaje.query.filter(
            Fichaje.id_trabajador == t.id_trabajador,
            Fichaje.tipo == 'ENTRADA',
            db.func.date(Fichaje.fecha_hora) == hoy
        ).first()

        if not fichaje:
            detectados += 1
            if t.email:
                # Enviar correo real
                exito = enviar_correo_ausencia(t.email, t.nombre)
                if exito: enviados += 1

    if detectados == 0:
        flash("Todos los empleados con turno han fichado correctamente hoy.", "success")
    else:
        flash(f"Proceso finalizado: Se detectaron {detectados} ausencias y se enviaron {enviados} correos.", "warning")

    return redirect(url_for('rrhh_web.fichajes_list'))
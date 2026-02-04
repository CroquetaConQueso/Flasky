from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from models import Trabajador, Rol, Horario, Franja, Fichaje, Empresa, Incidencia, Dia
from forms import TrabajadorForm, HorarioForm, FichajeManualForm, IncidenciaCrearForm, IncidenciaAdminForm
from utils.decorators import admin_required
from utils.email_sender import enviar_correo_resolucion
from extensions import db
from datetime import datetime

rrhh_bp = Blueprint('rrhh_web', __name__)

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

# --- FICHAJES E INCIDENCIAS ---

@rrhh_bp.get("/fichajes")
@admin_required
def fichajes_list():
    empresa_id = session.get("empresa_id")
    filtro_empleado = request.args.get('empleado_id', type=int)
    filtro_fecha = request.args.get('fecha')

    query = Fichaje.query.join(Trabajador).filter(Trabajador.idEmpresa == empresa_id)

    if filtro_empleado:
        query = query.filter(Trabajador.id_trabajador == filtro_empleado)
    if filtro_fecha:
        query = query.filter(db.func.date(Fichaje.fecha_hora) == filtro_fecha)

    fichajes_raw = query.order_by(Fichaje.fecha_hora.asc()).limit(1000).all()

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

    return render_template("fichajes_list.html",
                           jornadas=jornadas,
                           empleados=empleados,
                           filtro_empleado=filtro_empleado,
                           filtro_fecha=filtro_fecha)

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
    
    # Recogida de filtros
    filtro_empleado = request.args.get('empleado_id', type=int)
    filtro_inicio = request.args.get('fecha_inicio')
    filtro_fin = request.args.get('fecha_fin')

    # Query base filtrada por empresa
    query = Incidencia.query.join(Trabajador).filter(Trabajador.idEmpresa == empresa_id)

    # Aplicación de filtros
    if filtro_empleado:
        query = query.filter(Incidencia.id_trabajador == filtro_empleado)
    
    if filtro_inicio:
        query = query.filter(Incidencia.fecha_inicio >= filtro_inicio)
    
    if filtro_fin:
        query = query.filter(Incidencia.fecha_fin <= filtro_fin)

    incidencias = query.order_by(Incidencia.fecha_solicitud.desc()).all()
    
    # Lista de empleados para el selector del filtro
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
from app import create_app
from extensions import db
from models import Empresa, Rol, Horario, Trabajador, Dia, Franja, Fichaje, Incidencia
from datetime import datetime, timedelta, time
import calendar

app = create_app()

def get_or_create(model, **kwargs):
    """Busca un registro o lo crea si no existe."""
    instance = model.query.filter_by(**kwargs).first()
    if instance:
        return instance
    instance = model(**kwargs)
    db.session.add(instance)
    db.session.commit()
    return instance

with app.app_context():
    print("[INFO] Iniciando carga de datos de prueba...")

    # 1. Crear Empresa
    empresa = Empresa.query.filter_by(nombrecomercial="Empresa Demo").first()
    if not empresa:
        empresa = Empresa(
            nombrecomercial="Empresa Demo",
            cif="A12345678",
            latitud=40.4167,
            longitud=-3.7032,
            radio=500
        )
        db.session.add(empresa)
        db.session.commit()

    # 2. Crear Roles
    rol_admin = get_or_create(Rol, nombre_rol="Administrador")
    rol_super = get_or_create(Rol, nombre_rol="Superadministrador")
    rol_empleado = get_or_create(Rol, nombre_rol="Empleado")

    # 3. Crear Días (Minúsculas para compatibilidad con backend)
    nombres_dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    dias_objs = {}
    for nombre in nombres_dias:
        dias_objs[nombre] = get_or_create(Dia, nombre=nombre)

    # 4. Crear Horario y Franjas
    horario = Horario.query.filter_by(nombre_horario="Horario General").first()
    if not horario:
        horario = Horario(
            nombre_horario="Horario General",
            descripcion="Jornada intensiva de mañanas (08:00 - 15:00)",
            empresa_id=empresa.id_empresa
        )
        db.session.add(horario)
        db.session.commit()

        # Crear franjas L-V de 08:00 a 15:00
        laborables = ["lunes", "martes", "miercoles", "jueves", "viernes"]
        for dia_nombre in laborables:
            franja = Franja(
                id_horario=horario.id_horario,
                id_dia=dias_objs[dia_nombre].id,
                hora_entrada=time(8, 0),
                hora_salida=time(15, 0)
            )
            db.session.add(franja)
        db.session.commit()

    # 5. Crear Empleados Demo
    # Admin
    admin = Trabajador.query.filter_by(nif="00000000A").first()
    if not admin:
        admin = Trabajador(
            nif="00000000A",
            nombre="Super",
            apellidos="Admin",
            email="admin@example.com",
            telef="600000000",
            idEmpresa=empresa.id_empresa,
            idHorario=horario.id_horario,
            idRol=rol_super.id_rol
        )
        admin.set_password("admin123")
        db.session.add(admin)

    # Empleado Modelo (Cumple horario exacto)
    modelo = Trabajador.query.filter_by(nif="11111111B").first()
    if not modelo:
        modelo = Trabajador(
            nif="11111111B",
            nombre="Juan",
            apellidos="Modelo",
            email="juan@example.com",
            telef="600111111",
            idEmpresa=empresa.id_empresa,
            idHorario=horario.id_horario,
            idRol=rol_empleado.id_rol
        )
        modelo.set_password("1234")
        db.session.add(modelo)

    # Empleado Extra (Acumula horas extra)
    extra = Trabajador.query.filter_by(nif="22222222C").first()
    if not extra:
        extra = Trabajador(
            nif="22222222C",
            nombre="Ana",
            apellidos="Trabajadora",
            email="ana@example.com",
            telef="600222222",
            idEmpresa=empresa.id_empresa,
            idHorario=horario.id_horario,
            idRol=rol_empleado.id_rol
        )
        extra.set_password("1234")
        db.session.add(extra)

    # Empleado Relax (Debe horas)
    relax = Trabajador.query.filter_by(nif="33333333D").first()
    if not relax:
        relax = Trabajador(
            nif="33333333D",
            nombre="Pedro",
            apellidos="Relax",
            email="pedro@example.com",
            telef="600333333",
            idEmpresa=empresa.id_empresa,
            idHorario=horario.id_horario,
            idRol=rol_empleado.id_rol
        )
        relax.set_password("1234")
        db.session.add(relax)
    
    db.session.commit()

    # 6. Generar Historial de Fichajes (Mes Actual)
    # Solo generamos si no hay fichajes recientes para evitar duplicados masivos
    last_fichaje = Fichaje.query.order_by(Fichaje.fecha_hora.desc()).first()
    today = datetime.now()
    
    if not last_fichaje or last_fichaje.fecha_hora.month != today.month:
        print("[INFO] Generando fichajes para el mes en curso...")
        
        # Iterar desde el día 1 hasta ayer
        for day in range(1, today.day + 1):
            current_date = datetime(today.year, today.month, day)
            
            # Ignorar fines de semana
            if current_date.weekday() >= 5: 
                continue

            # Juan Modelo: 08:00 - 15:00 (Perfecto)
            db.session.add(Fichaje(id_trabajador=modelo.id_trabajador, tipo="ENTRADA", fecha_hora=current_date.replace(hour=8, minute=0), latitud=40.4, longitud=-3.7))
            db.session.add(Fichaje(id_trabajador=modelo.id_trabajador, tipo="SALIDA", fecha_hora=current_date.replace(hour=15, minute=0), latitud=40.4, longitud=-3.7))

            # Ana Trabajadora: 07:50 - 16:30 (Horas Extra)
            db.session.add(Fichaje(id_trabajador=extra.id_trabajador, tipo="ENTRADA", fecha_hora=current_date.replace(hour=7, minute=50), latitud=40.4, longitud=-3.7))
            db.session.add(Fichaje(id_trabajador=extra.id_trabajador, tipo="SALIDA", fecha_hora=current_date.replace(hour=16, minute=30), latitud=40.4, longitud=-3.7))

            # Pedro Relax: 08:15 - 14:00 (Debe Horas)
            db.session.add(Fichaje(id_trabajador=relax.id_trabajador, tipo="ENTRADA", fecha_hora=current_date.replace(hour=8, minute=15), latitud=40.4, longitud=-3.7))
            db.session.add(Fichaje(id_trabajador=relax.id_trabajador, tipo="SALIDA", fecha_hora=current_date.replace(hour=14, minute=0), latitud=40.4, longitud=-3.7))
        
        db.session.commit()

    # 7. Crear Incidencias de Prueba
    if not Incidencia.query.first():
        inc1 = Incidencia(
            id_trabajador=extra.id_trabajador,
            tipo="VACACIONES",
            fecha_inicio=today.date() + timedelta(days=5),
            fecha_fin=today.date() + timedelta(days=10),
            comentario_trabajador="Solicito vacaciones de verano.",
            estado="PENDIENTE"
        )
        inc2 = Incidencia(
            id_trabajador=relax.id_trabajador,
            tipo="BAJA",
            fecha_inicio=today.date() - timedelta(days=2),
            fecha_fin=today.date(),
            comentario_trabajador="Gripe fuerte.",
            estado="APROBADA",
            comentario_admin="Recupérate pronto."
        )
        db.session.add_all([inc1, inc2])
        db.session.commit()

    print("[SUCCESS] Datos de ejemplo cargados correctamente.")
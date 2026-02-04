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

def init_db():
    """Limpia y recrea la base de datos de cero."""
    print("🗑️  Borrando base de datos...")
    # Desactivar checks para borrar sin problemas de foreign keys
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
    db.session.commit()
    
    db.drop_all()
    
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
    db.session.commit()
    
    print("✨ Creando tablas nuevas...")
    db.create_all()

with app.app_context():
    print("[INFO] Iniciando script de semilla...")
    
    # PASO 1: REINICIAR TABLAS (CRÍTICO)
    # Esto asegura que las tablas existen antes de consultarlas
    init_db()

    # PASO 2: CREAR DATOS
    print("🏭 Creando empresa...")
    empresa = Empresa(
        nombrecomercial="Empresa Demo",
        cif="A12345678",
        latitud=40.4167,
        longitud=-3.7032,
        radio=500
    )
    db.session.add(empresa)
    db.session.commit()

    print("👮 Creando roles...")
    rol_admin = Rol(nombre_rol="Administrador")
    rol_super = Rol(nombre_rol="Superadministrador")
    rol_empleado = Rol(nombre_rol="Empleado")
    db.session.add_all([rol_admin, rol_super, rol_empleado])
    db.session.commit()

    print("📅 Creando días...")
    # Nombres en minúscula para coincidir con la lógica del backend
    nombres_dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    dias_objs = {}
    for nombre in nombres_dias:
        d = Dia(nombre=nombre)
        db.session.add(d)
        dias_objs[nombre] = d
    db.session.commit()

    print("⏰ Creando horario y franjas...")
    # Horario con los nuevos campos booleanos por defecto (L-V True)
    horario = Horario(
        nombre_horario="Horario General",
        descripcion="Jornada intensiva de mañanas (08:00 - 15:00)",
        empresa_id=empresa.id_empresa,
        lunes=True, martes=True, miercoles=True, jueves=True, viernes=True,
        sabado=False, domingo=False
    )
    db.session.add(horario)
    db.session.commit()

    # Crear franjas L-V de 08:00 a 15:00
    laborables = ["lunes", "martes", "miercoles", "jueves", "viernes"]
    for dia_nombre in laborables:
        # Recuperar el objeto Dia de la sesión actual
        dia_obj = Dia.query.filter_by(nombre=dia_nombre).first()
        franja = Franja(
            id_horario=horario.id_horario,
            id_dia=dia_obj.id,
            hora_entrada=time(8, 0),
            hora_salida=time(15, 0)
        )
        db.session.add(franja)
    db.session.commit()

    print("👥 Creando empleados...")
    # Admin
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
    
    # Empleado Modelo
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

    # Empleado Extra
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

    # Empleado Relax
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

    db.session.add_all([admin, modelo, extra, relax])
    db.session.commit()

    print("🕓 Generando fichajes mes actual...")
    today = datetime.now()
    
    # Generar fichajes desde el día 1 hasta ayer
    for day in range(1, today.day + 1):
        current_date = datetime(today.year, today.month, day)
        
        if current_date.weekday() >= 5: continue # Fin de semana

        # Juan: Perfecto
        db.session.add(Fichaje(id_trabajador=modelo.id_trabajador, tipo="ENTRADA", fecha_hora=current_date.replace(hour=8, minute=0), latitud=40.4, longitud=-3.7))
        db.session.add(Fichaje(id_trabajador=modelo.id_trabajador, tipo="SALIDA", fecha_hora=current_date.replace(hour=15, minute=0), latitud=40.4, longitud=-3.7))

        # Ana: Extras
        db.session.add(Fichaje(id_trabajador=extra.id_trabajador, tipo="ENTRADA", fecha_hora=current_date.replace(hour=7, minute=50), latitud=40.4, longitud=-3.7))
        db.session.add(Fichaje(id_trabajador=extra.id_trabajador, tipo="SALIDA", fecha_hora=current_date.replace(hour=16, minute=30), latitud=40.4, longitud=-3.7))

        # Pedro: Debe horas
        db.session.add(Fichaje(id_trabajador=relax.id_trabajador, tipo="ENTRADA", fecha_hora=current_date.replace(hour=8, minute=15), latitud=40.4, longitud=-3.7))
        db.session.add(Fichaje(id_trabajador=relax.id_trabajador, tipo="SALIDA", fecha_hora=current_date.replace(hour=14, minute=0), latitud=40.4, longitud=-3.7))
    
    db.session.commit()

    print("[SUCCESS] Datos de ejemplo cargados correctamente.")
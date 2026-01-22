from app import app
from extensions import db
from models import Empresa, Rol, Horario, Trabajador, Dia


with app.app_context():
    # 1. Crear Empresa
    empresa = Empresa.query.filter_by(nombrecomercial="Empresa Demo").first()
    if not empresa:
        empresa = Empresa(
            nombrecomercial="Empresa Demo",
            cif="A12345678",
            latitud=40.4167,
            longitud=-3.7032,
            radio=100
        )
        db.session.add(empresa)

    # 2. Crear Roles
    rol_admin = Rol.query.filter_by(nombre_rol="Administrador").first()
    if not rol_admin:
        rol_admin = Rol(nombre_rol="Administrador")
        db.session.add(rol_admin)

    rol_super = Rol.query.filter_by(nombre_rol="Superadministrador").first()
    if not rol_super:
        rol_super = Rol(nombre_rol="Superadministrador")
        db.session.add(rol_super)

    rol_empleado = Rol.query.filter_by(nombre_rol="Empleado").first()
    if not rol_empleado:
        rol_empleado = Rol(nombre_rol="Empleado")
        db.session.add(rol_empleado)

    # 3. Crear Horario
    horario = Horario.query.filter_by(nombre_horario="Horario general").first()
    if not horario:
        horario = Horario(
            nombre_horario="Horario general",
            descripcion="Horario genérico para todos los empleados"
        )
        db.session.add(horario)

    # 4. Crear Días
    nombres_dias = [
        "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
    ]
    for nombre in nombres_dias:
        dia = Dia.query.filter_by(nombre=nombre).first()
        if not dia:
            dia = Dia(nombre=nombre)
            db.session.add(dia)

    db.session.commit()


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

    db.session.commit()
    print("Datos de ejemplo creados/actualizados correctamente (con contraseñas seguras).")

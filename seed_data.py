from app import app
from extensions import db
from models import Empresa, Rol, Horario, Trabajador, Dia


with app.app_context():
    empresa = Empresa.query.filter_by(nombrecomercial="Empresa Demo").first()
    if not empresa:
        empresa = Empresa(
            nombrecomercial="Empresa Demo",
            cif="A12345678"
        )
        db.session.add(empresa)

    rol_admin = Rol.query.filter_by(nombre_rol="Administrador").first()
    if not rol_admin:
        rol_admin = Rol(nombre_rol="Administrador")
        db.session.add(rol_admin)

    rol_empleado = Rol.query.filter_by(nombre_rol="Empleado").first()
    if not rol_empleado:
        rol_empleado = Rol(nombre_rol="Empleado")
        db.session.add(rol_empleado)

    horario = Horario.query.filter_by(nombre_horario="Horario general").first()
    if not horario:
        horario = Horario(
            nombre_horario="Horario general",
            descripcion="Horario genérico para todos los empleados"
        )
        db.session.add(horario)

    nombres_dias = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]

    for nombre in nombres_dias:
        dia = Dia.query.filter_by(nombre=nombre).first()
        if not dia:
            dia = Dia(nombre=nombre)
            db.session.add(dia)

    admin = Trabajador.query.filter_by(nif="00000000A").first()
    if not admin:
        admin = Trabajador(
            nif="00000000A",
            nombre="Admin",
            apellidos="Principal",
            passw="admin123",
            email="admin@example.com",
            telef="600000000",
            empresa=empresa,
            horario=horario,
            rol=rol_admin
        )
        db.session.add(admin)

    db.session.commit()
    print("Datos de ejemplo creados/actualizados correctamente.")

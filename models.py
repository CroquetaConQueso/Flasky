from extensions import db


class Empresa(db.Model):
    __tablename__ = "empresa"

    id_empresa = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombrecomercial = db.Column(db.String(120), nullable=False)
    cif = db.Column(db.String(20), nullable=False)

    trabajadores = db.relationship("Trabajador", back_populates="empresa")


class Rol(db.Model):
    __tablename__ = "rol"

    id_rol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_rol = db.Column(db.String(80), nullable=False, unique=True)

    trabajadores = db.relationship("Trabajador", back_populates="rol")


class Horario(db.Model):
    __tablename__ = "horario"

    id_horario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_horario = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.String(255))

    trabajadores = db.relationship("Trabajador", back_populates="horario")
    franjas = db.relationship(
        "Franja",
        back_populates="horario",
        cascade="all, delete-orphan"
    )


class Dia(db.Model):
    __tablename__ = "dia"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(30), nullable=False, unique=True)

    franjas = db.relationship("Franja", back_populates="dia")


class Franja(db.Model):
    __tablename__ = "franjas"

    id_dia = db.Column(db.Integer, db.ForeignKey("dia.id"), primary_key=True)
    id_horario = db.Column(db.Integer, db.ForeignKey("horario.id_horario"), primary_key=True)
    hora_entrada = db.Column(db.Time, nullable=False)
    hora_salida = db.Column(db.Time, nullable=False)

    dia = db.relationship("Dia", back_populates="franjas")
    horario = db.relationship("Horario", back_populates="franjas")


class Trabajador(db.Model):
    __tablename__ = "trabajador"

    id_trabajador = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nif = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    apellidos = db.Column(db.String(120), nullable=False)
    passw = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telef = db.Column(db.String(30))

    idEmpresa = db.Column(db.Integer, db.ForeignKey("empresa.id_empresa"), nullable=False)
    idHorario = db.Column(db.Integer, db.ForeignKey("horario.id_horario"), nullable=False)
    idRol = db.Column(db.Integer, db.ForeignKey("rol.id_rol"), nullable=False)

    empresa = db.relationship("Empresa", back_populates="trabajadores")
    horario = db.relationship("Horario", back_populates="trabajadores")
    rol = db.relationship("Rol", back_populates="trabajadores")

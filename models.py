from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class Empresa(db.Model):
    __tablename__ = "empresa"

    id_empresa = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombrecomercial = db.Column(db.String(120), nullable=False)
    cif = db.Column(db.String(20), nullable=False)
    latitud = db.Column(db.Float, nullable=True)
    longitud = db.Column(db.Float, nullable=True)
    radio = db.Column(db.Integer, nullable=True, default=100)

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
    
    # Relación con fichajes
    fichajes = db.relationship("Fichaje", back_populates="trabajador", cascade="all, delete-orphan")

    def set_password(self, password):
        self.passw = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.passw, password)


# NUEVA CLASE PARA FICHAJES
class Fichaje(db.Model):
    __tablename__ = "fichaje"

    id_fichaje = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.now)
    tipo = db.Column(db.String(20), nullable=False) # 'ENTRADA' o 'SALIDA'
    latitud = db.Column(db.Float, nullable=False)
    longitud = db.Column(db.Float, nullable=False)
    
    id_trabajador = db.Column(db.Integer, db.ForeignKey("trabajador.id_trabajador"), nullable=False)
    trabajador = db.relationship("Trabajador", back_populates="fichajes")
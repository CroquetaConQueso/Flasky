from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class Empresa(db.Model):
    """Empresa: geolocalización (lat/lon/radio) y NFC de oficina para restringir fichajes."""
    __tablename__ = "empresa"

    id_empresa = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombrecomercial = db.Column(db.String(120), nullable=False)
    cif = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)

    latitud = db.Column(db.Float, nullable=True)
    longitud = db.Column(db.Float, nullable=True)
    radio = db.Column(db.Integer, nullable=True, default=100)

    codigo_nfc_oficina = db.Column(db.String(50), nullable=True)

    trabajadores = db.relationship("Trabajador", back_populates="empresa")
    horarios = db.relationship("Horario", backref="empresa", lazy=True)


class Rol(db.Model):
    """Rol: controla permisos (admin/superadmin) y acceso a endpoints/paneles."""
    __tablename__ = "rol"

    id_rol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_rol = db.Column(db.String(80), nullable=False, unique=True)

    trabajadores = db.relationship("Trabajador", back_populates="rol")


class Horario(db.Model):
    """Horario: plantilla semanal; sus franjas por día definen la jornada teórica."""
    __tablename__ = "horario"

    id_horario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_horario = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.String(255))

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id_empresa"), nullable=True)

    lunes = db.Column(db.Boolean, default=True)
    martes = db.Column(db.Boolean, default=True)
    miercoles = db.Column(db.Boolean, default=True)
    jueves = db.Column(db.Boolean, default=True)
    viernes = db.Column(db.Boolean, default=True)
    sabado = db.Column(db.Boolean, default=False)
    domingo = db.Column(db.Boolean, default=False)

    trabajadores = db.relationship("Trabajador", back_populates="horario")
    franjas = db.relationship("Franja", back_populates="horario", cascade="all, delete-orphan")


class Dia(db.Model):
    """Dia: catálogo (lunes..domingo) para asociar franjas a un día concreto."""
    __tablename__ = "dia"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(30), nullable=False, unique=True)

    franjas = db.relationship("Franja", back_populates="dia")


class Franja(db.Model):
    """Franja: horas de entrada/salida por (horario, día). PK compuesta."""
    __tablename__ = "franjas"

    id_horario = db.Column(db.Integer, db.ForeignKey("horario.id_horario"), primary_key=True)
    id_dia = db.Column(db.Integer, db.ForeignKey("dia.id"), primary_key=True)

    hora_entrada = db.Column(db.Time, nullable=False)
    hora_salida = db.Column(db.Time, nullable=False)

    dia = db.relationship("Dia", back_populates="franjas")
    horario = db.relationship("Horario", back_populates="franjas")


class Trabajador(db.Model):
    """Trabajador: credenciales, rol, empresa, horario, NFC personal y token FCM."""
    __tablename__ = "trabajador"

    id_trabajador = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nif = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    apellidos = db.Column(db.String(120), nullable=False)
    passw = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telef = db.Column(db.String(30))

    codigo_nfc = db.Column(db.String(50), unique=True, nullable=True)
    fcm_token = db.Column(db.String(255), nullable=True)

    idEmpresa = db.Column(db.Integer, db.ForeignKey("empresa.id_empresa"), nullable=False)
    idHorario = db.Column(db.Integer, db.ForeignKey("horario.id_horario"), nullable=True)
    idRol = db.Column(db.Integer, db.ForeignKey("rol.id_rol"), nullable=False)

    empresa = db.relationship("Empresa", back_populates="trabajadores")
    horario = db.relationship("Horario", back_populates="trabajadores")
    rol = db.relationship("Rol", back_populates="trabajadores")

    fichajes = db.relationship("Fichaje", back_populates="trabajador", cascade="all, delete-orphan")
    incidencias = db.relationship("Incidencia", back_populates="trabajador", cascade="all, delete-orphan")

    def set_password(self, password):
        self.passw = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.passw, password)


class Fichaje(db.Model):
    """Fichaje: registro ENTRADA/SALIDA con fecha y posición para control de presencia."""
    __tablename__ = "fichaje"

    id_fichaje = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.now)
    tipo = db.Column(db.String(20), nullable=False)
    latitud = db.Column(db.Float, nullable=False)
    longitud = db.Column(db.Float, nullable=False)

    id_trabajador = db.Column(db.Integer, db.ForeignKey("trabajador.id_trabajador"), nullable=False)
    trabajador = db.relationship("Trabajador", back_populates="fichajes")


class Incidencia(db.Model):
    """Incidencia: solicitudes (vacaciones/baja/olvido...) con estado y comentarios."""
    __tablename__ = "incidencia"

    id_incidencia = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo = db.Column(db.String(50), nullable=False)
    fecha_solicitud = db.Column(db.DateTime, default=datetime.now)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    comentario_trabajador = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(20), default="PENDIENTE")
    comentario_admin = db.Column(db.Text, nullable=True)

    id_trabajador = db.Column(db.Integer, db.ForeignKey("trabajador.id_trabajador"), nullable=False)
    trabajador = db.relationship("Trabajador", back_populates="incidencias")

from marshmallow import Schema, fields, validate

# --- ESQUEMAS BASICOS ---
class PlainEmpresaSchema(Schema):
    id_empresa = fields.Int(dump_only=True)
    nombrecomercial = fields.String(required=True)
    cif = fields.String(required=True)
    latitud = fields.Float()
    longitud = fields.Float()
    radio = fields.Float()

class PlainRolSchema(Schema):
    id_rol = fields.Int(dump_only=True)
    nombre_rol = fields.String(required=True)

class PlainTrabajadorSchema(Schema):
    id_trabajador = fields.Int(dump_only=True)
    nif = fields.String(required=True)
    nombre = fields.String(required=True)
    apellidos = fields.String(required=True)
    email = fields.String()
    telef = fields.String()

class PlainHorarioSchema(Schema):
    id_horario = fields.Int(dump_only=True)
    nombre_horario = fields.String(required=True)
    descripcion = fields.String()

class PlainFichajeSchema(Schema):
    id_fichaje = fields.Int(dump_only=True)
    tipo = fields.String(required=True, validate=validate.OneOf(["ENTRADA", "SALIDA"]))
    fecha_hora = fields.DateTime(dump_only=True)
    latitud = fields.Float()
    longitud = fields.Float()

# --- LOGIN Y RECUPERACIÓN ---
class UserLoginSchema(Schema):
    # Aceptamos hasta 100 chars para Emails
    nif = fields.String(required=True, validate=validate.Length(min=4, max=100))
    password = fields.String(required=True, load_only=True)

class PasswordResetSchema(Schema):
    identificador = fields.String(required=True, validate=validate.Length(min=4, max=100))

# --- ESQUEMAS COMPLETOS ---
class TrabajadorSchema(PlainTrabajadorSchema):
    idEmpresa = fields.Int(required=True, load_only=True)
    idRol = fields.Int(required=True, load_only=True)
    idHorario = fields.Int(load_only=True)
    empresa = fields.Nested(PlainEmpresaSchema(), dump_only=True)
    rol = fields.Nested(PlainRolSchema(), dump_only=True)
    horario = fields.Nested(PlainHorarioSchema(), dump_only=True)

class EmpresaSchema(PlainEmpresaSchema):
    trabajadores = fields.List(fields.Nested(PlainTrabajadorSchema()), dump_only=True)

class FichajeSchema(PlainFichajeSchema):
    id_trabajador = fields.Int(required=True, load_only=True)
    trabajador = fields.Nested(PlainTrabajadorSchema(), dump_only=True)

class IncidenciaSchema(Schema):
    id_incidencia = fields.Int(dump_only=True)
    id_trabajador = fields.Int(required=True, load_only=True)
    tipo = fields.String(required=True)
    fecha_solicitud = fields.DateTime(dump_only=True)
    fecha_inicio = fields.Date(required=True)
    fecha_fin = fields.Date(required=True)
    comentario_trabajador = fields.String()
    estado = fields.String(dump_only=True)
    comentario_admin = fields.String(dump_only=True)
    trabajador = fields.Nested(PlainTrabajadorSchema(), dump_only=True)
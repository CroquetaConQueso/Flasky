from marshmallow import Schema, fields, validate

# --- ESQUEMAS BÁSICOS ---

class PlainEmpresaSchema(Schema):
    id_empresa = fields.Int(dump_only=True)
    nombrecomercial = fields.String(required=True, validate=validate.Length(max=100))
    cif = fields.String(required=True, validate=validate.Length(max=20))
    latitud = fields.Float()
    longitud = fields.Float()
    radio = fields.Float()

class PlainRolSchema(Schema):
    id_rol = fields.Int(dump_only=True)
    nombre_rol = fields.String(required=True, validate=validate.Length(max=50))

class PlainTrabajadorSchema(Schema):
    id_trabajador = fields.Int(dump_only=True)
    nif = fields.String(required=True, validate=validate.Length(max=20))
    nombre = fields.String(required=True, validate=validate.Length(max=50))
    apellidos = fields.String(required=True, validate=validate.Length(max=100))
    email = fields.String(validate=validate.Email())
    telef = fields.String(validate=validate.Length(max=20))

class PlainHorarioSchema(Schema):
    id_horario = fields.Int(dump_only=True)
    nombre_horario = fields.String(required=True, validate=validate.Length(max=50))
    descripcion = fields.String()

class PlainFichajeSchema(Schema):
    id_fichaje = fields.Int(dump_only=True)
    tipo = fields.String(required=True, validate=validate.OneOf(["ENTRADA", "SALIDA"]))
    fecha_hora = fields.DateTime(dump_only=True)
    latitud = fields.Float()
    longitud = fields.Float()

# --- ESQUEMAS DE LOGIN Y RECUPERACIÓN (CORREGIDO PARA SER FLEXIBLE) ---

class UserLoginSchema(Schema):
    nif = fields.String(required=True, validate=validate.Length(min=4, max=100))
    password = fields.String(required=True, load_only=True)

class PasswordResetSchema(Schema):
    # CORRECCIÓN IMPORTANTE: No exigimos 'required=True' en un solo campo.
    # Permitimos que lleguen como opcionales y lo gestionamos en auth.py
    identificador = fields.String(load_default=None)
    email = fields.String(load_default=None)
    nif = fields.String(load_default=None)

# --- ESQUEMAS COMPLETOS (Relaciones) ---

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

# --- ESQUEMAS NECESARIOS PARA FICHAJES (Añadidos para evitar errores de importación) ---

class FichajeInputSchema(Schema):
    latitud = fields.Float(required=True)
    longitud = fields.Float(required=True)

class FichajeOutputSchema(Schema):
    id_fichaje = fields.Int(dump_only=True)
    fecha_hora = fields.DateTime(dump_only=True)
    tipo = fields.String(dump_only=True)
    latitud = fields.Float(dump_only=True)
    longitud = fields.Float(dump_only=True)

class ChangePasswordSchema(Schema):
    current_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=validate.Length(min=6))

class IncidenciaCreateSchema(Schema):
    tipo = fields.String(required=True, validate=validate.OneOf(["VACACIONES", "BAJA", "ASUNTOS_PROPIOS", "OLVIDO", "HORAS_EXTRA"]))
    fecha_inicio = fields.Date(required=True)
    fecha_fin = fields.Date(required=True)
    comentario_trabajador = fields.String()

# --- RESUMENES DE HORAS

class ResumenMensualQuerySchema(Schema):
    mes = fields.Int(load_default=None)
    anio = fields.Int(load_default=None)

class ResumenMensualOutputSchema(Schema):
    mes = fields.String()
    teoricas = fields.Float()
    trabajadas = fields.Float()
    saldo = fields.Float()
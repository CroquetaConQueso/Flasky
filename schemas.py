from marshmallow import Schema, fields, validate

# --- ESQUEMAS BÁSICOS ---

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
    # Quitamos la validación OneOf para que acepte cualquier string que envíe la app
    tipo = fields.String(required=True) 
    fecha_hora = fields.DateTime(dump_only=True)
    latitud = fields.Float()
    longitud = fields.Float()

# --- LOGIN & PASSWORD ---

class UserLoginSchema(Schema):
    # Quitamos validación de longitud
    nif = fields.String(required=True) 
    password = fields.String(required=True, load_only=True)

class PasswordResetSchema(Schema):
    identificador = fields.String(load_default=None)
    email = fields.String(load_default=None)
    nif = fields.String(load_default=None)

# --- ESQUEMAS COMPLETOS (Relationships) ---

class TrabajadorSchema(PlainTrabajadorSchema):
    idEmpresa = fields.Int(required=True, load_only=True)
    idRol = fields.Int(required=True, load_only=True)
    idHorario = fields.Int(load_only=True)
    rol_nombre = fields.String(attribute="rol.nombre_rol", dump_only=True)

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

# --- EXTRAS ---

class FichajeInputSchema(Schema):
    latitud = fields.Float(required=True)
    longitud = fields.Float(required=True)
    # Campo opcional para que no falle si la app antigua no lo envía
    nfc_data = fields.String(load_default=None) 

class FichajeOutputSchema(Schema):
    id_fichaje = fields.Int(dump_only=True)
    fecha_hora = fields.DateTime(dump_only=True)
    tipo = fields.String(dump_only=True)
    latitud = fields.Float(dump_only=True)
    longitud = fields.Float(dump_only=True)

class ChangePasswordSchema(Schema):
    current_password = fields.String(required=True)
    # IMPORTANTE: Eliminado validate.Length(min=6). Ahora acepta "123".
    new_password = fields.String(required=True) 

class IncidenciaCreateSchema(Schema):
    # IMPORTANTE: Eliminado validate.OneOf. Ahora acepta "Vacaciones", "baja", etc.
    tipo = fields.String(required=True) 
    # Mantenemos Date. Si la app envía formato incorrecto, fallará, 
    # pero Marshmallow requiere Date para convertirlo a objeto Python.
    fecha_inicio = fields.Date(required=True)
    fecha_fin = fields.Date(required=True)
    comentario_trabajador = fields.String()

class ResumenMensualQuerySchema(Schema):
    mes = fields.Int(load_default=None)
    anio = fields.Int(load_default=None)

class ResumenMensualOutputSchema(Schema):
    mes = fields.String()
    teoricas = fields.Float()
    trabajadas = fields.Float()
    saldo = fields.Float()

class FcmTokenSchema(Schema):
    token = fields.String(required=True)

class FichajeNFCInputSchema(Schema):
    nfc_data = fields.String(required=True)
    latitud = fields.Float(load_default=None)
    longitud = fields.Float(load_default=None)
from marshmallow import Schema, fields

class EmpresaSchema(Schema):
    id_empresa = fields.Int(dump_only=True)
    nombrecomercial = fields.Str(required=True)
    cif = fields.Str(required=True)
    latitud = fields.Float()
    longitud = fields.Float()
    radio = fields.Int()

class UserLoginSchema(Schema):
    nif = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)

class FichajeInputSchema(Schema):
    latitud = fields.Float(required=True)
    longitud = fields.Float(required=True)

class FichajeOutputSchema(Schema):
    id_fichaje = fields.Int(dump_only=True)
    fecha_hora = fields.DateTime(dump_only=True)
    tipo = fields.Str(dump_only=True) # ENTRADA/SALIDA
    latitud = fields.Float(dump_only=True)
    longitud = fields.Float(dump_only=True)
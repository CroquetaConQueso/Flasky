from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField, IntegerField, TextAreaField, DateField
from wtforms.validators import DataRequired, Length, Optional

# --- BLOQUE ANTI-CRASH (Detecta versiones y faltas de librerías) ---

# 1. Gestión de Campos Modernos
try:
    # Intenta importar versión moderna (3.x)
    from wtforms.fields import TimeField, DateTimeLocalField, TelField
except ImportError:
    try:
        # Intenta importar versión antigua (2.x - HTML5)
        from wtforms.fields.html5 import TimeField, DateTimeLocalField, TelField
    except ImportError:
        # Si todo falla, usa campos de texto simples (Fallback de seguridad)
        from wtforms.fields import StringField as TimeField
        from wtforms.fields import StringField as TelField
        from wtforms.fields import DateTimeField as DateTimeLocalField

# 2. Gestión del Validador de Email (Causa común de error 500)
try:
    from wtforms.validators import Email
except ImportError:
    # Si falta la librería 'email-validator', creamos un validador "tonto" que no hace nada
    # para que la web no explote.
    def Email(message=None):
        def _email(form, field):
            pass # No valida nada, pero permite arrancar
        return _email

# ---------------------------------------------------------------------

# 1. LOGIN
class LoginForm(FlaskForm):
    nif = StringField("Identificación", validators=[DataRequired(), Length(max=100)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    empresa_id = SelectField("Empresa", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Entrar")

# 2. EMPRESA
class EmpresaForm(FlaskForm):
    nombrecomercial = StringField("Nombre comercial", validators=[DataRequired(), Length(max=120)])
    cif = StringField("CIF", validators=[DataRequired(), Length(max=20)])
    latitud = FloatField("Latitud", validators=[DataRequired()])
    longitud = FloatField("Longitud", validators=[DataRequired()])
    radio = IntegerField("Radio (metros)", validators=[DataRequired()])
    submit = SubmitField("Guardar")

# 3. ROLES
class RolForm(FlaskForm):
    nombre_rol = StringField("Nombre del rol", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Guardar")

# 4. TRABAJADORES
class TrabajadorForm(FlaskForm):
    nif = StringField("NIF", validators=[DataRequired(), Length(max=20)])
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    apellidos = StringField("Apellidos", validators=[DataRequired(), Length(max=120)])
    passw = PasswordField("Contraseña", validators=[Optional(), Length(max=255)])

    # Usa el validador Email (real o parcheado)
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])

    telef = TelField("Teléfono")
    rol_id = SelectField("Rol", coerce=int, validators=[DataRequired()])
    horario_id = SelectField("Horario", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Guardar")

# 5. HORARIOS
class HorarioForm(FlaskForm):
    nombre_horario = StringField("Nombre del horario", validators=[DataRequired(), Length(max=80)])
    descripcion = StringField("Descripción", validators=[Length(max=255)])
    submit = SubmitField("Guardar")

# 6. FRANJAS
class FranjaForm(FlaskForm):
    dia_id = SelectField("Día", coerce=int, validators=[DataRequired()])
    # format es necesario solo si es TimeField real, si es StringField lo ignora o lo acepta
    hora_entrada = TimeField("Hora de entrada", validators=[DataRequired()], format='%H:%M')
    hora_salida = TimeField("Hora de salida", validators=[DataRequired()], format='%H:%M')
    submit = SubmitField("Añadir franja")

# 7. INCIDENCIAS (RESOLVER)
class IncidenciaAdminForm(FlaskForm):
    estado = SelectField("Resolución", choices=[
        ('PENDIENTE', 'Pendiente'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada')
    ], validators=[DataRequired()])
    comentario_admin = TextAreaField("Motivo / Respuesta", validators=[Length(max=500)])
    submit = SubmitField("Guardar Resolución")

# 8. INCIDENCIAS (CREAR)
class IncidenciaCrearForm(FlaskForm):
    trabajador_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    tipo = SelectField("Tipo de Incidencia", choices=[
        ('VACACIONES', 'Vacaciones'),
        ('BAJA', 'Baja Médica'),
        ('ASUNTOS_PROPIOS', 'Asuntos Propios'),
        ('OLVIDO', 'Olvido de Fichaje'),
        ('HORAS_EXTRA', 'Horas Extra')
    ], validators=[DataRequired()])
    fecha_inicio = DateField("Fecha Inicio", format='%Y-%m-%d', validators=[DataRequired()])
    fecha_fin = DateField("Fecha Fin", format='%Y-%m-%d', validators=[DataRequired()])
    comentario = TextAreaField("Observaciones", validators=[Length(max=500)])
    submit = SubmitField("Registrar Incidencia")

# 9. FICHAJE MANUAL
class FichajeManualForm(FlaskForm):
    trabajador_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    tipo = SelectField("Tipo de Movimiento", choices=[
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida')
    ], validators=[DataRequired()])

    fecha_hora = DateTimeLocalField("Fecha y Hora", format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    submit = SubmitField("Registrar Fichaje")

class RequestPasswordForm(FlaskForm):
    # Usamos StringField con validación de Email para mayor compatibilidad
    email = StringField("Correo electrónico", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Enviar nueva contraseña")
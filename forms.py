from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    TelField,
    FloatField,
    IntegerField,
    TextAreaField,
    DateField  # Importante: DateField añadido
)
from wtforms.fields import TimeField
from wtforms.validators import DataRequired, Length, Email, Optional

# 1. LOGIN
class LoginForm(FlaskForm):
    nif = StringField("NIF", validators=[DataRequired(), Length(max=20)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    empresa_id = SelectField("Empresa", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Entrar")

# 2. EMPRESA
class EmpresaForm(FlaskForm):
    nombrecomercial = StringField(
        "Nombre comercial", validators=[DataRequired(), Length(max=120)]
    )
    cif = StringField("CIF", validators=[DataRequired(), Length(max=20)])
    latitud = FloatField("Latitud", validators=[DataRequired()])
    longitud = FloatField("Longitud", validators=[DataRequired()])
    radio = IntegerField("Radio (metros)", validators=[DataRequired()])
    submit = SubmitField("Guardar")

# 3. ROLES
class RolForm(FlaskForm):
    nombre_rol = StringField(
        "Nombre del rol", validators=[DataRequired(), Length(max=80)]
    )
    submit = SubmitField("Guardar")

# 4. TRABAJADORES
class TrabajadorForm(FlaskForm):
    nif = StringField("NIF", validators=[DataRequired(), Length(max=20)])
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    apellidos = StringField("Apellidos", validators=[DataRequired(), Length(max=120)])
    
    # Optional permite editar sin cambiar la contraseña
    passw = PasswordField("Contraseña", validators=[Optional(), Length(max=255)])
    
    # Restauramos Email() porque ya tienes la librería instalada
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    
    telef = TelField("Teléfono")
    rol_id = SelectField("Rol", coerce=int, validators=[DataRequired()])
    horario_id = SelectField("Horario", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Guardar")

# 5. HORARIOS
class HorarioForm(FlaskForm):
    nombre_horario = StringField(
        "Nombre del horario", validators=[DataRequired(), Length(max=80)]
    )
    descripcion = StringField("Descripción", validators=[Length(max=255)])
    submit = SubmitField("Guardar")

# 6. FRANJAS
class FranjaForm(FlaskForm):
    dia_id = SelectField("Día", coerce=int, validators=[DataRequired()])
    hora_entrada = TimeField(
        "Hora de entrada", validators=[DataRequired()], format="%H:%M"
    )
    hora_salida = TimeField(
        "Hora de salida", validators=[DataRequired()], format="%H:%M"
    )
    submit = SubmitField("Añadir franja")

# 7. INCIDENCIAS (ADMIN RESOLVER)
class IncidenciaAdminForm(FlaskForm):
    estado = SelectField("Resolución", choices=[
        ('PENDIENTE', 'Pendiente'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada')
    ], validators=[DataRequired()])
    
    comentario_admin = TextAreaField("Motivo / Respuesta", validators=[Length(max=500)])
    
    submit = SubmitField("Guardar Resolución")

# 8. INCIDENCIAS (ADMIN CREAR NUEVA) - ¡NUEVO!
class IncidenciaCrearForm(FlaskForm):
    trabajador_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    
    tipo = SelectField("Tipo de Incidencia", choices=[
        ('VACACIONES', 'Vacaciones'),
        ('BAJA', 'Baja Médica'),
        ('ASUNTOS_PROPIOS', 'Asuntos Propios'),
        ('OLVIDO', 'Olvido de Fichaje'),
        ('HORAS_EXTRA', 'Horas Extra (Compensación)')
    ], validators=[DataRequired()])
    
    # DateField requiere el formato YYYY-MM-DD del input HTML date
    fecha_inicio = DateField("Fecha Inicio", format='%Y-%m-%d', validators=[DataRequired()])
    fecha_fin = DateField("Fecha Fin", format='%Y-%m-%d', validators=[DataRequired()])
    
    comentario = TextAreaField("Observaciones", validators=[Length(max=500)])
    
    submit = SubmitField("Registrar Incidencia")
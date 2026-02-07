from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    FloatField,
    IntegerField,
    TextAreaField,
    DateField,
)
from wtforms.validators import DataRequired, Length, Optional, EqualTo

try:
    from wtforms.fields import TimeField, DateTimeLocalField, TelField
except ImportError:
    try:
        from wtforms.fields.html5 import TimeField, DateTimeLocalField, TelField
    except ImportError:
        from wtforms.fields import StringField as TimeField
        from wtforms.fields import StringField as TelField
        from wtforms.fields import DateTimeField as DateTimeLocalField

try:
    from wtforms.validators import Email
except ImportError:
    def Email(message=None):
        def _email(form, field):
            return None
        return _email


# Forms web (login, CRUD, incidencias, fichajes)
class LoginForm(FlaskForm):
    nif = StringField("Identificación", validators=[DataRequired(), Length(max=100)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    empresa_id = SelectField("Empresa", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Entrar")


class EmpresaForm(FlaskForm):
    nombrecomercial = StringField("Nombre comercial", validators=[DataRequired(), Length(max=120)])
    cif = StringField("CIF", validators=[DataRequired(), Length(max=20)])
    latitud = FloatField("Latitud", validators=[DataRequired()])
    longitud = FloatField("Longitud", validators=[DataRequired()])
    radio = IntegerField("Radio (metros)", validators=[DataRequired()])
    submit = SubmitField("Guardar")


class RolForm(FlaskForm):
    nombre_rol = StringField("Nombre del rol", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Guardar")


class TrabajadorForm(FlaskForm):
    nif = StringField("NIF", validators=[DataRequired(), Length(max=20)])
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    apellidos = StringField("Apellidos", validators=[DataRequired(), Length(max=120)])
    passw = PasswordField("Contraseña", validators=[Optional(), Length(max=255)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    telef = TelField("Teléfono")
    rol_id = SelectField("Rol", coerce=int, validators=[DataRequired()])
    horario_id = SelectField("Horario", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Guardar")


class HorarioForm(FlaskForm):
    nombre_horario = StringField("Nombre del horario", validators=[DataRequired(), Length(max=80)])
    descripcion = StringField("Descripción", validators=[Length(max=255)])
    submit = SubmitField("Guardar")


class FranjaForm(FlaskForm):
    dia_id = SelectField("Día", coerce=int, validators=[DataRequired()])
    hora_entrada = TimeField("Hora de entrada", validators=[DataRequired()], format="%H:%M")
    hora_salida = TimeField("Hora de salida", validators=[DataRequired()], format="%H:%M")
    submit = SubmitField("Añadir franja")


class IncidenciaAdminForm(FlaskForm):
    estado = SelectField(
        "Resolución",
        choices=[
            ("PENDIENTE", "Pendiente"),
            ("APROBADA", "Aprobada"),
            ("RECHAZADA", "Rechazada"),
        ],
        validators=[DataRequired()],
    )
    comentario_admin = TextAreaField("Motivo / Respuesta", validators=[Length(max=500)])
    submit = SubmitField("Guardar Resolución")


class IncidenciaCrearForm(FlaskForm):
    trabajador_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    tipo = SelectField(
        "Tipo de Incidencia",
        choices=[
            ("VACACIONES", "Vacaciones"),
            ("BAJA", "Baja Médica"),
            ("ASUNTOS_PROPIOS", "Asuntos Propios"),
            ("OLVIDO", "Olvido de Fichaje"),
            ("HORAS_EXTRA", "Horas Extra"),
        ],
        validators=[DataRequired()],
    )
    fecha_inicio = DateField("Fecha Inicio", format="%Y-%m-%d", validators=[DataRequired()])
    fecha_fin = DateField("Fecha Fin", format="%Y-%m-%d", validators=[DataRequired()])
    comentario = TextAreaField("Observaciones", validators=[Length(max=500)])
    submit = SubmitField("Registrar Incidencia")


class FichajeManualForm(FlaskForm):
    trabajador_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    tipo = SelectField(
        "Tipo de Movimiento",
        choices=[("ENTRADA", "Entrada"), ("SALIDA", "Salida")],
        validators=[DataRequired()],
    )
    fecha_hora = DateTimeLocalField("Fecha y Hora", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    submit = SubmitField("Registrar Fichaje")


class RequestPasswordForm(FlaskForm):
    email = StringField("Correo electrónico", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Enviar nueva contraseña")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña Actual", validators=[DataRequired()])
    new_password = PasswordField("Nueva Contraseña", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Repetir Nueva",
        validators=[DataRequired(), EqualTo("new_password", message="Las contraseñas no coinciden")],
    )
    submit = SubmitField("Guardar Nueva Contraseña")

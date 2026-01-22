from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    TelField,
    FloatField,
    IntegerField
)
from wtforms.fields import TimeField
from wtforms.validators import DataRequired, Length, Email


class LoginForm(FlaskForm):
    nif = StringField("NIF", validators=[DataRequired(), Length(max=20)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    empresa_id = SelectField("Empresa", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Entrar")


class EmpresaForm(FlaskForm):
    nombrecomercial = StringField(
        "Nombre comercial", validators=[DataRequired(), Length(max=120)]
    )
    cif = StringField("CIF", validators=[DataRequired(), Length(max=20)])
    latitud = FloatField("Latitud", validators=[DataRequired()])
    longitud = FloatField("Longitud", validators=[DataRequired()])
    radio = IntegerField("Radio (metros)", validators=[DataRequired()])
    submit = SubmitField("Guardar")


class RolForm(FlaskForm):
    nombre_rol = StringField(
        "Nombre del rol", validators=[DataRequired(), Length(max=80)]
    )
    submit = SubmitField("Guardar")


class TrabajadorForm(FlaskForm):
    nif = StringField("NIF", validators=[DataRequired(), Length(max=20)])
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    apellidos = StringField("Apellidos", validators=[DataRequired(), Length(max=120)])
    passw = PasswordField("Contraseña", validators=[DataRequired(), Length(max=255)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    telef = TelField("Teléfono")
    rol_id = SelectField("Rol", coerce=int, validators=[DataRequired()])
    horario_id = SelectField("Horario", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Guardar")


class HorarioForm(FlaskForm):
    nombre_horario = StringField(
        "Nombre del horario", validators=[DataRequired(), Length(max=80)]
    )
    descripcion = StringField("Descripción", validators=[Length(max=255)])
    submit = SubmitField("Guardar")


class FranjaForm(FlaskForm):
    dia_id = SelectField("Día", coerce=int, validators=[DataRequired()])
    hora_entrada = TimeField(
        "Hora de entrada", validators=[DataRequired()], format="%H:%M"
    )
    hora_salida = TimeField(
        "Hora de salida", validators=[DataRequired()], format="%H:%M"
    )
    submit = SubmitField("Añadir franja")
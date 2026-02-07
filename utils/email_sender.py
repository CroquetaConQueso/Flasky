import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def _get_sender_display_name(default_name: str) -> str:
    sender_name_tuple = current_app.config.get("MAIL_DEFAULT_SENDER")
    if isinstance(sender_name_tuple, (tuple, list)) and len(sender_name_tuple) > 0:
        return sender_name_tuple[0]
    return default_name


def _send_smtp(destinatario: str, subject: str, text: str, html: str, default_sender_name: str) -> bool:
    """
    Envía un email multipart (plain + html) usando SMTP+STARTTLS.
    Devuelve True/False sin lanzar excepción (las funciones públicas ya controlan).
    """
    try:
        smtp_server = current_app.config.get("MAIL_SERVER")
        smtp_port = current_app.config.get("MAIL_PORT")
        sender_email = current_app.config.get("MAIL_USERNAME")
        sender_password = current_app.config.get("MAIL_PASSWORD")

        sender_display_name = _get_sender_display_name(default_sender_name)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_display_name} <{sender_email}>"
        msg["To"] = destinatario

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, destinatario, msg.as_string())

        return True

    except Exception as e:
        print(f"[ERROR] Fallo enviando correo: {e}")
        return False


# -----------------------------
# 1) Recuperación de contraseña
# -----------------------------
def enviar_correo_password(destinatario: str, nombre_usuario: str, link_reset: str) -> bool:
    """
    Envío SMTP de correo de recuperación.
    IMPORTANTE: En la versión con token (15 min), el 3er parámetro es un LINK, no una password.
    Si aún usas password temporal, cambia el contenido aquí o crea otra función.
    """
    subject = "Recuperación de contraseña - App Presencia"

    text = f"""
Hola {nombre_usuario},

Se ha solicitado restablecer tu contraseña.

Abre este enlace (caduca en 15 minutos):
{link_reset}

Si no has solicitado esto, ignora este correo.
""".strip()

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; color:#000; background-color:#f4f4f4;">
    <div style="max-width:600px;margin:0 auto;padding:20px;background:#fff;border:4px solid #000;box-shadow:8px 8px 0px #000;">
      <h2 style="text-transform:uppercase;border-bottom:4px solid #000;padding-bottom:10px;margin-top:0;">Recuperación de acceso</h2>
      <p>Hola <strong>{nombre_usuario}</strong>,</p>
      <p>Hemos recibido una solicitud para restablecer tu contraseña.</p>

      <div style="margin:20px 0;text-align:center;">
        <a href="{link_reset}"
           style="display:inline-block;background:#3a86ff;color:#fff;text-decoration:none;font-weight:900;border:4px solid #000;padding:12px 20px;box-shadow:6px 6px 0px #000;text-transform:uppercase;">
           Restablecer contraseña
        </a>
      </div>

      <p style="font-size:12px;color:#666;margin-top:30px;border-top:2px solid #000;padding-top:10px;">
        Este enlace caduca en 15 minutos. Si no lo solicitaste, ignora este correo.
      </p>
    </div>
  </body>
</html>
""".strip()

    return _send_smtp(destinatario, subject, text, html, default_sender_name="Soporte RRHH")


# --------------------------------------
# 2) Resolución de incidencia (admin)
# --------------------------------------
def enviar_correo_resolucion(
    destinatario: str,
    nombre: str,
    tipo_incidencia: str,
    estado: str,
    comentario_admin: str,
    f_inicio: str,
    f_fin: str
) -> bool:
    traducciones_tipo = {
        "VACACIONES": "Vacaciones",
        "BAJA": "Baja Médica",
        "ASUNTOS_PROPIOS": "Asuntos Propios",
        "OLVIDO": "Olvido de Fichaje",
        "HORAS_EXTRA": "Horas Extra",
    }
    tipo_legible = traducciones_tipo.get(tipo_incidencia, (tipo_incidencia or "").replace("_", " ").capitalize())

    subject = f"Resolución: {tipo_legible} ({estado})"

    if estado == "APROBADA":
        color_header = "#2ed573"
        titulo_estado = "SOLICITUD APROBADA"
        texto_intro = "Tu solicitud ha sido aceptada."
    else:
        color_header = "#ff4757"
        titulo_estado = "SOLICITUD RECHAZADA"
        texto_intro = "Tu solicitud no ha podido ser aceptada."

    text = f"""
Hola {nombre},

{texto_intro}

DETALLES:
Tipo: {tipo_legible}
Desde: {f_inicio}
Hasta: {f_fin}

Comentario de Administración:
{comentario_admin}
""".strip()

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; color:#000; background-color:#f4f4f4;">
    <div style="max-width:600px;margin:0 auto;padding:20px;background:#fff;border:4px solid #000;box-shadow:8px 8px 0px #000;">

      <div style="background-color:{color_header};border:4px solid #000;padding:15px;text-align:center;margin-bottom:20px;">
        <h2 style="margin:0;color:#fff;text-transform:uppercase;font-weight:900;letter-spacing:1px;text-shadow:2px 2px 0px #000;">
          {titulo_estado}
        </h2>
      </div>

      <p>Hola <strong>{nombre}</strong>,</p>
      <p>{texto_intro}</p>

      <div style="background-color:#eef;border:2px solid #000;padding:15px;margin:15px 0;">
        <p style="margin:5px 0;"><strong>TIPO:</strong> {tipo_legible}</p>
        <p style="margin:5px 0;"><strong>DESDE:</strong> {f_inicio}</p>
        <p style="margin:5px 0;"><strong>HASTA:</strong> {f_fin}</p>
      </div>

      <div style="background-color:#f1f1f1;border-left:6px solid #000;padding:15px;margin:20px 0;">
        <p style="margin:0 0 5px 0;font-weight:900;text-transform:uppercase;">Respuesta de Administración:</p>
        <p style="margin:0;font-style:italic;">"{comentario_admin}"</p>
      </div>

      <p style="font-size:12px;color:#666;margin-top:30px;border-top:2px solid #000;padding-top:10px;">
        Puedes consultar el historial completo en la App Móvil.
      </p>

    </div>
  </body>
</html>
""".strip()

    return _send_smtp(destinatario, subject, text, html, default_sender_name="RRHH")


# --------------------------------------
# 3) Alerta por ausencia de fichaje
# --------------------------------------
def enviar_correo_ausencia(destinatario: str, nombre: str) -> bool:
    subject = "ALERTA: Ausencia de fichaje detectada"

    text = f"""
Hola {nombre},

El sistema ha detectado que tienes turno asignado hoy, pero NO consta tu fichaje de entrada.

Por favor, accede a la aplicación para fichar o contacta con RRHH si es un error.
""".strip()

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; color:#000; background-color:#f4f4f4;">
    <div style="max-width:600px;margin:0 auto;padding:20px;background:#fff;border:4px solid #000;box-shadow:8px 8px 0px #000;">

      <div style="background-color:#ffde59;border-bottom:4px solid #000;padding:15px;text-align:center;margin-bottom:20px;">
        <h2 style="margin:0;color:#000;text-transform:uppercase;font-weight:900;">⚠️ ALERTA DE AUSENCIA</h2>
      </div>

      <p>Hola <strong>{nombre}</strong>,</p>
      <p>Nuestros sistemas indican que <strong>tienes turno hoy</strong> pero no hemos registrado tu entrada.</p>

      <div style="background-color:#fff0f3;border-left:6px solid #ff4757;padding:15px;margin:20px 0;">
        <p style="margin:0;color:#ff4757;font-weight:bold;">Acción requerida:</p>
        <p style="margin:5px 0 0 0;">Si estás trabajando, por favor entra en la App y ficha ahora mismo.</p>
      </div>

      <p style="font-size:12px;color:#666;margin-top:30px;border-top:2px solid #000;padding-top:10px;">
        Si estás de baja o vacaciones y recibes esto, contacta con RRHH para corregir tu calendario.
      </p>

    </div>
  </body>
</html>
""".strip()

    return _send_smtp(destinatario, subject, text, html, default_sender_name="RRHH Alertas")

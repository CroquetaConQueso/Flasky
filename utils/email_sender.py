import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def enviar_correo_password(destinatario, nombre_usuario, nueva_password):
    try:
        smtp_server = current_app.config.get('MAIL_SERVER')
        smtp_port = current_app.config.get('MAIL_PORT')
        sender_email = current_app.config.get('MAIL_USERNAME')
        sender_password = current_app.config.get('MAIL_PASSWORD')
        
        sender_name_tuple = current_app.config.get('MAIL_DEFAULT_SENDER')
        if isinstance(sender_name_tuple, tuple) or isinstance(sender_name_tuple, list):
            sender_display_name = sender_name_tuple[0]
        else:
            sender_display_name = "Soporte RRHH"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Recuperacion de Clave - App Presencia"
        msg["From"] = f"{sender_display_name} <{sender_email}>"
        msg["To"] = destinatario

        text = f"""
        Hola {nombre_usuario},

        Se ha solicitado restablecer tu contraseña.
        Tu nueva clave temporal es: {nueva_password}

        Por favor, cámbiala al iniciar sesión.
        """

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #000; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #fff; border: 4px solid #000; box-shadow: 8px 8px 0px #000;">
                <h2 style="text-transform: uppercase; border-bottom: 4px solid #000; padding-bottom: 10px; margin-top: 0;">Recuperacion de Acceso</h2>
                <p>Hola <strong>{nombre_usuario}</strong>,</p>
                <p>Hemos generado una nueva contraseña temporal para ti:</p>
                
                <div style="background-color: #000; color: #FFD700; padding: 20px; margin: 20px 0; text-align: center; border: 2px solid #000;">
                    <span style="font-size: 24px; font-weight: 900; letter-spacing: 2px;">{nueva_password}</span>
                </div>

                <p>Utiliza esta clave para entrar en la App.</p>
            </div>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, destinatario, msg.as_string())
            
        return True

    except Exception as e:
        print(f"[ERROR] Fallo enviando correo password: {e}")
        return False

# --- FUNCIÓN ACTUALIZADA CON FECHAS ---
def enviar_correo_resolucion(destinatario, nombre, tipo_incidencia, estado, comentario_admin, f_inicio, f_fin):
    try:
        smtp_server = current_app.config.get('MAIL_SERVER')
        smtp_port = current_app.config.get('MAIL_PORT')
        sender_email = current_app.config.get('MAIL_USERNAME')
        sender_password = current_app.config.get('MAIL_PASSWORD')

        sender_name_tuple = current_app.config.get('MAIL_DEFAULT_SENDER')
        if isinstance(sender_name_tuple, tuple) or isinstance(sender_name_tuple, list):
            sender_display_name = sender_name_tuple[0]
        else:
            sender_display_name = "RRHH"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Resolucion: {tipo_incidencia} ({estado})"
        msg["From"] = f"{sender_display_name} <{sender_email}>"
        msg["To"] = destinatario

        if estado == "APROBADA":
            color_header = "#2ed573" 
            titulo_estado = "SOLICITUD APROBADA"
            texto_intro = "Tu solicitud ha sido aceptada."
        else:
            color_header = "#ff4757" 
            titulo_estado = "SOLICITUD RECHAZADA"
            texto_intro = "Tu solicitud no ha podido ser aceptada."

        # Texto plano
        text = f"""
        Hola {nombre},
        
        {texto_intro}
        
        DETALLES:
        Tipo: {tipo_incidencia}
        Desde: {f_inicio}
        Hasta: {f_fin}
        
        Comentario de Administración:
        {comentario_admin}
        """

        # HTML con estilo
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #000; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #fff; border: 4px solid #000; box-shadow: 8px 8px 0px #000;">
                
                <div style="background-color: {color_header}; border: 4px solid #000; padding: 15px; text-align: center; margin-bottom: 20px;">
                    <h2 style="margin: 0; color: #fff; text-transform: uppercase; font-weight: 900; letter-spacing: 1px; text-shadow: 2px 2px 0px #000;">{titulo_estado}</h2>
                </div>

                <p>Hola <strong>{nombre}</strong>,</p>
                <p>{texto_intro}</p>
                
                <div style="background-color: #eef; border: 2px solid #000; padding: 15px; margin: 15px 0;">
                    <p style="margin: 5px 0;"><strong>TIPO:</strong> {tipo_incidencia}</p>
                    <p style="margin: 5px 0;"><strong>DESDE:</strong> {f_inicio}</p>
                    <p style="margin: 5px 0;"><strong>HASTA:</strong> {f_fin}</p>
                </div>
                
                <div style="background-color: #f1f1f1; border-left: 6px solid #000; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0 0 5px 0; font-weight: 900; text-transform: uppercase;">Respuesta de Administracion:</p>
                    <p style="margin: 0; font-style: italic;">"{comentario_admin}"</p>
                </div>

                <p style="font-size: 12px; color: #666; margin-top: 30px; border-top: 2px solid #000; padding-top: 10px;">
                    Puedes consultar el historial completo en la App Movil.
                </p>
            </div>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, destinatario, msg.as_string())
            
        return True

    except Exception as e:
        print(f"[ERROR] Fallo enviando correo resolucion: {e}")
        return False
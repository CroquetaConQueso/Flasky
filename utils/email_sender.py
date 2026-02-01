import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def enviar_correo_password(destinatario, nombre_usuario, nueva_password):
    """
    Envía un correo con la nueva contraseña generada usando la configuración de Flask.
    Soporta Gmail y servidores con STARTTLS.
    """
    try:
        # Recuperar configuración de la app actual
        smtp_server = current_app.config.get('MAIL_SERVER')
        smtp_port = current_app.config.get('MAIL_PORT')
        sender_email = current_app.config.get('MAIL_USERNAME')
        sender_password = current_app.config.get('MAIL_PASSWORD')
        
        # Recuperamos el remitente por defecto (Nombre, Email)
        sender_name_tuple = current_app.config.get('MAIL_DEFAULT_SENDER')
        if isinstance(sender_name_tuple, tuple) or isinstance(sender_name_tuple, list):
            sender_display_name = sender_name_tuple[0]
        else:
            sender_display_name = "Soporte RRHH"

        # --- CREAR EL MENSAJE ---
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Recuperación de Contraseña - App Presencia"
        msg["From"] = f"{sender_display_name} <{sender_email}>"
        msg["To"] = destinatario

        # Cuerpo en Texto Plano
        text = f"""
        Hola {nombre_usuario},

        Se ha solicitado restablecer tu contraseña.
        Tu nueva clave temporal es: {nueva_password}

        Por favor, cámbiala al iniciar sesión.
        """

        # Cuerpo en HTML (Diseño limpio)
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 4px solid #000; box-shadow: 8px 8px 0px #000;">
                <h2 style="text-transform: uppercase; border-bottom: 4px solid #FFD700; padding-bottom: 10px;">Recuperación de Acceso</h2>
                <p>Hola <strong>{nombre_usuario}</strong>,</p>
                <p>Hemos generado una nueva contraseña temporal para ti:</p>
                
                <div style="background-color: #000; color: #FFD700; padding: 15px; margin: 20px 0; text-align: center;">
                    <span style="font-size: 24px; font-weight: 900; letter-spacing: 2px;">{nueva_password}</span>
                </div>

                <p>Utiliza esta clave para entrar en la App o en la Web.</p>
            </div>
          </body>
        </html>
        """

        # Adjuntar partes
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        # --- CONEXIÓN SEGURA CON GMAIL ---
        context = ssl.create_default_context()

        print(f"--> Conectando a {smtp_server}:{smtp_port}...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context) # ¡CRUCIAL PARA GMAIL!
            server.ehlo()
            
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, destinatario, msg.as_string())
            
            print(f"--> Correo enviado correctamente a {destinatario}")

        return True

    except Exception as e:
        print(f"❌ ERROR CRÍTICO enviando correo: {e}")
        # Importante: Imprimimos la configuración para depurar (ocultando password)
        print(f"Config usada: Server={current_app.config.get('MAIL_SERVER')}, User={current_app.config.get('MAIL_USERNAME')}")
        return False
import smtplib
from email.message import EmailMessage
from flask import current_app

def enviar_correo_password(destinatario, nombre, nueva_pass):
    try:
        msg = EmailMessage()
        msg['Subject'] = 'RECUPERACION DE CONTRASEÑA - Control de Presencia'
        msg['From'] = current_app.config['MAIL_USERNAME']
        msg['To'] = destinatario
        
        # CUERPO DEL MENSAJE , se tiene que usar html para el cuerpo para que no se vea mal
        mensaje_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #212121; background-color: #FAFAFA; padding: 20px;">
            
            <div style="max-width: 500px; margin: 0 auto; background-color: #FFFFFF; border: 4px solid #212121; padding: 0;">
                
                <div style="background-color: #FFD700; padding: 20px; border-bottom: 4px solid #212121; text-align: center;">
                    <h2 style="margin: 0; text-transform: uppercase; letter-spacing: 2px;">ACCESO EMPLEADOS</h2>
                </div>

                <div style="padding: 30px;">
                    <p style="font-size: 16px;">Hola <strong>{nombre}</strong>,</p>
                    <p>Hemos recibido una solicitud para restablecer tu acceso.</p>
                    <p>Aquí tienes tu clave temporal:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <span style="font-size: 24px; font-weight: bold; background-color: #212121; color: #FFD700; padding: 15px 30px; letter-spacing: 3px;">
                            {nueva_pass}
                        </span>
                    </div>

                    <p style="font-size: 14px;">Entra en la App y cambia esta contraseña desde tu perfil lo antes posible.</p>
                </div>

                <div style="background-color: #212121; color: #FFFFFF; padding: 10px; text-align: center; font-size: 12px;">
                    SISTEMA DE CONTROL DE PRESENCIA
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.set_content(f"Hola {nombre}, tu nueva contraseña temporal es: {nueva_pass}") # Texto plano alternativo
        msg.add_alternative(mensaje_html, subtype='html')

        # Usamos smtp
        server = smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        server.starttls()
        server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        
        print(f"Correo enviado a {destinatario}")
        return True
    except Exception as e:
        print(f"Error enviando correo: {e}")
        return False
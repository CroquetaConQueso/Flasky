import firebase_admin
from firebase_admin import credentials, messaging
import os

# Evitar inicializar la app multiples veces si Flask se reinicia
if not firebase_admin._apps:
    # Ruta al archivo que acabas de descargar
    cred_path = os.path.join(os.getcwd(), "serviceAccountKey.json")
    
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("[FIREBASE] Conectado correctamente.")
    else:
        print(f"[FIREBASE] No se encontro {cred_path}. Las notificaciones no funcionaran.")

def enviar_notificacion_push(token, titulo, cuerpo):
    """Envia una notificacion Push a un dispositivo Android especifico."""
    if not token:
        print("[FIREBASE] Usuario sin token FCM. No se puede enviar.")
        return False

    try:
        # Construir el mensaje
        message = messaging.Message(
            notification=messaging.Notification(
                title=titulo,
                body=cuerpo,
            ),
            # Datos extra (opcional, util para abrir una pantalla especifica)
            data={
                "titulo": titulo,
                "mensaje": cuerpo
            },
            token=token,
        )

        # Enviar
        response = messaging.send(message)
        print(f"[FIREBASE] Notificacion enviada ID: {response}")
        return True

    except Exception as e:
        print(f"[FIREBASE] Error enviando push: {e}")
        return False
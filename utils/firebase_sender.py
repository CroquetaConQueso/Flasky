import firebase_admin
from firebase_admin import credentials, messaging
import os

# Cliente Firebase (FCM) para notificaciones push
if not firebase_admin._apps:
    cred_path = os.path.join(os.getcwd(), "serviceAccountKey.json")

    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("[FIREBASE] Conectado correctamente.")
    else:
        print(f"[FIREBASE] ERROR CRÍTICO: No se encontró {cred_path}.")


def enviar_notificacion_push(token, titulo, cuerpo):
    # Envío de push a un token FCM
    if not token:
        raise ValueError("Usuario sin token FCM")

    message = messaging.Message(
        notification=messaging.Notification(
            title=titulo,
            body=cuerpo,
        ),
        data={
            "title": titulo,
            "body": cuerpo,
            "titulo": titulo,
            "mensaje": cuerpo
        },
        token=token,
    )

    response = messaging.send(message)
    print(f"[FIREBASE] ÉXITO REAL. ID: {response}")
    return True

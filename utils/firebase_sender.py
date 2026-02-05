import firebase_admin
from firebase_admin import credentials, messaging
import os

# Inicialización única
if not firebase_admin._apps:
    cred_path = os.path.join(os.getcwd(), "serviceAccountKey.json")
    
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("[FIREBASE] Conectado correctamente.")
    else:
        print(f"[FIREBASE] ERROR CRÍTICO: No se encontró {cred_path}.")

def enviar_notificacion_push(token, titulo, cuerpo):
    """
    Envía notificación. NO captura excepciones para que el
    código que llama (auth.py) sepa si ha fallado.
    """
    if not token:
        # Lanzamos error para que auth.py se entere
        raise ValueError("Usuario sin token FCM")

    # Construir el mensaje con datos redundantes para asegurar que Android lo lea
    message = messaging.Message(
        notification=messaging.Notification(
            title=titulo,
            body=cuerpo,
        ),
        data={
            "title": titulo,    # Claves estándar
            "body": cuerpo,
            "titulo": titulo,   # Claves legacy (para tu app actual)
            "mensaje": cuerpo
        },
        token=token,
    )

    # Si esto falla, explotará y auth.py capturará el error real
    response = messaging.send(message)
    print(f"[FIREBASE] ÉXITO REAL. ID: {response}")
    return True
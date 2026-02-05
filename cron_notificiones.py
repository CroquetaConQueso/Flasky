from app import create_app
from extensions import db
from models import Trabajador, Horario, Franja, Dia, Fichaje
from utils.email_sender import enviar_correo_ausencia
# IMPORTANTE: Importamos la funcion para enviar al movil
from utils.firebase_sender import enviar_notificacion_push
from datetime import datetime, date
import sys

# Mapeo de dias de Python (0=Lunes) a tu Base de Datos
DIAS_SEMANA = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo"
}

def comprobar_ausencias():
    app = create_app()
    
    # Aseguramos que use la configuracion de produccion (MySQL) si es necesario
    # Si tu config.py ya lo gestiona, esto es redundante pero seguro
    uri_mysql = "mysql+pymysql://SQulito:usuario12!@SQulito.mysql.eu.pythonanywhere-services.com/SQulito$app"
    app.config['SQLALCHEMY_DATABASE_URI'] = uri_mysql

    with app.app_context():
        print("\n--- INICIANDO COMPROBACION DE AUSENCIAS ---")
        
        hoy = date.today()
        dia_semana_num = hoy.weekday()
        nombre_dia = DIAS_SEMANA[dia_semana_num]
        
        print(f"Fecha: {hoy} ({nombre_dia})")

        # 1. Buscar el ID del dia de hoy en la BDD
        dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
        if not dia_db:
            print("Error: El dia no existe en la base de datos.")
            return

        # 2. Obtener trabajadores
        trabajadores = Trabajador.query.all()
        cont_emails = 0
        cont_push = 0

        for t in trabajadores:
            # A. Tiene horario?
            if not t.idHorario:
                continue

            # B. Trabaja hoy? (Miramos si tiene Franjas para hoy)
            franja_hoy = Franja.query.filter_by(id_horario=t.idHorario, id_dia=dia_db.id).first()
            if not franja_hoy:
                # Hoy libra
                continue

            # C. Ha fichado ENTRADA hoy?
            fichaje = Fichaje.query.filter(
                Fichaje.id_trabajador == t.id_trabajador,
                Fichaje.tipo == 'ENTRADA',
                db.func.date(Fichaje.fecha_hora) == hoy
            ).first()

            if fichaje:
                print(f"OK: {t.nombre} ha fichado a las {fichaje.fecha_hora.strftime('%H:%M')}")
            else:
                print(f"FALTA: {t.nombre} NO HA FICHADO. Enviando alertas...")
                
                # -----------------------------------------------------------
                # 1. ENVIAR CORREO (Tu codigo original)
                # -----------------------------------------------------------
                if t.email:
                    exito = enviar_correo_ausencia(t.email, t.nombre)
                    if exito:
                        print(f"   -> Email enviado a: {t.email}")
                        cont_emails += 1
                    else:
                        print(f"   -> Error enviando email a: {t.email}")
                
                # -----------------------------------------------------------
                # 2. ENVIAR NOTIFICACION PUSH (Lo nuevo)
                # -----------------------------------------------------------
                if t.fcm_token:
                    try:
                        titulo = "Falta de Fichaje"
                        mensaje = f"Hola {t.nombre}, consta que trabajas hoy y no has registrado tu entrada."
                        enviar_notificacion_push(t.fcm_token, titulo, mensaje)
                        print(f"   -> Notificacion Push enviada al movil.")
                        cont_push += 1
                    except Exception as e:
                        print(f"   -> Error enviando Push: {e}")
                else:
                    print("   -> No se puede enviar Push (Sin Token FCM).")

        print(f"--- FIN: Emails: {cont_emails} | Notificaciones: {cont_push} ---\n")

if __name__ == "__main__":
    comprobar_ausencias()
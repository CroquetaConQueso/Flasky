from app import create_app
from extensions import db
from models import Trabajador, Horario, Franja, Dia, Fichaje
from utils.email_sender import enviar_correo_ausencia
from datetime import datetime, date

# Mapeo de días de Python (0=Lunes) a tu Base de Datos
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
    with app.app_context():
        print("\n🔎 --- INICIANDO COMPROBACIÓN DE AUSENCIAS ---")
        
        hoy = date.today()
        dia_semana_num = hoy.weekday()
        nombre_dia = DIAS_SEMANA[dia_semana_num]
        
        print(f"📅 Fecha: {hoy} ({nombre_dia})")

        # 1. Buscar el ID del día de hoy en la BDD
        dia_db = Dia.query.filter_by(nombre=nombre_dia).first()
        if not dia_db:
            print("❌ Error: El día no existe en la base de datos.")
            return

        # 2. Obtener trabajadores
        trabajadores = Trabajador.query.all()
        cont_enviados = 0

        for t in trabajadores:
            # A. ¿Tiene horario?
            if not t.idHorario:
                continue

            # B. ¿Trabaja hoy? (Miramos si tiene Franjas para hoy)
            franja_hoy = Franja.query.filter_by(id_horario=t.idHorario, id_dia=dia_db.id).first()
            if not franja_hoy:
                # Hoy libra (no tiene franjas definidas para este día)
                continue

            # C. ¿Ha fichado ENTRADA hoy?
            fichaje = Fichaje.query.filter(
                Fichaje.id_trabajador == t.id_trabajador,
                Fichaje.tipo == 'ENTRADA',
                db.func.date(Fichaje.fecha_hora) == hoy
            ).first()

            if fichaje:
                print(f"✅ {t.nombre} {t.apellidos}: Ha fichado ({fichaje.fecha_hora.strftime('%H:%M')})")
            else:
                print(f"⚠️  {t.nombre} {t.apellidos}: NO HA FICHADO. Enviando alerta...")
                
                # D. ENVÍO REAL DE CORREO (Líneas descomentadas)
                if t.email:
                    exito = enviar_correo_ausencia(t.email, t.nombre)
                    if exito:
                        print(f"   📧 [ENVÍO OK] Correo enviado a: {t.email}")
                        cont_enviados += 1
                    else:
                        print(f"   ❌ [ENVÍO FALLIDO] Error al enviar a: {t.email}")
                else:
                    print("   ℹ️ Usuario sin email configurado.")

        print(f"🏁 --- FIN: Se han enviado {cont_enviados} avisos. ---\n")

if __name__ == "__main__":
    comprobar_ausencias()
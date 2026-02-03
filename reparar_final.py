from app import app
from extensions import db
from models import Dia, Franja, Horario
from datetime import time

print("--- REPARACIÓN FINAL (MODELO REAL) ---")

with app.app_context():
    # 1. REPARAR TABLA DÍAS (Usando 'id' y 'nombre')
    print("\n[PASO 1] Verificando tabla 'dia'...")
    try:
        dias = Dia.query.all()
        if not dias:
            print("⚠️  TABLA VACÍA. Insertando días...")
            lista_dias = [
                "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"
            ]
            for n in lista_dias:
                # AQUÍ ESTABA EL ERROR: Usamos 'nombre' (tu modelo), no 'nombre_dia'
                nuevo = Dia(nombre=n)
                db.session.add(nuevo)
            db.session.commit()
            print("✅ Días insertados correctamente.")
        else:
            print(f"✅ Tabla 'dia' OK ({len(dias)} registros).")
            # Verificar nombres correctos
            primero = dias[0]
            print(f"   Día 1: ID={primero.id}, Nombre='{primero.nombre}'")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")

    # 2. INTENTO DE CREAR FRANJA (Prueba final)
    print("\n[PASO 2] Prueba de inserción de franja...")
    try:
        horario = Horario.query.first()
        if horario:
            # Buscamos el lunes (usando 'nombre')
            lunes = Dia.query.filter_by(nombre="lunes").first()
            if lunes:
                print(f"   Intentando guardar franja para Horario {horario.id_horario} y Día {lunes.id}...")
                nueva = Franja(
                    id_horario=horario.id_horario,
                    id_dia=lunes.id,  # Usamos el ID correcto del día
                    hora_entrada=time(9, 0),
                    hora_salida=time(14, 0)
                )
                db.session.add(nueva)
                db.session.flush() # Prueba sin commit
                print("✅ ¡ÉXITO! La franja se guarda correctamente.")
                db.session.rollback()
            else:
                print("❌ No se encontró el día 'lunes'.")
        else:
            print("ℹ️  Crea un horario primero.")

    except Exception as e:
        print(f"❌ ERROR AL GUARDAR: {e}")

print("\n--- FIN ---")
import sys
from app import create_app
from extensions import db
from models import Trabajador

# Inicializamos la app
app = create_app()

# CREDENCIALES EXPLICITAS DE TU MYSQL (Extraídas de tu config.py)
uri_mysql = "mysql+pymysql://SQulito:usuario12!@SQulito.mysql.eu.pythonanywhere-services.com/SQulito$app"
app.config['SQLALCHEMY_DATABASE_URI'] = uri_mysql

print(f"--- CONECTANDO A MYSQL: {uri_mysql.split('@')[1]} ---")

with app.app_context():
    try:
        # 1. Obtener TODOS los trabajadores
        usuarios = Trabajador.query.all()
        
        if not usuarios:
            print("⚠️ No se encontraron usuarios en la base de datos MySQL.")
            sys.exit()

        print(f"✅ Se han encontrado {len(usuarios)} usuarios.")
        print("⏳ Reparando contraseñas a '1234' (Hasheadas)...")
        
        for u in usuarios:
            # Forzamos la contraseña '1234' para que se genere el hash nuevo
            u.set_password("1234")
            print(f"   -> Usuario: {u.nombre} | NIF: {u.nif}")

        # 2. Guardar cambios en MySQL
        db.session.commit()
        
        print("\n🎉 REPARACIÓN COMPLETADA.")
        print("Todas las contraseñas son ahora: 1234")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
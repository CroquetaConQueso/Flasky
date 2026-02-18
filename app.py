from flask import Flask, render_template
from config import Config
from extensions import db, migrate, jwt, api

# 1. Imports de la API (Para la App Móvil - JSON)
from resources.auth import blp as AuthBlueprint
from resources.empresa import blp as EmpresaBlueprint
from resources.fichaje import blp as FichajeBlueprint
from resources.incidencia import blp as IncidenciaBlueprint
from resources.avisos import blp as AvisosBlueprint
# 2. Imports de la Web (Para el Administrador - HTML)
from routes.auth_routes import auth_bp
from routes.super_routes import super_bp
from routes.empresa_routes import empresa_bp
from routes.rrhh_routes import rrhh_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- Inicialización de Extensiones ---
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    api.init_app(app)

    # --- Registro de API (Móvil) ---
    # Se registran en 'api' (Flask-Smorest) con prefijo /api
    api.register_blueprint(AuthBlueprint, url_prefix="/api")
    api.register_blueprint(EmpresaBlueprint, url_prefix="/api")
    api.register_blueprint(FichajeBlueprint, url_prefix="/api")
    api.register_blueprint(IncidenciaBlueprint, url_prefix="/api")
    api.register_blueprint(AvisosBlueprint, url_prefix="/api")
    # --- Registro de Web (Admin) ---
    # Se registran en 'app' (Flask estándar)
    app.register_blueprint(auth_bp)
    app.register_blueprint(super_bp)
    app.register_blueprint(empresa_bp)
    app.register_blueprint(rrhh_bp)

    # --- Ruta Principal (Landing Page) ---
    @app.route("/")
    def index():
        return render_template("index.html")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5002, host="0.0.0.0")
import os

class Config:
    # --- CLAVES DE SEGURIDAD ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-secreta-desarrollo-web-carlos")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "clave-super-secreta-jwt-api-carlos")

    # --- BASE DE DATOS ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://SQulito:usuario12!@SQulito.mysql.eu.pythonanywhere-services.com/SQulito$app"
    )
    
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- DOCUMENTACIÓN API ---
    API_TITLE = "API de Control de Presencia"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.2"
    OPENAPI_URL_PREFIX = "/"
    OPENAPI_SWAGGER_UI_PATH = "/swagger-ui"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    # --- CONFIGURACIÓN DEL SERVIDOR DE CORREO (SMTP) ---
    
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    

    MAIL_USERNAME = "ctorleo571@iesfuengirola1.es"

    MAIL_PASSWORD = "xqunwlcpwcmgilpp"
    
    MAIL_DEFAULT_SENDER = ("Soporte PracticaApi", "ctorleo571@iesfuengirola1.es")
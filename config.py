import os

class Config:
    # Clave para las sesiones de la Web (cookies)
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-secreta-desarrollo-web-carlos")
    
    # Base de datos
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://SQulito:usuario12!@SQulito.mysql.eu.pythonanywhere-services.com/SQulito$app"
    )
    

    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 280}

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración de JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "clave-super-secreta-jwt-api-carlos")

    API_TITLE = "API de Control de Presencia"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.2"
    OPENAPI_URL_PREFIX = "/"
    OPENAPI_SWAGGER_UI_PATH = "/swagger-ui"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
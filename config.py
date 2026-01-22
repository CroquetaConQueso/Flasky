import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://SQulito:usuario12!@SQulito.mysql.eu.pythonanywhere-services.com/SQulito$app"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

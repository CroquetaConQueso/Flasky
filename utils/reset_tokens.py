from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


def _serializer():
    return URLSafeTimedSerializer(
        secret_key=current_app.config["SECRET_KEY"],
        salt="pwd-reset"
    )


def generar_token_reset(user_id: int) -> str:
    s = _serializer()
    return s.dumps({"uid": int(user_id)})


def validar_token_reset(token: str, max_age_seconds: int = 900) -> int:
    s = _serializer()
    data = s.loads(token, max_age=max_age_seconds)
    return int(data["uid"])

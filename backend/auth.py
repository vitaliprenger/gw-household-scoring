import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

#: ``production`` schaltet die Absicherungen des Betriebs ein (Passwortpflicht,
#: keine Migration beim Start). Jeder andere Wert gilt als Entwicklung.
APP_ENV = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"

DEV_DEFAULT_PASSWORD = "geheim"
MIN_PASSWORD_LENGTH = 12


def _load_password() -> str:
    password = os.environ.get("APP_PASSWORD", "")
    if not IS_PRODUCTION:
        return password or DEV_DEFAULT_PASSWORD
    # In Produktion startet die Anwendung nicht ohne festes Passwort.
    if not password or password == DEV_DEFAULT_PASSWORD:
        raise RuntimeError(
            "APP_ENV=production: APP_PASSWORD muss gesetzt sein und darf nicht "
            f"'{DEV_DEFAULT_PASSWORD}' lauten."
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise RuntimeError(
            f"APP_ENV=production: APP_PASSWORD muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."
        )
    return password


APP_PASSWORD = _load_password()

_session_token = secrets.token_hex(32)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(password: str) -> str:
    # Bytes vergleichen: compare_digest lehnt str mit Umlauten ab.
    if not secrets.compare_digest(password.encode(), APP_PASSWORD.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falsches Passwort",
        )
    return _session_token


def require_auth(token: str = Depends(oauth2_scheme)):
    if not secrets.compare_digest(token, _session_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert",
            headers={"WWW-Authenticate": "Bearer"},
        )

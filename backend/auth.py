import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

APP_PASSWORD = os.environ.get("APP_PASSWORD", "geheim")

_session_token = secrets.token_hex(32)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(password: str) -> str:
    if not secrets.compare_digest(password, APP_PASSWORD):
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

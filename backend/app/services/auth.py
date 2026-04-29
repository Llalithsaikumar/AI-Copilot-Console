from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import Settings
from app.services.user_store import get_user_by_email, create_user, get_user_by_id


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def create_access_token(user_id: str, settings: Settings) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.access_token_exp_hours)
    payload = {"sub": user_id, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token subject missing")
    return str(subject)


def register_user(settings: Settings, email: str, password: str) -> dict:
    existing = get_user_by_email(settings, email)
    if existing:
        raise ValueError("Email already registered")
    return create_user(settings, email, hash_password(password))


def lookup_user_by_email(settings: Settings, email: str) -> dict | None:
    return get_user_by_email(settings, email)


def lookup_user_by_id(settings: Settings, user_id: str) -> dict | None:
    return get_user_by_id(settings, user_id)

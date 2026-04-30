from datetime import datetime, timedelta, timezone
from typing import Any

from passlib.context import CryptContext
from jose import JWTError, jwt

from app.config import get_settings

_settings = get_settings()
SECRET_KEY = _settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta_minutes: int | None = None,
) -> str:
    to_encode = dict(data)
    if expires_delta_minutes is not None:
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta_minutes)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from unittest.mock import MagicMock

from app.auth.dependencies import get_current_user
from app.auth.utils import create_access_token


def test_get_current_user_valid_token():
    token = create_access_token({"sub": "user123"})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user_id = get_current_user(credentials)
    assert user_id == "user123"


def test_get_current_user_invalid_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials)
    assert exc_info.value.status_code == 401


def test_get_current_user_no_sub():
    # Create a token without 'sub' claim
    from jose import jwt
    from app.auth.utils import SECRET_KEY
    token = jwt.encode({"exp": 9999999999}, SECRET_KEY, algorithm="HS256")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials)
    assert exc_info.value.status_code == 401

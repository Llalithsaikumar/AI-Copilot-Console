import pytest
import time
from app.auth.utils import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_string():
    hashed = hash_password("secret123")
    assert isinstance(hashed, str)
    assert hashed != "secret123"


def test_verify_password_correct():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_create_access_token_returns_jwt():
    token = create_access_token({"sub": "user123"})
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # JWT has 3 parts


def test_verify_token_valid():
    token = create_access_token({"sub": "user123"})
    payload = verify_token(token)
    assert payload["sub"] == "user123"


def test_verify_token_invalid():
    with pytest.raises(Exception):
        verify_token("invalid-token")


def test_verify_token_expired():
    token = create_access_token({"sub": "user123"}, expires_delta_minutes=-1)
    with pytest.raises(Exception):
        verify_token(token)

import pytest
from app.auth.models import UserCreate, UserLogin, TokenResponse, UserInDB


def test_user_create_has_email_and_password():
    user = UserCreate(email="test@example.com", password="secret123")
    assert user.email == "test@example.com"
    assert user.password == "secret123"


def test_user_login_has_email_and_password():
    user = UserLogin(email="test@example.com", password="secret123")
    assert user.email == "test@example.com"


def test_token_response_has_access_token():
    response = TokenResponse(access_token="abc123", token_type="bearer")
    assert response.access_token == "abc123"
    assert response.token_type == "bearer"


def test_user_in_db_has_required_fields():
    user = UserInDB(
        email="test@example.com",
        password_hash="hashed",
        created_at="2026-04-30T00:00:00Z",
    )
    assert user.email == "test@example.com"
    assert user.password_hash == "hashed"

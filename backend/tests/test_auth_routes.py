import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user_collection():
    with patch("app.auth.routes._get_user_collection") as mock:
        collection = MagicMock()
        mock.return_value = collection
        yield collection


def test_register_success(client, mock_user_collection):
    mock_user_collection.find_one.return_value = None
    mock_user_collection.insert_one.return_value = MagicMock()
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "secret123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data


def test_register_duplicate_email(client, mock_user_collection):
    mock_user_collection.find_one.return_value = {"email": "test@example.com"}
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "secret123456"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_login_success(client, mock_user_collection):
    from app.auth.utils import hash_password
    mock_user_collection.find_one.return_value = {
        "email": "test@example.com",
        "password_hash": hash_password("secret123456"),
    }
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "secret123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, mock_user_collection):
    from app.auth.utils import hash_password
    mock_user_collection.find_one.return_value = {
        "email": "test@example.com",
        "password_hash": hash_password("secret123456"),
    }
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_login_nonexistent_user(client, mock_user_collection):
    mock_user_collection.find_one.return_value = None
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "secret123456"},
    )
    assert response.status_code == 401


def test_me_without_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 403  # FastAPI HTTPBearer returns 403 for missing auth


def test_me_with_invalid_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_register_short_password(client, mock_user_collection):
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "short"},
    )
    assert response.status_code == 422  # Validation error
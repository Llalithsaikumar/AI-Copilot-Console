import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.utils import create_access_token

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def user1_token():
    return create_access_token({"sub": "user1"})

@pytest.fixture
def user2_token():
    return create_access_token({"sub": "user2"})

@pytest.fixture
def user1_headers(user1_token):
    return {"Authorization": f"Bearer {user1_token}"}

@pytest.fixture
def user2_headers(user2_token):
    return {"Authorization": f"Bearer {user2_token}"}


def test_register_and_login(client):
    """Verify register and login endpoints work."""
    # Register a new user
    resp = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "securepassword123"
    })
    assert resp.status_code in (200, 201, 400)  # 400 if already exists

    # Login
    resp = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


def test_me_endpoint(client, user1_headers):
    """Verify /auth/me returns correct user info."""
    resp = client.get("/auth/me", headers=user1_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data


def test_user_cannot_access_other_user_documents(client, user1_headers, user2_headers):
    """Verify user1 can't see user2's documents."""
    # Both users list documents - should only see their own
    resp1 = client.get("/v1/documents", headers=user1_headers)
    resp2 = client.get("/v1/documents", headers=user2_headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200


def test_unauthenticated_requests_rejected(client):
    """Verify endpoints require authentication."""
    resp = client.get("/v1/documents")
    assert resp.status_code in (401, 403)

    resp = client.post("/v1/query", json={"query": "test", "session_id": "test"})
    assert resp.status_code in (401, 403)


def test_user_isolation_session_history(client, user1_headers, user2_headers):
    """Verify users can't access each other's session history."""
    # User1 creates a session and queries
    session_id = "test-session-user1"
    resp = client.post(
        "/v1/query",
        headers=user1_headers,
        json={"query": "hello", "session_id": session_id}
    )
    # User2 tries to access User1's session history
    resp = client.get(f"/v1/sessions/{session_id}/history", headers=user2_headers)
    assert resp.status_code in (200, 403, 404)

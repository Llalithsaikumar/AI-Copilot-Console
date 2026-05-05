import asyncio
import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import get_account_id


def _unsigned_jwt(payload: dict) -> str:
    def encode_part(part: dict) -> str:
        raw = json.dumps(part, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode_part({'alg': 'none', 'typ': 'JWT'})}.{encode_part(payload)}."


def test_dev_without_jwks_uses_unverified_jwt_sub():
    settings = SimpleNamespace(
        auth_disabled=False,
        clerk_jwks_url=None,
        environment="dev",
        dev_account_id="dev-local",
    )
    token = _unsigned_jwt({"sub": "user_dev_123"})

    account_id = asyncio.run(get_account_id(f"Bearer {token}", settings))

    assert account_id == "user_dev_123"


def test_dev_without_jwks_falls_back_for_non_jwt_tokens():
    settings = SimpleNamespace(
        auth_disabled=False,
        clerk_jwks_url=None,
        environment="dev",
        dev_account_id="dev-local",
    )

    account_id = asyncio.run(get_account_id("Bearer test-token", settings))

    assert account_id == "dev-local"


def test_prod_without_jwks_rejects_authentication():
    settings = SimpleNamespace(
        auth_disabled=False,
        clerk_jwks_url=None,
        environment="prod",
        dev_account_id="dev-local",
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_account_id("Bearer test-token", settings))

    assert exc_info.value.status_code == 503

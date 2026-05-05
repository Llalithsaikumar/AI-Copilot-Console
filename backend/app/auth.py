"""Clerk JWT verification. Account id = JWT `sub` (never from request body)."""

from __future__ import annotations

import logging
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class JWTVerificationError(Exception):
    pass


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def verify_clerk_token(token: str, settings: Settings) -> str:
    if not settings.clerk_jwks_url:
        raise JWTVerificationError("CLERK_JWKS_URL is not configured")
    try:
        signing_key = _jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        options: dict = {"require": ["exp", "sub"]}
        if not settings.clerk_issuer:
            options["verify_iss"] = False
        if not settings.clerk_audience:
            options["verify_aud"] = False
        decode_kw: dict = {
            "algorithms": ["RS256", "ES256"],
            "options": options,
        }
        if settings.clerk_issuer:
            decode_kw["issuer"] = settings.clerk_issuer
        if settings.clerk_audience:
            decode_kw["audience"] = settings.clerk_audience

        payload = jwt.decode(token, signing_key.key, **decode_kw)
    except jwt.InvalidTokenError as exc:
        raise JWTVerificationError(str(exc)) from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise JWTVerificationError("Token missing sub claim")
    return sub


def _decode_unverified_sub(token: str) -> str | None:
    """Extract `sub` from a local dev JWT when JWKS verification is not configured."""
    try:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except jwt.InvalidTokenError:
        return None

    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None


async def get_account_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Returns Clerk user id (`sub`). Use AUTH_DISABLED=true only in automated tests.
    """
    if settings.auth_disabled:
        return settings.dev_account_id

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(None, 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    if not settings.clerk_jwks_url:
        if settings.environment.lower() == "dev":
            unverified_sub = _decode_unverified_sub(token)
            if unverified_sub:
                logger.warning(
                    "CLERK_JWKS_URL unset; using unverified JWT sub in dev only"
                )
                return unverified_sub
            logger.warning(
                "CLERK_JWKS_URL unset; using DEV_ACCOUNT_ID without JWT verification (dev only)"
            )
            return settings.dev_account_id
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured (set CLERK_JWKS_URL)",
        )

    try:
        return verify_clerk_token(token, settings)
    except JWTVerificationError as exc:
        logger.info("JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def validate_session_belongs_to_account(session_id: str, account_id: str) -> None:
    """Sessions must be created as `{account_id}:{uuid}` so ownership is provable without an extra join."""
    prefix = f"{account_id}:"
    if not session_id.startswith(prefix):
        raise HTTPException(status_code=403, detail="Session does not belong to this account")

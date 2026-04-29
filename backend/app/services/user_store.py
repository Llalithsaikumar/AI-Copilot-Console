from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from app.config import Settings


_client: MongoClient | None = None


def _get_client(settings: Settings) -> MongoClient:
    global _client
    if not settings.mongo_uri:
        raise RuntimeError("MONGO_URI is required for MongoDB auth.")
    if _client is None:
        _client = MongoClient(settings.mongo_uri)
    return _client


def _users_collection(settings: Settings):
    client = _get_client(settings)
    db = client[settings.mongo_db_name]
    return db[settings.mongo_users_collection]


def ensure_indexes(settings: Settings) -> None:
    collection = _users_collection(settings)
    collection.create_index("email", unique=True)


def get_user_by_email(settings: Settings, email: str) -> dict | None:
    collection = _users_collection(settings)
    return collection.find_one({"email": email})


def get_user_by_id(settings: Settings, user_id: str) -> dict | None:
    collection = _users_collection(settings)
    return collection.find_one({"_id": user_id})


def create_user(settings: Settings, email: str, password_hash: str) -> dict:
    ensure_indexes(settings)
    collection = _users_collection(settings)
    user_id = str(uuid4())
    payload = {
        "_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        collection.insert_one(payload)
    except DuplicateKeyError as exc:
        raise ValueError("Email already registered") from exc
    return payload

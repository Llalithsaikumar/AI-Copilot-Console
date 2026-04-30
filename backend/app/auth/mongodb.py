import threading
from pymongo import MongoClient
from pymongo.database import Database
from app.config import get_settings

_client: MongoClient | None = None
_lock = threading.Lock()


def get_mongodb_client() -> MongoClient:
    """Get or create a singleton MongoDB client using settings."""
    global _client
    with _lock:
        if _client is None:
            settings = get_settings()
            _client = MongoClient(settings.mongodb_url)
        return _client


def get_database(database_name: str) -> Database:
    """Get a MongoDB database instance."""
    client = get_mongodb_client()
    return client[database_name]


def close_mongodb_connection() -> None:
    """Close the MongoDB connection and reset the singleton."""
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None

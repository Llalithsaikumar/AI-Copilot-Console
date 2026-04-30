from pymongo import MongoClient
from pymongo.database import Database
from typing import Optional

_client: Optional[MongoClient] = None


def get_mongodb_client(url: str) -> MongoClient:
    """Get or create a singleton MongoDB client."""
    global _client
    if _client is None:
        _client = MongoClient(url)
    return _client


def get_database(url: str, database_name: str) -> Database:
    """Get a MongoDB database instance."""
    client = get_mongodb_client(url)
    return client[database_name]


def close_mongodb_connection() -> None:
    """Close the MongoDB connection and reset the singleton."""
    global _client
    if _client is not None:
        _client.close()
        _client = None

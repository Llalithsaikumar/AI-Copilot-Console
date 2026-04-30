import pytest
from unittest.mock import MagicMock, patch

from app.auth.mongodb import get_mongodb_client, get_database, close_mongodb_connection


def setup_function():
    """Reset the MongoDB singleton between tests."""
    close_mongodb_connection()


def test_get_mongodb_client_returns_client():
    with patch("app.auth.mongodb.MongoClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        client = get_mongodb_client("mongodb://localhost:27017")
        mock_client_class.assert_called_once_with("mongodb://localhost:27017")
        assert client is mock_client


def test_get_database_returns_correct_db():
    with patch("app.auth.mongodb.MongoClient") as mock_client_class:
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_client_class.return_value = mock_client
        db = get_database("mongodb://localhost:27017", "test_db")
        assert db is mock_db

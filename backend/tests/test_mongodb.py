import pytest
from unittest.mock import MagicMock, patch

from app.auth.mongodb import get_mongodb_client, get_database, close_mongodb_connection


def setup_function():
    """Reset the MongoDB singleton between tests."""
    close_mongodb_connection()


def test_get_mongodb_client_returns_client():
    with patch("app.auth.mongodb.MongoClient") as mock_client_class, \
         patch("app.auth.mongodb.get_settings") as mock_get_settings:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_settings = MagicMock()
        mock_settings.mongodb_url = "mongodb://localhost:27017"
        mock_get_settings.return_value = mock_settings
        client = get_mongodb_client()
        mock_client_class.assert_called_once_with("mongodb://localhost:27017")
        assert client is mock_client


def test_get_database_returns_correct_db():
    with patch("app.auth.mongodb.MongoClient") as mock_client_class, \
         patch("app.auth.mongodb.get_settings") as mock_get_settings:
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_client_class.return_value = mock_client
        mock_settings = MagicMock()
        mock_settings.mongodb_url = "mongodb://localhost:27017"
        mock_get_settings.return_value = mock_settings
        db = get_database("test_db")
        assert db is mock_db


def test_singleton_returns_same_instance():
    with patch("app.auth.mongodb.MongoClient") as mock_client_class, \
         patch("app.auth.mongodb.get_settings") as mock_get_settings:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_settings = MagicMock()
        mock_settings.mongodb_url = "mongodb://localhost:27017"
        mock_get_settings.return_value = mock_settings
        client1 = get_mongodb_client()
        client2 = get_mongodb_client()
        assert client1 is client2
        assert mock_client_class.call_count == 1


def test_close_resets_singleton():
    with patch("app.auth.mongodb.MongoClient") as mock_client_class, \
         patch("app.auth.mongodb.get_settings") as mock_get_settings:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_settings = MagicMock()
        mock_settings.mongodb_url = "mongodb://localhost:27017"
        mock_get_settings.return_value = mock_settings
        get_mongodb_client()
        close_mongodb_connection()
        # After close, new call should create a new client
        get_mongodb_client()
        assert mock_client_class.call_count == 2

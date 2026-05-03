import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.models import HistoryTurn


class MemoryStore(ABC):
    @abstractmethod
    def save(self, session_id: str, message: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def load(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def add_turn(
        self,
        *,
        account_id: str,
        session_id: str,
        user_input: str,
        system_response: str,
        mode_used: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        pass

    @abstractmethod
    def list_turns(self, account_id: str, session_id: str, limit: int = 50) -> list[HistoryTurn]:
        pass

    @abstractmethod
    def delete_turns_for_session(self, account_id: str, session_id: str) -> int:
        pass

    @abstractmethod
    def list_sessions_for_account(self, account_id: str) -> list[dict[str, Any]]:
        pass

    def recent_messages(
        self, account_id: str, session_id: str, limit: int = 6
    ) -> list[dict[str, str]]:
        turns = self.list_turns(account_id, session_id, limit=limit)
        messages: list[dict[str, str]] = []
        for turn in turns:
            messages.append({"role": "user", "content": turn.user_input})
            messages.append({"role": "assistant", "content": turn.system_response})
        return messages


class SQLiteMemoryStore(MemoryStore):
    _LEGACY_ACCOUNT = "legacy"

    def __init__(self, sqlite_path: Path):
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(sqlite_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    system_response TEXT NOT NULL,
                    mode_used TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turns_session_created
                ON conversation_turns(session_id, created_at)
                """
            )
        self._migrate_account_id_column()

    def _migrate_account_id_column(self) -> None:
        with self._lock:
            info = self._connection.execute("PRAGMA table_info(conversation_turns)").fetchall()
            columns = {row[1] for row in info}
            if "account_id" in columns:
                return
            self._connection.execute(
                """
                ALTER TABLE conversation_turns
                ADD COLUMN account_id TEXT NOT NULL DEFAULT 'legacy'
                """
            )
            self._connection.execute(
                f"""
                UPDATE conversation_turns
                SET account_id = '{self._LEGACY_ACCOUNT}'
                WHERE account_id IS NULL OR account_id = ''
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turns_account_session
                ON conversation_turns(account_id, session_id, created_at)
                """
            )

    def save(self, session_id: str, message: dict[str, Any]) -> None:
        metadata = dict(message.get("metadata") or {})
        self.add_turn(
            account_id=str(message.get("account_id") or self._LEGACY_ACCOUNT),
            session_id=session_id,
            user_input=str(message.get("user_input") or message.get("input") or ""),
            system_response=str(
                message.get("system_response") or message.get("response") or ""
            ),
            mode_used=str(message.get("mode_used") or message.get("role") or "message"),
            request_id=str(message.get("request_id") or "manual"),
            metadata=metadata,
        )

    def load(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [
            turn.model_dump()
            for turn in self.list_turns(self._LEGACY_ACCOUNT, session_id, limit=limit)
        ]

    def add_turn(
        self,
        *,
        account_id: str,
        session_id: str,
        user_input: str,
        system_response: str,
        mode_used: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO conversation_turns (
                    account_id, session_id, user_input, system_response,
                    mode_used, request_id, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    session_id,
                    user_input,
                    system_response,
                    mode_used,
                    request_id,
                    json.dumps(metadata),
                ),
            )

    def list_turns(self, account_id: str, session_id: str, limit: int = 50) -> list[HistoryTurn]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM conversation_turns
                WHERE account_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (account_id, session_id, limit),
            ).fetchall()

        turns = []
        for row in reversed(rows):
            turns.append(
                HistoryTurn(
                    id=row["id"],
                    session_id=row["session_id"],
                    user_input=row["user_input"],
                    system_response=row["system_response"],
                    mode_used=row["mode_used"],
                    request_id=row["request_id"],
                    created_at=row["created_at"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                )
            )
        return turns

    def delete_turns_for_session(self, account_id: str, session_id: str) -> int:
        with self._lock, self._connection:
            cur = self._connection.execute(
                """
                DELETE FROM conversation_turns
                WHERE account_id = ? AND session_id = ?
                """,
                (account_id, session_id),
            )
            return cur.rowcount

    def list_sessions_for_account(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                  t.session_id,
                  COUNT(*) AS turn_count,
                  MAX(t.created_at) AS last_active_at,
                  (
                    SELECT user_input FROM conversation_turns x
                    WHERE x.account_id = t.account_id AND x.session_id = t.session_id
                    ORDER BY x.id DESC LIMIT 1
                  ) AS last_query_preview,
                  (
                    SELECT mode_used FROM conversation_turns x
                    WHERE x.account_id = t.account_id AND x.session_id = t.session_id
                    ORDER BY x.id DESC LIMIT 1
                  ) AS last_mode
                FROM conversation_turns t
                WHERE t.account_id = ?
                GROUP BY t.session_id
                ORDER BY last_active_at DESC
                """,
                (account_id,),
            ).fetchall()
        return [
            {
                "session_id": row["session_id"],
                "turn_count": int(row["turn_count"]),
                "last_active_at": str(row["last_active_at"] or ""),
                "last_query_preview": str(row["last_query_preview"] or "")[:200],
                "mode": row["last_mode"],
            }
            for row in rows
        ]


class PostgresMemoryStore(MemoryStore):
    _LEGACY_ACCOUNT = "legacy"

    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required when STORAGE_BACKEND=postgres or ENV=prod."
            ) from exc

        self._lock = threading.Lock()
        self._connection = psycopg.connect(dsn, row_factory=dict_row)
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    system_response TEXT NOT NULL,
                    mode_used TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    metadata_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turns_session_created
                ON conversation_turns(session_id, created_at)
                """
            )
        self._migrate_account_id_column()

    def _migrate_account_id_column(self) -> None:
        with self._connection.transaction():
            row = self._connection.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'conversation_turns' AND column_name = 'account_id'
                """
            ).fetchone()
            if row:
                return
            self._connection.execute(
                """
                ALTER TABLE conversation_turns
                ADD COLUMN account_id TEXT NOT NULL DEFAULT 'legacy'
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turns_account_session
                ON conversation_turns(account_id, session_id, created_at)
                """
            )

    def save(self, session_id: str, message: dict[str, Any]) -> None:
        metadata = dict(message.get("metadata") or {})
        self.add_turn(
            account_id=str(message.get("account_id") or self._LEGACY_ACCOUNT),
            session_id=session_id,
            user_input=str(message.get("user_input") or message.get("input") or ""),
            system_response=str(
                message.get("system_response") or message.get("response") or ""
            ),
            mode_used=str(message.get("mode_used") or message.get("role") or "message"),
            request_id=str(message.get("request_id") or "manual"),
            metadata=metadata,
        )

    def load(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [
            turn.model_dump()
            for turn in self.list_turns(self._LEGACY_ACCOUNT, session_id, limit=limit)
        ]

    def add_turn(
        self,
        *,
        account_id: str,
        session_id: str,
        user_input: str,
        system_response: str,
        mode_used: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO conversation_turns (
                    account_id, session_id, user_input, system_response,
                    mode_used, request_id, metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    account_id,
                    session_id,
                    user_input,
                    system_response,
                    mode_used,
                    request_id,
                    json.dumps(metadata),
                ),
            )

    def list_turns(self, account_id: str, session_id: str, limit: int = 50) -> list[HistoryTurn]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM conversation_turns
                WHERE account_id = %s AND session_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (account_id, session_id, limit),
            ).fetchall()

        turns = []
        for row in reversed(rows):
            metadata = row.get("metadata_json") or {}
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            created_at = row["created_at"]
            turns.append(
                HistoryTurn(
                    id=row["id"],
                    session_id=row["session_id"],
                    user_input=row["user_input"],
                    system_response=row["system_response"],
                    mode_used=row["mode_used"],
                    request_id=row["request_id"],
                    created_at=(
                        created_at.isoformat()
                        if hasattr(created_at, "isoformat")
                        else str(created_at)
                    ),
                    metadata=metadata,
                )
            )
        return turns

    def delete_turns_for_session(self, account_id: str, session_id: str) -> int:
        with self._lock, self._connection.transaction():
            cur = self._connection.execute(
                """
                DELETE FROM conversation_turns
                WHERE account_id = %s AND session_id = %s
                """,
                (account_id, session_id),
            )
            return cur.rowcount

    def list_sessions_for_account(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                  t.session_id,
                  COUNT(*)::INT AS turn_count,
                  MAX(t.created_at) AS last_active_at,
                  (
                    SELECT user_input FROM conversation_turns x
                    WHERE x.account_id = t.account_id AND x.session_id = t.session_id
                    ORDER BY x.id DESC LIMIT 1
                  ) AS last_query_preview,
                  (
                    SELECT mode_used FROM conversation_turns x
                    WHERE x.account_id = t.account_id AND x.session_id = t.session_id
                    ORDER BY x.id DESC LIMIT 1
                  ) AS last_mode
                FROM conversation_turns t
                WHERE t.account_id = %s
                GROUP BY t.account_id, t.session_id
                ORDER BY MAX(t.created_at) DESC
                """,
                (account_id,),
            ).fetchall()
        return [
            {
                "session_id": row["session_id"],
                "turn_count": int(row["turn_count"]),
                "last_active_at": (
                    row["last_active_at"].isoformat()
                    if hasattr(row["last_active_at"], "isoformat")
                    else str(row["last_active_at"] or "")
                ),
                "last_query_preview": str(row["last_query_preview"] or "")[:200],
                "mode": row["last_mode"],
            }
            for row in rows
        ]


def build_memory_store(settings: Any) -> MemoryStore:
    backend = (settings.storage_backend or "").lower()
    if not backend:
        backend = "postgres" if settings.environment.lower() == "prod" else "sqlite"

    if backend == "postgres":
        if not settings.postgres_dsn:
            raise RuntimeError("POSTGRES_DSN is required for the PostgreSQL memory store.")
        return PostgresMemoryStore(settings.postgres_dsn)

    return SQLiteMemoryStore(settings.sqlite_path)

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import init_engine
from app.db_models import Message, Session as UserSession
from app.models import HistoryTurn


class MemoryStore(ABC):
    @abstractmethod
    def create_session(self, user_id: str) -> str:
        pass

    @abstractmethod
    def get_session(self, user_id: str, session_id: str) -> bool:
        pass

    @abstractmethod
    def ensure_session(self, user_id: str, session_id: str) -> None:
        pass

    @abstractmethod
    def save(self, user_id: str, session_id: str, message: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def load(self, user_id: str, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def add_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        user_input: str,
        system_response: str,
        mode_used: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        pass

    @abstractmethod
    def list_turns(
        self,
        user_id: str,
        session_id: str,
        limit: int = 50,
    ) -> list[HistoryTurn]:
        pass

    def recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int = 6,
    ) -> list[dict[str, str]]:
        turns = self.list_turns(user_id, session_id, limit=limit)
        messages: list[dict[str, str]] = []
        for turn in turns:
            messages.append({"role": "user", "content": turn.user_input})
            messages.append({"role": "assistant", "content": turn.system_response})
        return messages


class DatabaseMemoryStore(MemoryStore):
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def _ensure_engine(self) -> None:
        init_engine()

    def create_session(self, user_id: str) -> str:
        self._ensure_engine()
        session_id = str(uuid.uuid4())
        with self._session_factory() as db:
            db.add(UserSession(id=session_id, user_id=user_id))
            db.commit()
        return session_id

    def get_session(self, user_id: str, session_id: str) -> bool:
        self._ensure_engine()
        with self._session_factory() as db:
            result = db.execute(
                select(UserSession.id).where(
                    UserSession.id == session_id,
                    UserSession.user_id == user_id,
                )
            ).first()
        return bool(result)

    def ensure_session(self, user_id: str, session_id: str) -> None:
        if not self.get_session(user_id, session_id):
            raise ValueError("Session not found")

    def save(self, user_id: str, session_id: str, message: dict[str, Any]) -> None:
        self._ensure_engine()
        self.add_turn(
            user_id=user_id,
            session_id=session_id,
            user_input=str(message.get("user_input") or message.get("input") or ""),
            system_response=str(
                message.get("system_response") or message.get("response") or ""
            ),
            mode_used=str(message.get("mode_used") or message.get("role") or "message"),
            request_id=str(message.get("request_id") or "manual"),
            metadata=dict(message.get("metadata") or {}),
        )

    def load(self, user_id: str, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        self._ensure_engine()
        return [turn.model_dump() for turn in self.list_turns(user_id, session_id, limit=limit)]

    def add_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        user_input: str,
        system_response: str,
        mode_used: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        self._ensure_engine()
        with self._session_factory() as db:
            db.add(
                Message(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=user_input,
                    mode_used="user",
                    request_id=request_id,
                    metadata_json="{}",
                )
            )
            db.add(
                Message(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=system_response,
                    mode_used=mode_used,
                    request_id=request_id,
                    metadata_json=json.dumps(metadata),
                )
            )
            db.commit()

    def list_turns(
        self,
        user_id: str,
        session_id: str,
        limit: int = 50,
    ) -> list[HistoryTurn]:
        self._ensure_engine()
        with self._session_factory() as db:
            messages = (
                db.execute(
                    select(Message)
                    .where(
                        Message.user_id == user_id,
                        Message.session_id == session_id,
                    )
                    .order_by(Message.created_at.asc())
                )
                .scalars()
                .all()
            )

        turns: list[HistoryTurn] = []
        pending_user: Message | None = None
        for message in messages:
            if message.role == "user":
                pending_user = message
                continue
            if message.role == "assistant" and pending_user:
                try:
                    metadata = json.loads(message.metadata_json or "{}")
                except (ValueError, TypeError):
                    metadata = {}
                created_at = message.created_at
                turns.append(
                    HistoryTurn(
                        id=str(message.id),
                        session_id=str(message.session_id),
                        user_input=pending_user.content,
                        system_response=message.content,
                        mode_used=message.mode_used or "assistant",
                        request_id=message.request_id or "",
                        created_at=(
                            created_at.isoformat()
                            if hasattr(created_at, "isoformat")
                            else str(created_at)
                        ),
                        metadata=metadata,
                    )
                )
                pending_user = None

        if limit and len(turns) > limit:
            return turns[-limit:]
        return turns


class InMemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._sessions: set[tuple[str, str]] = set()
        self._turns: list[HistoryTurn] = []

    def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        self._sessions.add((user_id, session_id))
        return session_id

    def get_session(self, user_id: str, session_id: str) -> bool:
        return (user_id, session_id) in self._sessions

    def ensure_session(self, user_id: str, session_id: str) -> None:
        if not self.get_session(user_id, session_id):
            raise ValueError("Session not found")

    def save(self, user_id: str, session_id: str, message: dict[str, Any]) -> None:
        self.add_turn(
            user_id=user_id,
            session_id=session_id,
            user_input=str(message.get("user_input") or message.get("input") or ""),
            system_response=str(
                message.get("system_response") or message.get("response") or ""
            ),
            mode_used=str(message.get("mode_used") or message.get("role") or "message"),
            request_id=str(message.get("request_id") or "manual"),
            metadata=dict(message.get("metadata") or {}),
        )

    def load(self, user_id: str, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [turn.model_dump() for turn in self.list_turns(user_id, session_id, limit=limit)]

    def add_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        user_input: str,
        system_response: str,
        mode_used: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        self._sessions.add((user_id, session_id))
        turn_id = str(uuid.uuid4())
        self._turns.append(
            HistoryTurn(
                id=turn_id,
                session_id=session_id,
                user_input=user_input,
                system_response=system_response,
                mode_used=mode_used,
                request_id=request_id,
                created_at="",
                metadata=metadata,
            )
        )

    def list_turns(
        self,
        user_id: str,
        session_id: str,
        limit: int = 50,
    ) -> list[HistoryTurn]:
        turns = [turn for turn in self._turns if turn.session_id == session_id]
        if limit and len(turns) > limit:
            return turns[-limit:]
        return turns


def build_memory_store(session_factory: Callable[[], Session]) -> MemoryStore:
    return DatabaseMemoryStore(session_factory)

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import declarative_base

from app.db import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Text, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(Text, ForeignKey("sessions.id"), nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    mode_used = Column(Text, nullable=True)
    request_id = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

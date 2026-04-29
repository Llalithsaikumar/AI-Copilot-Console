from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import Settings, get_settings


Base = declarative_base()
_engine = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False)


def _build_engine(settings: Settings):
    db_path = settings.sqlite_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


def init_engine(settings: Settings | None = None):
    global _engine
    if _engine is None:
        from app import db_models  # noqa: F401
        _engine = _build_engine(settings or get_settings())
        SessionLocal.configure(bind=_engine)
        Base.metadata.create_all(bind=_engine)
    return _engine


def init_db() -> None:
    init_engine()


def get_db() -> Generator:
    init_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///isel_room.db')

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    from isel.db.models import User, AuditLog, Session, PointAdjustment  # noqa: F401
    Base.metadata.create_all(engine)

from __future__ import annotations
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///isel_room.db')

# check_same_thread is a SQLite-only argument — passing it to any other driver
# (e.g. the mysql+pymysql:// URL the README documents) raises on connect.
_connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    from isel.db.models import User, AuditLog, LabSession  # noqa: F401
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    """Yield a SQLAlchemy session, commit on success, rollback + re-raise on error.

    Replaces the SessionLocal/try/commit/except/rollback/finally/close pattern
    that used to be hand-rolled in every service function. For read-only
    callers the commit is a harmless no-op.

    Callers that want to translate an exception into a structured response
    (e.g. {'success': False, 'message': str(e)}) should wrap the `with`
    block in their own try/except — session cleanup is still guaranteed.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

"""Shared pytest fixtures for the isel_room test suite."""
from __future__ import annotations
import os

# Set before any project modules are imported so isel.db picks up the right URL.
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('ADMIN_PIN', 'test-pin')
os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret')

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import isel.db as _db

# Replace the module-level engine with a StaticPool in-memory engine so all
# sessions share the same in-memory database (SQLite creates a new DB per
# connection without StaticPool).
_test_engine = create_engine(
    'sqlite:///:memory:',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
_db.engine = _test_engine
_db.SessionLocal = sessionmaker(bind=_test_engine, autoflush=False, autocommit=False)

# Import models to register them with Base, then create tables.
from isel.db.models import Base, User, Session as LabSession, AuditLog  # noqa
Base.metadata.create_all(_test_engine)

from app import create_app


@pytest.fixture(scope='session')
def app():
    return create_app('test')


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session():
    session = _db.SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _clean_db():
    """Delete all rows between tests to keep isolation."""
    yield
    with _test_engine.connect() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())
        conn.commit()


@pytest.fixture()
def admin_client(client):
    client.post('/api/admin/login', json={'pin': 'test-pin'})
    return client

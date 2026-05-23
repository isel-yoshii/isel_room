"""Audit log service — single entry point for writing and reading audit entries."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, or_
from isel.db import SessionLocal
from isel.db.models import AuditLog


def record(
    action_type: str,
    target_user_id: int,
    target_name: str,
    performed_by: str = 'admin',
) -> None:
    session = SessionLocal()
    try:
        log = AuditLog(
            action_type=action_type,
            target_user_id=target_user_id,
            target_name=target_name,
            performed_by=performed_by,
            timestamp=datetime.now(),
        )
        session.add(log)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def recent_entries(
    limit: int = 200,
    user_id: int | None = None,
    user_ids: list[int] | None = None,
    action_types: list[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    q: str | None = None,
) -> list[dict]:
    session = SessionLocal()
    try:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        if user_id is not None:
            stmt = stmt.where(AuditLog.target_user_id == user_id)
        if user_ids:
            stmt = stmt.where(AuditLog.target_user_id.in_(user_ids))
        if action_types:
            stmt = stmt.where(AuditLog.action_type.in_(action_types))
        if start is not None:
            stmt = stmt.where(AuditLog.timestamp >= start)
        if end is not None:
            stmt = stmt.where(AuditLog.timestamp <= end)
        if q:
            like = f'%{q}%'
            stmt = stmt.where(or_(AuditLog.target_name.ilike(like), AuditLog.action_type.ilike(like)))
        rows = session.execute(stmt).scalars().all()
        return [
            {
                'action': r.action_type,
                'user_id': r.target_user_id,
                'name': r.target_name,
                'performed_by': r.performed_by,
                'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M'),
            }
            for r in rows
        ]
    finally:
        session.close()

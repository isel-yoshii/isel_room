"""Audit log service — single entry point for writing and reading audit entries."""
from __future__ import annotations
from datetime import datetime
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


def recent_entries(limit: int = 200) -> list[dict]:
    from sqlalchemy import select
    session = SessionLocal()
    try:
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
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

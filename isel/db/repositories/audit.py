from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from isel.db.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: DbSession) -> None:
        self.session = session

    def add(self, log: AuditLog) -> None:
        self.session.add(log)

    def get_recent(self, limit: int = 200) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

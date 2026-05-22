from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from isel.db.models import Session as LabSession


class SessionRepository:
    def __init__(self, session: DbSession) -> None:
        self.session = session

    def get_by_id(self, session_id: int) -> LabSession | None:
        return self.session.get(LabSession, session_id)

    def get_open_for_user(self, user_id: int) -> LabSession | None:
        stmt = (
            select(LabSession)
            .where(LabSession.user_id == user_id, LabSession.checked_out_at.is_(None))
            .order_by(LabSession.checked_in_at.desc())
        )
        return self.session.execute(stmt).scalars().first()

    def add(self, lab_session: LabSession) -> None:
        self.session.add(lab_session)

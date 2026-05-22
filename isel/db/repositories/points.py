from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session as DbSession
from isel.db.models import PointAdjustment


class PointAdjustmentRepository:
    def __init__(self, session: DbSession) -> None:
        self.session = session

    def add(self, adjustment: PointAdjustment) -> None:
        self.session.add(adjustment)

    def get_totals_by_user(self) -> dict[int, int]:
        stmt = (
            select(PointAdjustment.user_id, func.sum(PointAdjustment.delta).label('bonus'))
            .group_by(PointAdjustment.user_id)
        )
        rows = self.session.execute(stmt).all()
        return {r.user_id: (r.bonus or 0) for r in rows}

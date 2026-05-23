"""Points service — leaderboards and manual adjustments.

A user earns 1 point per calendar day on which they had at least one
completed session (both check_in and check_out present), plus the sum
of all point_adjustments.delta for that user (within month for monthly,
all-time for total).
"""
from __future__ import annotations
import calendar
from datetime import datetime
from sqlalchemy import select, func
from isel.db import SessionLocal
from isel.db.models import User, Session as LabSession, PointAdjustment


def monthly_leaderboard(year: int, month: int) -> list[dict]:
    session = SessionLocal()
    try:
        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59)

        rows = session.execute(
            select(
                User.user_id,
                User.name,
                User.user_type,
                func.count(func.distinct(func.date(LabSession.checked_in_at))).label('points'),
            )
            .join(LabSession, LabSession.user_id == User.user_id)
            .where(
                LabSession.checked_in_at >= start,
                LabSession.checked_in_at <= end,
            )
            .group_by(User.user_id)
        ).all()

        bonus_rows = session.execute(
            select(PointAdjustment.user_id, func.sum(PointAdjustment.delta))
            .where(PointAdjustment.timestamp >= start, PointAdjustment.timestamp <= end)
            .group_by(PointAdjustment.user_id)
        ).all()
        bonus_by_user = {uid: int(total or 0) for uid, total in bonus_rows}

        result = [
            {
                'id': r.user_id,
                'name': r.name,
                'type': r.user_type,
                'points': r.points + bonus_by_user.get(r.user_id, 0),
            }
            for r in rows
        ]
        result.sort(key=lambda x: x['points'], reverse=True)
        return result
    finally:
        session.close()


def all_time_leaderboard() -> list[dict]:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                User.user_id,
                User.name,
                User.user_type,
                func.count(func.distinct(func.date(LabSession.checked_in_at))).label('points'),
            )
            .join(LabSession, LabSession.user_id == User.user_id)
            .group_by(User.user_id)
        ).all()

        bonus_rows = session.execute(
            select(PointAdjustment.user_id, func.sum(PointAdjustment.delta))
            .group_by(PointAdjustment.user_id)
        ).all()
        bonus_by_user = {uid: int(total or 0) for uid, total in bonus_rows}

        result = [
            {
                'id': r.user_id,
                'name': r.name,
                'type': r.user_type,
                'points': r.points + bonus_by_user.get(r.user_id, 0),
            }
            for r in rows
        ]
        result.sort(key=lambda x: x['points'], reverse=True)
        return result
    finally:
        session.close()


def adjust_points(user_id: int, delta: int, note: str = '', performed_by: str = 'admin') -> bool:
    session = SessionLocal()
    try:
        adj = PointAdjustment(
            user_id=user_id,
            delta=int(delta),
            note=note,
            performed_by=performed_by,
            timestamp=datetime.now(),
        )
        session.add(adj)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()

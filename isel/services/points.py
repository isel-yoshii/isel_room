"""Points service — leaderboards.

A user earns 1 point per calendar day on which they had at least one
check-in. Score is purely days-present — no manual overrides.
"""
from __future__ import annotations
import calendar
from datetime import datetime
from sqlalchemy import select, func
from isel.db import SessionLocal
from isel.db.models import User, Session as LabSession


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

        result = [
            {
                'id': r.user_id,
                'name': r.name,
                'type': r.user_type,
                'points': r.points,
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

        result = [
            {
                'id': r.user_id,
                'name': r.name,
                'type': r.user_type,
                'points': r.points,
            }
            for r in rows
        ]
        result.sort(key=lambda x: x['points'], reverse=True)
        return result
    finally:
        session.close()

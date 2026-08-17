"""Points service — leaderboards.

A user earns 1 point per calendar day on which they had at least one
check-in. Score is purely days-present — no manual overrides.

The all-time leaderboard resets every April 1 (Japanese academic year):
each AY runs from April 1 (inclusive) to April 1 of the next year (exclusive).
"""
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import select, func
from isel.db import session_scope
from isel.db.models import User, Session as LabSession
from isel.utils import month_range


def current_academic_year(today: date | None = None) -> int:
    """Return the academic year (Apr 1 → Mar 31) containing the given date.

    AY YYYY runs from `YYYY-04-01` to `(YYYY+1)-04-01` (exclusive).
    """
    t = today or date.today()
    return t.year if t.month >= 4 else t.year - 1


def monthly_leaderboard(year: int, month: int) -> list[dict]:
    with session_scope() as session:
        start, end = month_range(year, month)

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
                LabSession.checked_in_at < end,
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


def academic_year_leaderboard(ay_year: int) -> list[dict]:
    """Distinct days-present per user within academic year `ay_year`.

    Window is [Apr 1 ay_year, Apr 1 ay_year+1) exclusive on the upper bound.
    """
    with session_scope() as session:
        start = datetime(ay_year, 4, 1)
        end   = datetime(ay_year + 1, 4, 1)
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
                LabSession.checked_in_at < end,
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

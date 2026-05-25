"""Tests for points leaderboard and manual adjustments."""
from __future__ import annotations
from datetime import datetime, timedelta

from isel.db.models import User, Session as LabSession
import isel.services.points as points


def _make_user(db_session, name='User', user_type='B4') -> User:
    user = User(name=name, user_type=user_type, status=False, embedding=None)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _completed_session(user_id: int, day_offset: int = 0) -> LabSession:
    base = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    cin  = base - timedelta(days=day_offset)
    cout = cin + timedelta(hours=2)
    return LabSession(user_id=user_id, checked_in_at=cin, checked_out_at=cout, check_in_method='face')


def test_days_present_counted_per_calendar_day(db_session):
    user = _make_user(db_session)
    now = datetime.now()

    # Two sessions on the same day → only 1 point.
    s1 = LabSession(
        user_id=user.user_id,
        checked_in_at=now.replace(hour=9),
        checked_out_at=now.replace(hour=11),
        check_in_method='face',
    )
    s2 = LabSession(
        user_id=user.user_id,
        checked_in_at=now.replace(hour=14),
        checked_out_at=now.replace(hour=16),
        check_in_method='face',
    )
    db_session.add_all([s1, s2])
    db_session.commit()

    board = points.monthly_leaderboard(now.year, now.month)
    assert len(board) == 1
    assert board[0]['points'] == 1


def test_sessions_on_different_days_each_count(db_session):
    user = _make_user(db_session)
    ay = points.current_academic_year()
    # Two April-of-current-AY sessions on consecutive days (always in current AY).
    d1 = datetime(ay, 4, 10, 10, 0)
    d2 = datetime(ay, 4, 11, 10, 0)
    db_session.add_all([
        LabSession(user_id=user.user_id, checked_in_at=d1,
                   checked_out_at=d1 + timedelta(hours=2), check_in_method='face'),
        LabSession(user_id=user.user_id, checked_in_at=d2,
                   checked_out_at=d2 + timedelta(hours=2), check_in_method='face'),
    ])
    db_session.commit()

    board = points.academic_year_leaderboard(ay)
    assert board[0]['points'] == 2


def test_monthly_vs_academic_year(db_session):
    user = _make_user(db_session)
    ay = points.current_academic_year()
    d_apr = datetime(ay, 4, 10, 10, 0)
    d_jun = datetime(ay, 6, 10, 10, 0)
    db_session.add_all([
        LabSession(user_id=user.user_id, checked_in_at=d_apr,
                   checked_out_at=d_apr + timedelta(hours=2), check_in_method='face'),
        LabSession(user_id=user.user_id, checked_in_at=d_jun,
                   checked_out_at=d_jun + timedelta(hours=2), check_in_method='face'),
    ])
    db_session.commit()

    apr_only = points.monthly_leaderboard(ay, 4)
    year     = points.academic_year_leaderboard(ay)

    assert apr_only[0]['points'] == 1
    assert year[0]['points'] == 2


def test_academic_year_boundary(db_session):
    user = _make_user(db_session)
    # Mar 31 belongs to previous AY; Apr 1 to the new AY.
    d_mar = datetime(2025, 3, 31, 10, 0)
    d_apr = datetime(2025, 4, 1,  10, 0)
    db_session.add_all([
        LabSession(user_id=user.user_id, checked_in_at=d_mar,
                   checked_out_at=d_mar + timedelta(hours=2), check_in_method='face'),
        LabSession(user_id=user.user_id, checked_in_at=d_apr,
                   checked_out_at=d_apr + timedelta(hours=2), check_in_method='face'),
    ])
    db_session.commit()

    assert points.academic_year_leaderboard(2024)[0]['points'] == 1  # Mar 31 → AY 2024
    assert points.academic_year_leaderboard(2025)[0]['points'] == 1  # Apr 1  → AY 2025

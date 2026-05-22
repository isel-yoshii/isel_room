"""Tests for points leaderboard and manual adjustments."""
from __future__ import annotations
from datetime import datetime, timedelta

from isel.db.models import User, Session as LabSession, PointAdjustment
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
    now  = datetime.now()

    s1 = _completed_session(user.user_id, day_offset=0)
    s2 = _completed_session(user.user_id, day_offset=1)
    db_session.add_all([s1, s2])
    db_session.commit()

    board = points.all_time_leaderboard()
    assert board[0]['points'] == 2


def test_point_adjustment_added_to_score(db_session):
    user = _make_user(db_session)
    now  = datetime.now()
    db_session.add(_completed_session(user.user_id))
    adj = PointAdjustment(
        user_id=user.user_id, delta=3, note='bonus',
        performed_by='admin', timestamp=now,
    )
    db_session.add(adj)
    db_session.commit()

    board = points.monthly_leaderboard(now.year, now.month)
    assert board[0]['points'] == 4  # 1 day + 3 bonus


def test_monthly_vs_alltime(db_session):
    user = _make_user(db_session)
    now  = datetime.now()

    # Session this month.
    db_session.add(_completed_session(user.user_id, day_offset=0))
    # Session last month (> 31 days ago).
    old = _completed_session(user.user_id, day_offset=40)
    db_session.add(old)
    db_session.commit()

    monthly = points.monthly_leaderboard(now.year, now.month)
    alltime = points.all_time_leaderboard()

    assert monthly[0]['points'] == 1
    assert alltime[0]['points'] == 2

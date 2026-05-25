"""Tests for attendance toggle and stale-session safeguard."""
from __future__ import annotations
from datetime import datetime, timedelta

import isel.db as _db
from isel.db.models import User, Session as LabSession, AuditLog
import isel.services.attendance as attendance


def _make_user(db_session, name='Test User', user_type='B4') -> int:
    user = User(name=name, user_type=user_type, status=False, embedding=None)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user.user_id


def test_toggle_checkin_creates_session(db_session):
    uid = _make_user(db_session)

    result = attendance.toggle_entry(uid, check_in_method='face')

    assert result['event_type'] == 'IN'
    sess = db_session.query(LabSession).filter_by(user_id=uid).first()
    assert sess is not None
    assert sess.checked_out_at is None
    assert sess.check_in_method == 'face'


def test_toggle_checkout_closes_session(db_session):
    uid = _make_user(db_session)
    attendance.toggle_entry(uid, check_in_method='face')

    result = attendance.toggle_entry(uid, check_in_method='face')

    assert result['event_type'] == 'OUT'
    sess = db_session.query(LabSession).filter_by(user_id=uid).first()
    assert sess.checked_out_at is not None


def test_stale_session_closed_on_new_checkin(db_session):
    uid = _make_user(db_session)
    stale_in = datetime.now() - timedelta(hours=25)
    stale = LabSession(
        user_id=uid,
        checked_in_at=stale_in,
        check_in_method='face',
    )
    db_session.add(stale)
    db_session.commit()

    result = attendance.toggle_entry(uid, check_in_method='face')

    assert result['event_type'] == 'IN'
    # Stale session should be closed.
    db_session.expire_all()
    stale_row = db_session.get(LabSession, stale.id)
    assert stale_row.checked_out_at is not None
    # Audit log should record the stale close.
    audit = db_session.query(AuditLog).filter_by(action_type='STALE_SESSION_CLOSED').first()
    assert audit is not None



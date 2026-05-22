"""Tests for user registration, deletion, and grade promotion."""
from __future__ import annotations
from unittest.mock import MagicMock
from datetime import datetime

from sqlalchemy import select

from isel.db.models import User, Session as LabSession, AuditLog
import isel.services.users as users


def _mock_engine():
    engine = MagicMock()
    engine.reg_threshold = 0.5
    engine.extract_embedding.return_value = [0.1] * 10
    engine.find_match.return_value = (None, None, None)  # no duplicate
    return engine


def test_registration_writes_audit_log(admin_client, app, db_session):
    app.config['FACE_ENGINE'] = _mock_engine()

    resp = admin_client.post('/api/register', json={
        'name': 'Alice', 'user_type': 'B4',
        'image': 'data:image/jpeg;base64,/9j/AA==',
    })
    assert resp.get_json()['success'] is True

    audit = db_session.query(AuditLog).filter_by(action_type='REGISTER').first()
    assert audit is not None
    assert audit.target_name == 'Alice'


def test_deletion_removes_user(db_session):
    user = User(name='Bob', user_type='M1', status=False, embedding=None)
    db_session.add(user)
    db_session.commit()
    uid = user.user_id

    users.delete_user(uid)

    result = db_session.execute(select(User).where(User.user_id == uid)).scalar_one_or_none()
    assert result is None


def test_promotion_advances_all_grades(db_session):
    for name, grade in [('Carol', 'B4'), ('Dave', 'M1'), ('Eve', 'M2')]:
        db_session.add(User(name=name, user_type=grade, status=False, embedding=None))
    db_session.commit()

    counts = users.promote_students()

    assert counts['B4'] == 1
    assert counts['M1'] == 1
    assert counts['M2'] == 1

    db_session.expire_all()
    def grade_of(name):
        return db_session.query(User).filter_by(name=name).first().user_type

    assert grade_of('Carol') == 'M1'
    assert grade_of('Dave')  == 'M2'
    assert grade_of('Eve')   == '卒業'

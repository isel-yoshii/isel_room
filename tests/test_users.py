from __future__ import annotations
from unittest.mock import MagicMock
from datetime import datetime

from sqlalchemy import select

from backend.db.models import User, LabSession, AuditLog
import backend.services.users as users


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
        'variants': {'normal': ['data:image/jpeg;base64,/9j/AA==']},
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


def test_promotion_applies_explicit_targets(db_session):
    carol = User(name='Carol', user_type='B4',  status=False, embedding=None)
    dave  = User(name='Dave',  user_type='M1',  status=False, embedding=None)
    eve   = User(name='Eve',   user_type='M2',  status=False, embedding=None)
    finn  = User(name='Finn',  user_type='PhD', status=False, embedding=None)
    db_session.add_all([carol, dave, eve, finn])
    db_session.commit()

    counts = users.promote_students([
        {'user_id': carol.user_id, 'new_type': 'M1'},
        {'user_id': dave.user_id,  'new_type': 'M2'},
        {'user_id': eve.user_id,   'new_type': 'PhD'},   # branching: M2→PhD instead of 卒業
        {'user_id': finn.user_id,  'new_type': '卒業'},
    ])

    assert counts['B4→M1']   == 1
    assert counts['M1→M2']   == 1
    assert counts['M2→PhD']  == 1
    assert counts['PhD→卒業'] == 1

    db_session.expire_all()
    def grade_of(name):
        return db_session.query(User).filter_by(name=name).first().user_type

    assert grade_of('Carol') == 'M1'
    assert grade_of('Dave')  == 'M2'
    assert grade_of('Eve')   == 'PhD'
    assert grade_of('Finn')  == '卒業'


def test_promotion_skips_noops(db_session):
    user = User(name='Sam', user_type='M2', status=False, embedding=None)
    db_session.add(user)
    db_session.commit()

    counts = users.promote_students([
        {'user_id': user.user_id, 'new_type': 'M2'},  # same as current
    ])
    assert counts == {}

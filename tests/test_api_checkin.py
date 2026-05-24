"""API round-trip tests for /api/auth and /api/toggle with a mock face engine."""
from __future__ import annotations
from unittest.mock import MagicMock

from isel.db.models import User
import isel.db as _db


def _add_user(db_session, name='Test User', status=False) -> int:
    user = User(name=name, user_type='B4', status=status, embedding=[0.1] * 10)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user.user_id


def _mock_engine(matched=True, user_id=1, name='Test User', status=False, dist=0.2):
    engine = MagicMock()
    engine.auth_threshold = 0.5
    if matched:
        engine.extract_embedding.return_value = [0.1] * 10
        engine.find_best_match.return_value = (user_id, name, dist)
    else:
        engine.extract_embedding.return_value = None
    return engine


def test_auth_matched_single_image(client, app, db_session):
    """Legacy single-frame shape {image: ...} still works."""
    uid = _add_user(db_session, status=False)
    app.config['FACE_ENGINE'] = _mock_engine(matched=True, user_id=uid, name='Test User')

    resp = client.post('/api/auth', json={'image': 'data:image/jpeg;base64,/9j/AA=='})

    data = resp.get_json()
    assert data['matched'] is True
    assert data['user_id'] == uid
    assert data['name'] == 'Test User'
    assert data['status'] is False


def test_auth_matched_multi_frame_burst(client, app, db_session):
    """New burst shape {images: [...]} picks the best match across frames."""
    uid = _add_user(db_session, status=False)
    app.config['FACE_ENGINE'] = _mock_engine(matched=True, user_id=uid, name='Test User')

    resp = client.post('/api/auth', json={'images': [
        'data:image/jpeg;base64,/9j/AA==',
        'data:image/jpeg;base64,/9j/AB==',
        'data:image/jpeg;base64,/9j/AC==',
    ]})

    data = resp.get_json()
    assert data['matched'] is True
    assert data['user_id'] == uid


def test_auth_no_face_detected(client, app, db_session):
    app.config['FACE_ENGINE'] = _mock_engine(matched=False)

    resp = client.post('/api/auth', json={'image': 'data:image/jpeg;base64,/9j/AA=='})

    data = resp.get_json()
    assert data['matched'] is False


def test_toggle_checkin(client, db_session):
    uid = _add_user(db_session, status=False)

    resp = client.post('/api/toggle', json={'user_id': uid, 'check_in_method': 'manual'})

    data = resp.get_json()
    assert data['event_type'] == 'IN'
    assert data['name'] == 'Test User'


def test_toggle_checkout(client, db_session):
    uid = _add_user(db_session, status=True)

    resp = client.post('/api/toggle', json={'user_id': uid, 'check_in_method': 'manual'})

    data = resp.get_json()
    assert data['event_type'] == 'OUT'

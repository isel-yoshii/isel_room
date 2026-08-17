from __future__ import annotations
from unittest.mock import MagicMock

from backend.db.models import User
from backend.face_engine import FaceEngine
import backend.db as _db


def _add_user(db_session, name='Test User', status=False) -> int:
    user = User(
        name=name, user_type='B4', status=status,
        embedding={'normal': [[0.1] * 10]},
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user.user_id


def _mock_engine(matched=True, user_id=1, name='Test User', status=False, dist=0.2):
    """A real FaceEngine with only the DeepFace call stubbed, so that
    embeddings_from_frames stays under test. A MagicMock engine would return a
    truthy Mock from it and the no-face-detected branch would never run."""
    engine = FaceEngine(get_embeddings=lambda: {})
    engine.auth_threshold = 0.5
    engine.extract_embedding = MagicMock(return_value=[0.1] * 10 if matched else None)
    if matched:
        engine.find_best_match = MagicMock(return_value=(user_id, name, dist))
    return engine


def test_auth_matched_multi_frame_burst(client, app, db_session):
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
    assert data['name'] == 'Test User'
    assert data['status'] is False


def test_auth_no_face_detected(client, app, db_session):
    app.config['FACE_ENGINE'] = _mock_engine(matched=False)

    resp = client.post('/api/auth', json={'images': ['data:image/jpeg;base64,/9j/AA==']})

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

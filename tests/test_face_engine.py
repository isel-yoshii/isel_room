"""Tests for FaceEngine.find_match and find_best_match."""
from __future__ import annotations

from isel.db.models import User
from isel.face_engine import FaceEngine
import isel.services.users as users_svc


def test_find_match_picks_closest_across_multi_variants(db_session):
    """A live vector close to the user's second variant still matches."""
    user = User(
        name='Multi', user_type='M1', status=False,
        embedding={
            'normal':  [[1.0, 0.0, 0.0]],
            'glasses': [[0.0, 1.0, 0.0]],
        },
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    live_vec = [0.05, 0.99, 0.0]  # near the glasses variant
    uid, name, dist = engine.find_match(live_vec, 0.55)
    assert uid == user.user_id
    assert name == 'Multi'
    assert dist < 0.1


def test_find_match_with_variant_dict(db_session):
    """Match works when stored embedding is a {variant: [vec, ...]} dict."""
    user = User(
        name='Variants', user_type='M1', status=False,
        embedding={
            'normal':  [[1.0, 0.0, 0.0]],
            'glasses': [[0.0, 1.0, 0.0]],
        },
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    uid, name, _ = engine.find_match([0.0, 0.99, 0.0], 0.55)
    assert uid == user.user_id
    assert name == 'Variants'


def test_find_match_returns_none_when_no_variant_below_threshold(db_session):
    user = User(
        name='Far',
        user_type='M2',
        status=False,
        embedding={'normal': [[1.0, 0.0, 0.0]]},
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    # Orthogonal vector. Cosine distance ~ 1.0, far above 0.55.
    uid, name, _ = engine.find_match([0.0, 1.0, 0.0], 0.55)
    assert uid is None and name is None


def test_find_best_match_picks_closest_across_frames(db_session):
    """Given multiple input embeddings, return the user matched by the closest one."""
    user = User(
        name='Bursty', user_type='M1', status=False,
        embedding={'normal': [[1.0, 0.0, 0.0]]},
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    frames = [
        [0.0, 1.0, 0.0],     # far (orthogonal)
        [0.99, 0.05, 0.0],   # very close to stored
        [0.0, 0.0, 1.0],     # far
    ]
    uid, name, dist = engine.find_best_match(frames, 0.55)
    assert uid == user.user_id
    assert name == 'Bursty'
    assert dist < 0.1


def test_find_best_match_empty_list_returns_none():
    engine = FaceEngine(lambda: {}, auth_threshold=0.55)
    uid, name, dist = engine.find_best_match([], 0.55)
    assert uid is None and name is None and dist is None


def test_find_best_match_single_frame_matches_find_match(db_session):
    """Calling find_best_match with one embedding gives the same result as find_match."""
    user = User(
        name='Single', user_type='M1', status=False,
        embedding={'normal': [[1.0, 0.0, 0.0]]},
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    probe = [0.99, 0.05, 0.0]
    a = engine.find_match(probe, 0.55)
    b = engine.find_best_match([probe], 0.55)
    assert a == b


def test_find_best_match_skips_none_embeddings(db_session):
    """None entries in the frames list (e.g. detection failed on that frame) are skipped."""
    user = User(
        name='Skip', user_type='M1', status=False,
        embedding={'normal': [[1.0, 0.0, 0.0]]},
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    uid, _, _ = engine.find_best_match([None, [0.99, 0.05, 0.0], None], 0.55)
    assert uid == user.user_id

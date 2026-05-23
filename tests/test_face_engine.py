"""Tests for the multi-variant FaceEngine.find_match behaviour."""
from __future__ import annotations

from isel.db.models import User
from isel.face_engine import FaceEngine
import isel.services.users as users_svc


def test_find_match_picks_closest_across_multi_variants(db_session):
    """A live vector close to the user's second variant still matches."""
    variant_a = [1.0, 0.0, 0.0]
    variant_b = [0.0, 1.0, 0.0]  # imagine 'glasses on'
    user = User(
        name='Multi', user_type='M1', status=False,
        embedding=[variant_a, variant_b],
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    live_vec = [0.05, 0.99, 0.0]  # near variant_b
    uid, name, dist = engine.find_match(live_vec, 0.55)
    assert uid == user.user_id
    assert name == 'Multi'
    assert dist < 0.1


def test_find_match_handles_legacy_single_vector(db_session):
    """A user registered before multi-embedding (single flat vector) still matches."""
    legacy_vec = [1.0, 0.0, 0.0]
    user = User(
        name='Legacy', user_type='B4', status=False,
        embedding=legacy_vec,  # legacy single-vector shape
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    uid, _, _ = engine.find_match([0.99, 0.01, 0.0], 0.55)
    assert uid == user.user_id


def test_find_match_with_variant_dict(db_session):
    """Match works when stored embedding is a {variant: [vec, ...]} dict (new shape)."""
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
        embedding=[[1.0, 0.0, 0.0]],
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    # Orthogonal vector → cosine distance ≈ 1.0, far above 0.55
    uid, name, _ = engine.find_match([0.0, 1.0, 0.0], 0.55)
    assert uid is None and name is None

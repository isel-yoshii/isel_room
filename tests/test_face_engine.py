from __future__ import annotations

from backend.db.models import User
from backend.face_engine import FaceEngine
import backend.services.users as users_svc


def test_find_match_picks_closest_across_multi_variants(db_session):
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
    user = User(
        name='Skip', user_type='M1', status=False,
        embedding={'normal': [[1.0, 0.0, 0.0]]},
    )
    db_session.add(user)
    db_session.commit()

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    uid, _, _ = engine.find_best_match([None, [0.99, 0.05, 0.0], None], 0.55)
    assert uid == user.user_id


# Added while investigating "the kiosk always identifies the same person".

def _enrol(db_session, name, vectors, variant='normal'):
    user = User(name=name, user_type='M1', status=False,
                embedding={variant: vectors})
    db_session.add(user)
    db_session.commit()
    return user


def test_ranking_collapses_each_identity_to_one_entry(db_session):
    """One row per person, not per stored vector — otherwise the runner-up is
    usually the same person's second frame, and the ambiguity margin would
    reject every scan instead of only the confusable ones."""
    _enrol(db_session, 'ManyFrames', [[1.0, 0.02 * (i + 1), 0.0] for i in range(5)])
    _enrol(db_session, 'FewFrames', [[0.0, 1.0, 0.0]])

    engine = FaceEngine(users_svc.get_all_embeddings)
    ranked = engine._rank([[1.0, 0.0, 0.0]], users_svc.get_all_embeddings())

    assert len(ranked) == 2, 'five frames + one frame must rank as two identities'
    assert [r[2] for r in ranked] == ['ManyFrames', 'FewFrames']
    # Each entry is that identity's own best distance.
    assert ranked[0][0] < ranked[1][0]


def test_ambiguous_scan_is_rejected_rather_than_guessed(db_session):
    """Two people near-equally close means try again, not pick one."""
    _enrol(db_session, 'Alice', [[1.0, 0.0, 0.0]])
    _enrol(db_session, 'Bob',   [[0.999, 0.045, 0.0]])

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55, match_margin=0.10)
    uid, name, dist = engine.find_match([1.0, 0.02, 0.0], 0.55)

    assert (uid, name, dist) == (None, None, None)


def test_a_clear_winner_still_matches_with_the_margin_on(db_session):
    alice = _enrol(db_session, 'Alice', [[1.0, 0.0, 0.0]])
    _enrol(db_session, 'Bob', [[0.0, 1.0, 0.0]])          # orthogonal: distance 1.0

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55, match_margin=0.10)
    uid, name, _ = engine.find_match([0.99, 0.02, 0.0], 0.55)

    assert (uid, name) == (alice.user_id, 'Alice')


def test_margin_zero_restores_the_old_nearest_wins_behaviour(db_session):
    _enrol(db_session, 'Alice', [[1.0, 0.0, 0.0]])
    _enrol(db_session, 'Bob',   [[0.999, 0.045, 0.0]])

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55, match_margin=0.0)
    uid, _, _ = engine.find_match([1.0, 0.02, 0.0], 0.55)

    assert uid is not None, 'margin=0 must disable the ambiguity check'


def test_a_single_registered_person_is_never_ambiguous(db_session):
    solo = _enrol(db_session, 'Solo', [[1.0, 0.0, 0.0]])

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55, match_margin=0.10)
    uid, _, _ = engine.find_match([1.0, 0.01, 0.0], 0.55)

    assert uid == solo.user_id


def test_a_degenerate_stored_vector_cannot_match(db_session):
    """A zero vector makes cosine return nan, which must not be treated as near."""
    _enrol(db_session, 'Broken', [[0.0, 0.0, 0.0]])

    engine = FaceEngine(users_svc.get_all_embeddings, auth_threshold=0.55)
    ranked = engine._rank([[1.0, 0.0, 0.0]], users_svc.get_all_embeddings())

    assert ranked == [], 'a nan distance must be skipped, not ranked'

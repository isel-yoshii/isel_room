"""User service — registration, CRUD, face variants, grade promotion."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from isel.db import SessionLocal
from isel.db.models import User, Session as LabSession, AuditLog


VARIANT_KEYS = ('normal', 'glasses', 'mask')
MAX_FRAMES_PER_VARIANT = 3


def _as_variant_dict(stored) -> dict[str, list[list[float]]]:
    """Normalise any historical embedding shape to {variant: [vec, ...]}.

    Cases:
      None / empty            -> {}
      Flat list of floats     -> {'normal': [stored]}        (legacy single vector)
      List of flat lists      -> {'normal': stored[:3]}      (prior-commit flat list)
      Dict already            -> filter to VARIANT_KEYS, capped at 3 frames per slot
    """
    if not stored:
        return {}
    if isinstance(stored, list):
        if stored and isinstance(stored[0], (int, float)):
            return {'normal': [stored]}
        return {'normal': stored[:MAX_FRAMES_PER_VARIANT]}
    if isinstance(stored, dict):
        return {
            k: list(v)[:MAX_FRAMES_PER_VARIANT]
            for k, v in stored.items()
            if k in VARIANT_KEYS and v
        }
    return {}


def register_user(name: str, user_type: str, variants) -> int:
    """Create a new user and return the generated user_id.

    `variants` may be a {variant_key: [vec, ...]} dict or a legacy list/single vector;
    always stored as a dict of variants.
    """
    variant_dict = _as_variant_dict(variants)
    session = SessionLocal()
    try:
        user = User(name=name, user_type=user_type, embedding=variant_dict)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.user_id
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


def delete_user(user_id: int) -> None:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if user:
            session.delete(user)
            session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


def user_name_exists(name: str) -> bool:
    session = SessionLocal()
    try:
        stmt = select(User).where(User.name == name)
        return session.execute(stmt).scalars().first() is not None
    finally:
        session.close()


def get_user_name(user_id: int) -> str | None:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        return user.name if user else None
    finally:
        session.close()


def get_all_users_info() -> list[dict]:
    session = SessionLocal()
    try:
        users = list(session.execute(select(User)).scalars().all())
        last_seen_rows = session.execute(
            select(LabSession.user_id, func.max(LabSession.checked_out_at))
            .group_by(LabSession.user_id)
        ).all()
        last_seen_map = {uid: ts for uid, ts in last_seen_rows if ts is not None}
        return [
            {
                'id': u.user_id,
                'name': u.name,
                'type': u.user_type,
                'status': u.status,
                'has_face': bool(u.embedding),
                'face_variants': [k for k in VARIANT_KEYS if k in _as_variant_dict(u.embedding)],
                'last_seen': last_seen_map[u.user_id].isoformat() if u.user_id in last_seen_map else None,
            }
            for u in users
        ]
    finally:
        session.close()


def get_all_embeddings() -> dict[int, dict]:
    """Return {user_id: {name, variants}}; variants is {variant_key: [vec, ...]}."""
    session = SessionLocal()
    try:
        users = list(session.execute(select(User)).scalars().all())
        return {
            u.user_id: {'name': u.name, 'variants': _as_variant_dict(u.embedding)}
            for u in users
        }
    finally:
        session.close()


def update_user(user_id: int, name: str, user_type: str) -> dict:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.name = name
        user.user_type = user_type
        session.commit()
        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        session.close()


def set_face_variant(user_id: int, variant_key: str, frames: list[list[float]]) -> dict:
    """Replace one variant slot (normal/glasses/mask) with the given frames.

    Caps at MAX_FRAMES_PER_VARIANT. Returns the present variant keys after the update.
    """
    if variant_key not in VARIANT_KEYS:
        return {'success': False, 'message': f'Invalid variant: {variant_key}'}
    if not frames:
        return {'success': False, 'message': 'No frames provided'}
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        current = _as_variant_dict(user.embedding)
        current[variant_key] = list(frames)[:MAX_FRAMES_PER_VARIANT]
        user.embedding = current
        session.commit()
        return {'success': True, 'variants': [k for k in VARIANT_KEYS if k in current]}
    except Exception as e:
        session.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        session.close()


def promote_students(promotions: list[dict]) -> dict[str, int]:
    """Apply a list of explicit promotions. Each item: {user_id, new_type}.

    Returns counts keyed by 'old_type→new_type' transitions for the summary.
    All-or-nothing transaction; any error rolls back the whole batch.
    """
    if not promotions:
        return {}
    session = SessionLocal()
    counts: dict[str, int] = {}
    try:
        now = datetime.now()
        for entry in promotions:
            user = session.get(User, entry['user_id'])
            if user is None:
                continue
            new_type = entry['new_type']
            if new_type == user.user_type:
                continue
            old_type = user.user_type
            user.user_type = new_type
            key = f'{old_type}→{new_type}'
            counts[key] = counts.get(key, 0) + 1
            session.add(AuditLog(
                action_type='PROMOTE',
                target_user_id=user.user_id,
                target_name=user.name,
                performed_by='admin',
                timestamp=now,
            ))
        session.commit()
        return counts
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

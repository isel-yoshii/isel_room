from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func
from isel.db import session_scope
from isel.db.models import User, LabSession, AuditLog
from isel.utils import ApiError


VARIANT_KEYS = ('normal', 'glasses', 'mask')
MAX_FRAMES_PER_VARIANT = 3


def _normalize_variants(stored: dict | None) -> dict[str, list[list[float]]]:
    """Single guard for the {variant_key: [vec, ...]} embedding shape."""
    if not stored:
        return {}
    return {
        k: list(v)[:MAX_FRAMES_PER_VARIANT]
        for k, v in stored.items()
        if k in VARIANT_KEYS and v
    }


def register_user(name: str, user_type: str, variants: dict) -> int:
    variant_dict = _normalize_variants(variants)
    with session_scope() as session:
        user = User(name=name, user_type=user_type, embedding=variant_dict)
        session.add(user)
        session.flush()
        return user.user_id


def delete_user(user_id: int) -> None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user:
            session.delete(user)


def user_name_exists(name: str) -> bool:
    with session_scope() as session:
        stmt = select(User).where(User.name == name)
        return session.execute(stmt).scalars().first() is not None


def get_user_name(user_id: int) -> str | None:
    with session_scope() as session:
        user = session.get(User, user_id)
        return user.name if user else None


def get_all_users_info() -> list[dict]:
    with session_scope() as session:
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
                'face_variants': [k for k in VARIANT_KEYS if k in _normalize_variants(u.embedding)],
                'last_seen': last_seen_map[u.user_id].isoformat() if u.user_id in last_seen_map else None,
            }
            for u in users
        ]


def get_all_embeddings() -> dict[int, dict]:
    with session_scope() as session:
        users = list(session.execute(select(User)).scalars().all())
        return {
            u.user_id: {'name': u.name, 'variants': _normalize_variants(u.embedding)}
            for u in users
        }


def update_user(user_id: int, name: str, user_type: str) -> None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if not user:
            raise ApiError('User not found', 404)
        user.name = name
        user.user_type = user_type


def set_face_variant(user_id: int, variant_key: str, frames: list[list[float]]) -> list[str]:
    """Replace one variant slot; returns the variant keys present afterwards."""
    if variant_key not in VARIANT_KEYS:
        raise ApiError(f'Invalid variant: {variant_key}')
    if not frames:
        raise ApiError('No frames provided')
    with session_scope() as session:
        user = session.get(User, user_id)
        if not user:
            raise ApiError('User not found', 404)
        current = _normalize_variants(user.embedding)
        current[variant_key] = list(frames)[:MAX_FRAMES_PER_VARIANT]
        user.embedding = current
        return [k for k in VARIANT_KEYS if k in current]


def promote_students(promotions: list[dict]) -> dict[str, int]:
    """Each item: {user_id, new_type}. Returns counts keyed 'old→new'."""
    if not promotions:
        return {}
    counts: dict[str, int] = {}
    with session_scope() as session:
        now = datetime.now()
        for entry in promotions:
            if not isinstance(entry, dict) or 'user_id' not in entry or 'new_type' not in entry:
                raise ApiError('each promotion needs a user_id and a new_type')
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
        return counts

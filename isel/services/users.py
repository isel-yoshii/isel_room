"""User service — registration, CRUD, face update, grade promotion."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from isel.db import SessionLocal
from isel.db.models import User, Session as LabSession, AuditLog


def register_user(name: str, user_type: str, embedding: list) -> int:
    """Create a new user and return the generated user_id."""
    session = SessionLocal()
    try:
        user = User(name=name, user_type=user_type, embedding=embedding)
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
                'last_seen': last_seen_map[u.user_id].isoformat() if u.user_id in last_seen_map else None,
            }
            for u in users
        ]
    finally:
        session.close()


def get_all_embeddings() -> dict[int, dict]:
    session = SessionLocal()
    try:
        users = list(session.execute(select(User)).scalars().all())
        return {u.user_id: {'name': u.name, 'embedding': u.embedding} for u in users}
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


def update_face(user_id: int, embedding: list) -> dict:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.embedding = embedding
        session.commit()
        return {'success': True}
    except Exception as e:
        session.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        session.close()


def promote_students() -> dict[str, int]:
    """Promote B4→M1, M1→M2, M2→卒業. Returns counts per grade."""
    session = SessionLocal()
    counts = {'B4': 0, 'M1': 0, 'M2': 0}
    try:
        for from_type, to_type in [('M2', '卒業'), ('M1', 'M2'), ('B4', 'M1')]:
            stmt = select(User).where(User.user_type == from_type)
            users = list(session.execute(stmt).scalars().all())
            for user in users:
                user.user_type = to_type
                counts[from_type] += 1
                session.add(AuditLog(
                    action_type='PROMOTE',
                    target_user_id=user.user_id,
                    target_name=user.name,
                    performed_by='system',
                    timestamp=datetime.now(),
                ))
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    return counts

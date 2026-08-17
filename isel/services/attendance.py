from __future__ import annotations
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from isel.db import session_scope
from isel.db.models import User, LabSession, AuditLog
from isel.utils import ApiError, minutes_between

logger = logging.getLogger(__name__)

_STALE_SESSION_HOURS = 24


def toggle_entry(user_id: int, check_in_method: str = 'face') -> dict:
    with session_scope() as session:
        user = session.get(User, user_id)
        now = datetime.now()

        if user.status:  # IN → OUT
            user.status = False
            event = 'OUT'
            _close_open_session(session, user_id, now)
        else:  # OUT → IN
            _close_stale_session(session, user_id, now)
            user.status = True
            event = 'IN'
            new_sess = LabSession(
                user_id=user_id,
                checked_in_at=now,
                check_in_method=check_in_method,
            )
            session.add(new_sess)

        action_map = {
            ('IN',  'face'):   'CHECKIN',
            ('IN',  'manual'): 'MANUAL_CHECKIN',
            ('OUT', 'face'):   'CHECKOUT',
            ('OUT', 'manual'): 'MANUAL_CHECKOUT',
        }
        action = action_map.get((event, check_in_method), 'CHECKIN')
        session.add(AuditLog(
            action_type=action,
            target_user_id=user_id,
            target_name=user.name,
            performed_by='check-in',
            timestamp=now,
        ))

        return {
            'user_id': user_id,
            'name': user.name,
            'event_type': event,
            'timestamp': now.isoformat(),
        }


def auto_checkout_all() -> int:
    """Close everyone out. Returns how many sessions were closed.

    Sweeps by *open session*, not by `users.status`: the two desync when a crash
    lands between the session row and the status flag, and a status-driven sweep
    leaves that session open forever as an ever-growing visit.

    Errors propagate on purpose — swallowing them made a job that fired and
    failed look exactly like a job that never fired.
    """
    now = datetime.now()
    with session_scope() as session:
        open_sessions = list(session.execute(
            select(LabSession).where(LabSession.checked_out_at.is_(None))
        ).scalars().all())

        for lab_sess in open_sessions:
            lab_sess.checked_out_at = now
            lab_sess.check_in_method = 'auto_checkout'
            user = session.get(User, lab_sess.user_id)
            session.add(AuditLog(
                action_type='AUTO_CHECKOUT',
                target_user_id=lab_sess.user_id,
                target_name=user.name if user else f'user_{lab_sess.user_id}',
                performed_by='system',
                timestamp=now,
            ))

        # The other half of the same desync: flagged present, nothing open.
        still_present = list(session.execute(
            select(User).where(User.status.is_(True))
        ).scalars().all())
        for user in still_present:
            user.status = False

        count = len(open_sessions)
        logger.info('Auto-checkout closed %d open session(s); cleared %d present flag(s).',
                    count, len(still_present))

    # Best-effort: the checkout is already committed, so a failed board refresh
    # must not turn into a failed checkout.
    try:
        from isel.integrations.slack import update_status_board
        update_status_board()
    except Exception:
        logger.exception('Slack board refresh after auto-checkout failed (checkout itself succeeded).')

    return count


def get_present_users() -> list[str]:
    with session_scope() as session:
        stmt = select(User).where(User.status.is_(True))
        users = session.execute(stmt).scalars().all()
        return [u.name for u in users]


def get_present_users_detailed() -> list[dict]:
    with session_scope() as session:
        stmt = select(User).where(User.status.is_(True))
        users = session.execute(stmt).scalars().all()
        result = []
        for u in users:
            open_sess = _open_session(session, u.user_id)
            duration = None
            if open_sess:
                mins = minutes_between(open_sess.checked_in_at, datetime.now())
                duration = f'{mins // 60}h {mins % 60:02d}m'
            result.append({'id': u.user_id, 'name': u.name, 'type': u.user_type, 'duration': duration})
        return result


def get_user_status(user_id: int) -> bool:
    with session_scope() as session:
        user = session.get(User, user_id)
        return bool(user.status) if user else False


def update_session(session_id: int, checked_in_at: datetime, checked_out_at: datetime | None) -> None:
    with session_scope() as session:
        lab_sess = session.get(LabSession, session_id)
        if not lab_sess:
            raise ApiError('Session not found', 404)
        lab_sess.checked_in_at = checked_in_at
        lab_sess.checked_out_at = checked_out_at


def _open_session(session, user_id: int):
    stmt = (
        select(LabSession)
        .where(LabSession.user_id == user_id, LabSession.checked_out_at.is_(None))
        .order_by(LabSession.checked_in_at.desc())
    )
    return session.execute(stmt).scalars().first()


def _close_open_session(
    session,
    user_id: int,
    now: datetime,
    method: str | None = None,
) -> None:
    open_sess = _open_session(session, user_id)
    if open_sess:
        open_sess.checked_out_at = now
        if method:
            open_sess.check_in_method = method


def _close_stale_session(session, user_id: int, now: datetime) -> None:
    """Unlike _close_open_session, records that the system — not the person —
    ended the visit."""
    open_sess = _open_session(session, user_id)
    if open_sess and (now - open_sess.checked_in_at) > timedelta(hours=_STALE_SESSION_HOURS):
        open_sess.checked_out_at = now
        open_sess.check_in_method = 'auto_checkout'
        user = session.get(User, user_id)
        session.add(AuditLog(
            action_type='STALE_SESSION_CLOSED',
            target_user_id=user_id,
            target_name=user.name if user else f'user_{user_id}',
            performed_by='system',
            timestamp=now,
        ))

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func
from config import Config
from backend.db import session_scope
from backend.db.models import User, LabSession, AuditLog, Device
from backend.utils import ApiError, minutes_between

logger = logging.getLogger(__name__)

_STALE_SESSION_HOURS = 24


_ACTIONS = {
    ('IN',  'face'):   'CHECKIN',
    ('IN',  'manual'): 'MANUAL_CHECKIN',
    ('IN',  'wifi'):   'WIFI_CHECKIN',
    ('OUT', 'face'):   'CHECKOUT',
    ('OUT', 'manual'): 'MANUAL_CHECKOUT',
    ('OUT', 'wifi'):   'WIFI_CHECKOUT',
}


def toggle_entry(user_id: int, check_in_method: str = 'face') -> dict:
    with session_scope() as session:
        user = _get_user(session, user_id)
        return apply_entry(session, user, not user.status, check_in_method, datetime.now())


def set_entry(user_id: int, present: bool, check_in_method: str = 'face') -> dict:
    """Unlike toggle_entry, asking for the state the person is already in changes
    nothing — so a face check-in after Wi-Fi already checked them in is harmless."""
    with session_scope() as session:
        user = _get_user(session, user_id)
        return apply_entry(session, user, present, check_in_method, datetime.now())


def apply_entry(session, user: User, present: bool, method: str, at: datetime) -> dict:
    """Move `user` to `present` inside the caller's transaction. `at` may be in
    the past: a Wi-Fi checkout is dated to when the phone was last seen."""
    changed = bool(user.status) != present
    if changed:
        if present:
            _close_stale_session(session, user.user_id, at)
            user.status = True
            session.add(LabSession(
                user_id=user.user_id,
                checked_in_at=at,
                check_in_method=method,
            ))
        else:
            user.status = False
            _close_open_session(session, user.user_id, at)

        event = 'IN' if present else 'OUT'
        session.add(AuditLog(
            action_type=_ACTIONS.get((event, method), 'CHECKIN'),
            target_user_id=user.user_id,
            target_name=user.name,
            performed_by='check-in',
            timestamp=at,
        ))

    # A person's own action decides whether their phone may check them in:
    # checking in re-arms it, checking out disarms it until it leaves once.
    if method != 'wifi':
        if present:
            _set_device_lock(session, [user.user_id], False)
        elif changed:
            _set_device_lock(session, [user.user_id], True)

    return {
        'user_id': user.user_id,
        'name': user.name,
        'event_type': 'IN' if user.status else 'OUT',
        'changed': changed,
        'timestamp': at.isoformat(),
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
            lab_sess.checked_out_at = _phone_left_at(session, lab_sess, now) or now
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

        # Phones are still on Wi-Fi at reset time; without this the next scan
        # would check everyone straight back in.
        _set_device_lock(
            session,
            [s.user_id for s in open_sessions] + [u.user_id for u in still_present],
            True,
        )

        count = len(open_sessions)
        logger.info('Auto-checkout closed %d open session(s); cleared %d present flag(s).',
                    count, len(still_present))

    # Best-effort: the checkout is already committed, so a failed board refresh
    # must not turn into a failed checkout.
    try:
        from backend.integrations.slack import update_status_board
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
            open_sess = open_session(session, u.user_id)
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


def _get_user(session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ApiError('User not found', 404)
    return user


def _phone_left_at(session, lab_sess: LabSession, now: datetime) -> datetime | None:
    """When the owner's phone was last on Wi-Fi, if that dates the end of this
    visit better than `now` does.

    Someone who left 15 minutes before the nightly reset is still inside their
    grace period, so the reset — not the Wi-Fi timeout — closes them out, and
    stamping `now` would pad the visit by those 15 minutes.
    """
    last_seen = session.execute(
        select(func.max(Device.last_seen_at)).where(Device.user_id == lab_sess.user_id)
    ).scalar()
    if last_seen is None or last_seen < lab_sess.checked_in_at:
        return None
    # Unseen for longer than the grace period yet still checked in means scanning
    # has been down, and a stale sighting is not evidence of when anyone left.
    if now - last_seen > timedelta(minutes=Config.PRESENCE_GRACE_MINUTES):
        return None
    return last_seen


def _set_device_lock(session, user_ids: list[int], locked: bool) -> None:
    if not user_ids:
        return
    devices = session.execute(
        select(Device).where(Device.user_id.in_(user_ids))
    ).scalars().all()
    for device in devices:
        device.locked = locked


def open_session(session, user_id: int):
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
    open_sess = open_session(session, user_id)
    if open_sess:
        open_sess.checked_out_at = now
        if method:
            open_sess.check_in_method = method


def _close_stale_session(session, user_id: int, now: datetime) -> None:
    """Unlike _close_open_session, records that the system — not the person —
    ended the visit."""
    open_sess = open_session(session, user_id)
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

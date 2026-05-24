"""Attendance service — toggle entry, auto checkout, presence queries."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import select
from isel.db import session_scope
from isel.db.models import User, Session as LabSession, AuditLog

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


def auto_checkout_all() -> None:
    try:
        with session_scope() as session:
            stmt = select(User).where(User.status.is_(True))
            present_users = list(session.execute(stmt).scalars().all())
            now = datetime.now()
            for user in present_users:
                user.status = False
                _close_open_session(session, user.user_id, now, method='auto_checkout')
                session.add(AuditLog(
                    action_type='AUTO_CHECKOUT',
                    target_user_id=user.user_id,
                    target_name=user.name,
                    performed_by='system',
                    timestamp=now,
                ))
            count = len(present_users)
        if count:
            print(f'[{datetime.now().strftime("%H:%M:%S")}] {count}名の自動退室処理を完了しました。')
        try:
            from isel.integrations.slack import update_status_board
            update_status_board()
        except Exception as e:
            print(f'Slack board refresh after auto-checkout failed: {e}')
    except Exception as e:
        print(f'自動退室処理でエラー: {e}')


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
            open_stmt = (
                select(LabSession)
                .where(LabSession.user_id == u.user_id, LabSession.checked_out_at.is_(None))
                .order_by(LabSession.checked_in_at.desc())
            )
            open_sess = session.execute(open_stmt).scalars().first()
            duration = None
            if open_sess:
                mins = int((datetime.now() - open_sess.checked_in_at).total_seconds() / 60)
                duration = f'{mins // 60}h {mins % 60:02d}m'
            result.append({'id': u.user_id, 'name': u.name, 'type': u.user_type, 'duration': duration})
        return result


def get_user_status(user_id: int) -> bool:
    with session_scope() as session:
        user = session.get(User, user_id)
        return bool(user.status) if user else False


def update_session(session_id: int, checked_in_at: datetime, checked_out_at: datetime | None) -> dict:
    try:
        with session_scope() as session:
            lab_sess = session.get(LabSession, session_id)
            if not lab_sess:
                return {'success': False, 'message': 'Session not found'}
            lab_sess.checked_in_at = checked_in_at
            lab_sess.checked_out_at = checked_out_at
            return {'success': True}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def _close_open_session(
    session,
    user_id: int,
    now: datetime,
    method: str | None = None,
) -> None:
    stmt = (
        select(LabSession)
        .where(LabSession.user_id == user_id, LabSession.checked_out_at.is_(None))
        .order_by(LabSession.checked_in_at.desc())
    )
    open_sess = session.execute(stmt).scalars().first()
    if open_sess:
        open_sess.checked_out_at = now
        if method:
            open_sess.check_in_method = method


def _close_stale_session(session, user_id: int, now: datetime) -> None:
    stmt = (
        select(LabSession)
        .where(LabSession.user_id == user_id, LabSession.checked_out_at.is_(None))
        .order_by(LabSession.checked_in_at.desc())
    )
    open_sess = session.execute(stmt).scalars().first()
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

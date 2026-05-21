from core.SQL.models.model import User, Session as LabSession, AuditLog
from datetime import datetime


class AttendanceService:
    def __init__(self, user_repo, session):
        self.user_repo = user_repo
        self.session = session

    def _close_open_session(self, user_id, now):
        """Open Session があれば閉じる。戻り値: 閉じたセッションの分数(なければ0)"""
        open_sess = (
            self.session.query(LabSession)
            .filter_by(user_id=user_id, checked_out_at=None)
            .order_by(LabSession.checked_in_at.desc())
            .first()
        )
        if open_sess:
            open_sess.checked_out_at = now
            minutes = int((now - open_sess.checked_in_at).total_seconds() / 60)
            return minutes
        return 0

    def toggle_entry(self, user_id, check_in_method='face'):
        user = self.user_repo.get_by_id(user_id)
        now = datetime.now()

        if user.status:  # 現在 IN → OUT へ切り替え
            user.status = False
            event = "OUT"
            self._close_open_session(user_id, now)

        else:  # 現在 OUT → IN へ切り替え
            # 安全策: 前回チェックアウト忘れのセッションがあれば先に閉じる
            self._close_open_session(user_id, now)
            user.status = True
            event = "IN"
            new_sess = LabSession(user_id=user_id, checked_in_at=now, check_in_method=check_in_method)
            self.session.add(new_sess)

        self.session.commit()

        action_map = {
            ('IN',  'face'):   'CHECKIN',
            ('IN',  'manual'): 'MANUAL_CHECKIN',
            ('OUT', 'face'):   'CHECKOUT',
            ('OUT', 'manual'): 'MANUAL_CHECKOUT',
        }
        action = action_map.get((event, check_in_method), 'CHECKIN')
        user = self.user_repo.get_by_id(user_id)
        audit = AuditLog(
            action_type=action,
            target_user_id=user_id,
            target_name=user.name,
            performed_by='kiosk',
            timestamp=now,
        )
        self.session.add(audit)
        self.session.commit()

        return self.get_log_json(user_id, event, now)

    def get_log_json(self, user_id, event, now):
        user = self.user_repo.get_by_id(user_id)
        return {
            "user_id": user_id,
            "name": user.name,
            "event_type": event,
            "timestamp": now.isoformat(),
        }

from core.SQL.models.model import User, TimeLog, Session as LabSession
from datetime import datetime

# ユーザーの入退室を管理するためのクラス(User, TimeLogテーブルを使用した処理を行う)
class AttendanceService:
    def __init__(self, user_repo, timelog_repo, session):
        self.user_repo = user_repo
        self.timelog_repo = timelog_repo
        self.session = session

    def _close_open_session(self, user_id, now):
        """Open Session があれば閉じて user.totaltime を更新する。戻り値: 閉じたセッションの分数(なければ0)"""
        user = self.user_repo.get_by_id(user_id)
        open_sess = (
            self.session.query(LabSession)
            .filter_by(user_id=user_id, checked_out_at=None)
            .order_by(LabSession.checked_in_at.desc())
            .first()
        )
        if open_sess:
            open_sess.checked_out_at = now
            minutes = int((now - open_sess.checked_in_at).total_seconds() / 60)
            user.totaltime = (user.totaltime or 0) + minutes
            return minutes
        return 0

    def toggle_entry(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        now = datetime.now()

        if user.status:  # 現在 IN → OUT へ切り替え
            user.status = False
            event = "OUT"

            # Session を閉じて totaltime を更新
            closed = self._close_open_session(user_id, now)
            if not closed:
                # 移行前データ: Session がない場合は TimeLog で計算(フォールバック)
                last_in = (
                    self.session.query(TimeLog)
                    .filter_by(user_id=user_id, event_type="IN")
                    .order_by(TimeLog.timestamp.desc())
                    .first()
                )
                if last_in:
                    minutes = int((now - last_in.timestamp).total_seconds() / 60)
                    user.totaltime = (user.totaltime or 0) + minutes

        else:  # 現在 OUT → IN へ切り替え
            # 安全策: 前回チェックアウト忘れのセッションがあれば先に閉じる
            self._close_open_session(user_id, now)

            user.status = True
            event = "IN"

            # 新しい Session を開始
            new_sess = LabSession(user_id=user_id, checked_in_at=now, check_in_method='face')
            self.session.add(new_sess)

        log = TimeLog(user_id=user_id, event_type=event, timestamp=now)
        self.timelog_repo.add(log)
        self.session.commit()

        return self.get_log_json(user_id, log)
    
    def get_log_json(self, user_id, timelog):
        user = self.user_repo.get_by_id(user_id)
        return {
            "user_id": user_id,
            "name": user.name,
            "event_type": timelog.event_type,
            "timestamp": timelog.timestamp.isoformat()
        }
    
    def get_logs_by_user_id(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        if user:
            return user.logs
        return None
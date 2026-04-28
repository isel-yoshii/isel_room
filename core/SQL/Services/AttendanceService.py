from core.SQL.models.model import User, TimeLog
from datetime import datetime

# ユーザーの入退室を管理するためのクラス(User, TimeLogテーブルを使用した処理を行う)
class AttendanceService:
    def __init__(self, user_repo, timelog_repo, session):
        self.user_repo = user_repo
        self.timelog_repo = timelog_repo
        self.session = session

    def toggle_entry(self, user_id):
        user = self.user_repo.get_by_id(user_id)

        if user.status:
            user.status = False
            event = "OUT"
        else:
            user.status = True
            event = "IN"

        log = TimeLog(user_id=user_id, event_type=event, timestamp=datetime.now())
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
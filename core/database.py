from core.SQL.sql_db import SessionClass, init_db
from core.SQL.repositories.repository import UserRepository, TimeLogRepository
from core.SQL.Services.UserService import UserService
from core.SQL.Services.AttendanceService import AttendanceService
from datetime import datetime, timedelta, time
import os


class SQLDatabase:
    """
    MemoryDB の代替。アプリ全体でこのクラスだけを使う。
    セッション・リポジトリ・サービスの細かい話はここで全部隠す。
    """

    def __init__(self):
        init_db()  # 起動時にテーブルを作成（既にあれば何もしない）

    # ---- ユーザー管理 ----

    def add_user(self, name, user_type, embedding):
        """ユーザーを登録してuser_idを返す"""
        session = SessionClass()
        user_repo = UserRepository(session)
        service = UserService(user_repo, session)
        user = service.add_user(name, user_type, embedding)
        user_id = user.user_id
        session.close()
        return user_id

    def delete_user(self, user_id):
        """ユーザーを削除する"""
        session = SessionClass()
        user_repo = UserRepository(session)
        service = UserService(user_repo, session)
        service.delete_user(user_id)
        session.close()

    def user_name_exists(self, name):
        """同じ名前のユーザーが既に存在するか確認する"""
        session = SessionClass()
        user_repo = UserRepository(session)
        users = user_repo.get_all_users()
        exists = any(u.name == name for u in users)
        session.close()
        return exists

    # ---- 顔認識用 ----

    def get_all_embeddings(self):
        """
        全ユーザーのID・名前・顔データを返す。
        face_engine.py の find_match() が使う。
        戻り値: {user_id: {"name": 名前, "embedding": [...]}}
        """
        session = SessionClass()
        user_repo = UserRepository(session)
        users = user_repo.get_all_users()
        result = {u.user_id: {"name": u.name, "embedding": u.embedding} for u in users}
        session.close()
        return result

    # ---- 入退室 ----

    def toggle_entry(self, user_id):
        """
        入室 or 退室を切り替えてログを記録する。
        戻り値: {"user_id": ..., "name": ..., "event_type": "IN"/"OUT", "timestamp": ...}
        """
        session = SessionClass()
        user_repo = UserRepository(session)
        timelog_repo = TimeLogRepository(session)
        service = AttendanceService(user_repo, timelog_repo, session)
        result = service.toggle_entry(user_id)
        session.close()
        return result

    # ---- 在室確認 ----

    def get_present_users(self):
        """現在在室しているユーザーの名前リストを返す"""
        from core.SQL.models.model import User
        session = SessionClass()
        users = session.query(User).filter(User.status == True).all()
        names = [u.name for u in users]
        session.close()
        return names

    def get_present_users_detailed(self):
        """Returns present users with name and how long they've been in (for UI strip/dashboard)."""
        from core.SQL.models.model import User, TimeLog
        from datetime import datetime
        session = SessionClass()
        users = session.query(User).filter(User.status == True).all()
        result = []
        for u in users:
            last_in = (
                session.query(TimeLog)
                .filter(TimeLog.user_id == u.user_id, TimeLog.event_type == 'IN')
                .order_by(TimeLog.timestamp.desc())
                .first()
            )
            duration = None
            if last_in:
                mins = int((datetime.now() - last_in.timestamp).total_seconds() / 60)
                duration = f"{mins // 60}h {mins % 60:02d}m"
            result.append({'id': u.user_id, 'name': u.name, 'type': u.user_type, 'duration': duration})
        session.close()
        return result

    def get_all_users_info(self):
        """Returns all users (id, name, type, status) for the admin panel."""
        session = SessionClass()
        user_repo = UserRepository(session)
        users = user_repo.get_all_users()
        result = [{'id': u.user_id, 'name': u.name, 'type': u.user_type, 'status': u.status} for u in users]
        session.close()
        return result

    def get_today_log(self):
        """Returns today's activity log sorted newest-first (for dashboard activity feed)."""
        from core.SQL.models.model import TimeLog, User
        from datetime import datetime, date
        session = SessionClass()
        now = datetime.now()

        reset_hour = int(os.getenv("DAY_RESET_HOUR", 4))

        if now.hour < reset_hour:
            logical_date = now.date() - timedelta(days=1)
        else:
            logical_date = now.date()
            
        today_start = datetime.combine(logical_date, time(reset_hour, 0))

        rows = (
            session.query(TimeLog, User)
            .join(User)
            .filter(TimeLog.timestamp >= today_start)
            .order_by(TimeLog.timestamp.desc())
            .all()
        )
        result = [
            {'name': u.name, 'event_type': l.event_type, 'timestamp': l.timestamp.strftime('%H:%M')}
            for l, u in rows
        ]
        session.close()
        return result
    
    def force_checkout_all(self):
        """在室中の全員を強制的に退室（OUT）にする（指定時間の自動処理用）"""
        from core.SQL.models.model import User, TimeLog
        from core.log_generator import append_attendance_log
        session = SessionClass()
        try:
            present_users = session.query(User).filter(User.status == True).all()
            now = datetime.now()

            for user in present_users:
                user.status = False
                log = TimeLog(user_id=user.user_id, event_type="OUT", timestamp=now)
                session.add(log)

            session.commit()

            for user in present_users:
                append_attendance_log(user.user_id, user.name, '退室(自動)')

            if present_users:
                print(f"[{now.strftime('%H:%M:%S')}] {len(present_users)}名の自動退室処理を完了しました。")
        except Exception as e:
            session.rollback()
            print(f"自動退室処理でエラー: {e}")
        finally:
            session.close()

    # ---- 管理者操作ログ ----

    def get_user_name(self, user_id):
        session = SessionClass()
        user_repo = UserRepository(session)
        name = user_repo.get_name(user_id)
        session.close()
        return name

    def add_audit_log(self, action_type, user_id, name):
        from core.SQL.models.model import AuditLog
        session = SessionClass()
        log = AuditLog(
            action_type=action_type,
            target_user_id=user_id,
            target_name=name,
            performed_by='admin',
            timestamp=datetime.now(),
        )
        session.add(log)
        session.commit()
        session.close()

    def get_audit_log(self, limit=50):
        from core.SQL.models.model import AuditLog
        session = SessionClass()
        rows = (
            session.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        result = [
            {
                'action': r.action_type,
                'user_id': r.target_user_id,
                'name': r.target_name,
                'performed_by': r.performed_by,
                'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M'),
            }
            for r in rows
        ]
        session.close()
        return result

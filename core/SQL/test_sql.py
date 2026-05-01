from core.SQL.Services.UserService import UserService
from core.SQL.Services.AttendanceService import AttendanceService
from core.SQL.repositories.repository import UserRepository, TimeLogRepository
from core.SQL.models.model import User, TimeLog
from core.SQL.sql_db import SessionClass, Base, engine
from datetime import datetime

def test_DB():
    # DBの初期化
    Base.metadata.create_all(bind=engine)
    session = SessionClass()

    # リポジトリとサービスの初期化
    user_repo = UserRepository(session)
    timelog_repo = TimeLogRepository(session)
    attendance_service = AttendanceService(user_repo, timelog_repo, session)
    user_service = UserService(user_repo, session)

    # ユーザーの追加
    user_service.add_user(name="Test User", user_type="student", embedding=[0.1, 0.2, 0.3])
    user = user_repo.get_by_id(1)
    assert user.name == "Test User"
    assert user.user_type == "student"
    assert user.embedding == [0.1, 0.2, 0.3]

    # 入退室の切り替えとログの取得
    log = attendance_service.toggle_entry(user.user_id)
    assert log["event_type"] == "IN"
    
    logs = attendance_service.get_logs_by_user_id(user.user_id)
    assert len(logs) == 1
    assert logs[0].event_type == "IN"

    # クリーンアップ
    user_service.delete_user(user.user_id)
    assert user_repo.get_by_id(user.user_id) is None
    
    # セッションを閉じる
    session.close()
    
    
    if __name__ == "__main__":
        test_DB()
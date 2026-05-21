from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from core.SQL.sql_db import Base

# Userテーブルのモデルを定義するクラス
class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, index=True)  # ユーザーID
    name = Column(String(255), index=True)  # ユーザーの表示名
    user_type = Column(String(50)) # ユーザーの権限（例: "学生", "管理者"など）
    embedding = Column(JSON)  # 顔データをJSON形式で保存
    # embeddingは　JSON型（MySQLならJSON）OR BLOB OR 別テーブル or 外部ストレージ（推奨）が良いかも
    status = Column(Boolean, default=False)  # 入室状態
    totaltime = Column(Integer, default=0)  # 合計滞在時間
    
    logs = relationship("TimeLog", back_populates="user", cascade="all, delete-orphan")  # TimeLogオブジェクトと紐付け(userと連動)

# TimeLogテーブルのモデルを定義するクラス
class TimeLog(Base):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True, index=True)  # ログID
    ### ForeignKeyでUserテーブルのuser_idと関連付ける※消すな ###
    user_id = Column(Integer, ForeignKey('users.user_id'))  # ユーザーID
    event_type = Column(String(10))  # 'IN' or 'OUT'
    timestamp = Column(DateTime)  # ログの時刻を保存するフィールド

    user = relationship("User", back_populates="logs")  # Userオブジェクトと紐付け(logsと連動)


# Sessionsテーブル: 1行 = 1回の入室セッション (checked_in_at → checked_out_at)
# duration は computed (checked_out_at - checked_in_at)、保存しない
class Session(Base):
    __tablename__ = 'sessions'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    checked_in_at   = Column(DateTime, nullable=False)
    checked_out_at  = Column(DateTime, nullable=True)   # NULL = 現在入室中
    check_in_method = Column(String(20), default='face') # face | manual | auto_checkout


# AuditLogテーブル: 管理者操作(登録・削除)の記録
class AuditLog(Base):
    __tablename__ = 'audit_log'

    id            = Column(Integer, primary_key=True, index=True)
    action_type   = Column(String(20))    # 'REGISTER' or 'DELETE'
    target_user_id = Column(Integer)
    target_name   = Column(String(255))
    performed_by  = Column(String(50), default='admin')
    timestamp     = Column(DateTime)
    
from sqlalchemy import Column, Integer, String, Boolean
from sql_db import Base

# ユーザーテーブルのモデルを定義するクラス
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    user_type = Column(String(50))
    embedding = Column(String(255))  # 顔データを文字列として保存する例
    status = Column(Boolean, default=False)  # 入室状態を表すフィールド
    totaltime = Column(Integer, default=0)  # 合計滞在時間を表すフィールド
    
    
class TimeLog(Base):
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    status = Column(Boolean, default=False)  # 入室状態を表すフィールド
    in_time = Column(String(255))  # ログの時刻を保存するフィールド
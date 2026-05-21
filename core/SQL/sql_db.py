from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# SQLiteはファイル1つで動く。プロジェクトルートに isel_room.db が作られる
# 将来MySQLに切り替える場合: 'mysql+pymysql://username:password@localhost/isel_room'
DATABASE_URL = 'sqlite:///isel_room.db'

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionClass = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db():
    """テーブルが存在しない場合に作成する。アプリ起動時に1回呼ぶ。"""
    from core.SQL.models.model import User, AuditLog, Session  # noqa: F401
    Base.metadata.create_all(engine)

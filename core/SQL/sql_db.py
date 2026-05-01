#import pymysql
#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# データベースの接続先を指定
DATABASE_URL = "mysql+pymysql://myuser:password@localhost/isel_room"
engine = create_engine(DATABASE_URL)
# DB操作用のセッションを作るためのクラスを定義
SessionClass = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# テーブルモデルのベースクラスを作成
Base = declarative_base()



#import pymysql
#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# データベースの接続先を指定
DATABASE_URL = 'mysql+pymysql://user_name:host_name/db_name'
engine = create_engine(DATABASE_URL)
# DB操作用のセッションを作るためのクラスを定義
SessionClass = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# テーブルモデルのベースクラスを作成
Base = declarative_base()

    

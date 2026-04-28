#import pymysql
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from model import User  # フォルダ構造に合わせたインポート

Base = declarative_base()

class SQLDatabase():
    # データベース接続やクエリ実行の基本的な機能を提供するクラス(読み出しと書き込み両方)
    def __init__(self):
        self.logs = []
        DATABASE_URL = 'mysql+pymysql://user_name:host_name/db_name'
        self.engine = sqlalchemy.create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
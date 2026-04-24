#import pymysql
#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from model import User, TimeLog
from datetime import datetime

# データベースの接続先を指定
DATABASE_URL = 'mysql+pymysql://user_name:host_name/db_name'
engine = create_engine(DATABASE_URL)
# DB操作用のセッションを作るためのクラスを定義
SessionClass = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# テーブルモデルのベースクラスを作成
Base = declarative_base()

class SQLDatabase():
    # データベース接続やクエリ実行の基本的な機能を提供するクラス(読み出しと書き込み両方)
    def __init__(self):
        self.logs = []
        self.session = SessionClass()
              
    def get_last_status(self, user_id):
        # Userテーブルのstatusを参照
        
        return "OUT"
    
    def get_ID(self, name):
        # 名前からIDを取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にIDを生成して返す
        return hash(name) % 10000  # 簡単なハッシュ関数でIDを生成
    
    def get_display_name(self, user_id):
        # IDから表示名を取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にIDを名前に変換して返す
        return f"User{user_id}"  # 仮の表示名
    
    def get_display_name_by_embedding(self, embedding):
        # 顔データから表示名を取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にIDを名前に変換して返す
        user_id = self.get_ID_by_embedding(embedding)
        return f"User{user_id}"  # 仮の表示名
    
    def get_usertype(self, user_id):
        # IDからユーザーの権限を取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にユーザーの権限を返す
        return "一般"  # 仮のユーザー権限
    
    def get_embedding_data(self, user_id):
        # IDからユーザーの顔データを取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮に顔データを返す
        return [0.0] * 128  # 仮の顔データ（128次元のベクトル）
    
    def add_last_status(self, user_id, status):
        # 入退室のログをデータベースに追加する（実際にはSQLクエリでデータベースに追加する）
        # ここでは仮にログを保存する処理をここに追加する
        self.logs.append({"user_id": user_id, "type": status, "time": "現在の時刻"})  # 仮の時刻
    
    def add_ID(self, name, user_type, embedding):
        # 名前、ユーザーの権限、顔データをデータベースに追加する（実際にはSQLクエリでデータベースに追加する）
        # ここでは仮にIDを生成して返す
        user_id = self.get_ID(name)
        # データベースにユーザー情報を保存する処理をここに追加する
        return user_id
    
    def add_display_name(self, user_id, disp_name):
        # IDと表示名をデータベースに追加する（実際にはSQLクエリでデータベースに追加する）
        # ここでは仮に表示名を保存する処理をここに追加する
        pass
    
    def add_usertype(self, user_id, usertype):
        # IDとユーザーの権限をデータベースに追加する（実際にはSQLクエリでデータベースに追加する）
        # ここでは仮にユーザーの権限を保存する処理をここに追加する
        pass
    
    def add_embedding_data(self, user_id, embedding):
        # IDと顔データをデータベースに追加する（実際にはSQLクエリでデータベースに追加する）
        # ここでは仮に顔データを保存する処理をここに追加する
        pass
    
    def delete_db(self, user_id):
        # IDに対応するユーザーをデータベースから削除する（実際にはSQLクエリでデータベースから削除する）
        # ここでは仮にユーザーを削除する処理をここに追加する
        pass
    



class UserService:
    def __init__(self, session):
        self.session = session

    def add_user(self, name, user_type, embedding):
        user = User(name=name, user_type=user_type, embedding=embedding)
        self.session.add(user)
        self.session.commit()
        return user

    def delete_user(self, user_id):
        user = self.session.get(User, user_id)
        self.session.delete(user)
        self.session.commit()
        
class AttendanceService:
    def __init__(self, session):
        self.session = session

    def toggle_entry(self, user_id):
        user = self.session.get(User, user_id)

        if user.status == False:
            user.status = True
            event = "IN"
        else:
            user.status = False
            event = "OUT"

        log = TimeLog(user=user, event_type=event, timestamp=datetime.now())

        self.session.add(log)
        self.session.commit()

        return event
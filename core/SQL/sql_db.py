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
        
    def get_last_status(self, user_id):
        # 最後のログを見て、次は入室か退室かを判断する 
        user_logs = [l for l in self.logs if l["user_id"] == user_id]
        if not user_logs or user_logs[-1]["type"] == "OUT":
            return "IN"
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
        
    def get_present_users(self, name):
        # 現在在室しているユーザーのリストを取得する
        session = self.SessionLocal()
        try:
            present_users = session.query(User).filter(User.status == True).all
            names = [user.name for user in present_users]
            return names
        except Exception as e:
            print(f"データ取得エラー: {e}")
            return []
        finally :
            session.close()

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
    



class Add_User(SQLDatabase):
    def __init__(self, disp_name, user_type, embedding):
        super().__init__()
        self.disp_name = disp_name
        self.user_type = user_type
        self.embedding = embedding
        
        
class Delete_User(SQLDatabase):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
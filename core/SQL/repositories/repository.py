# Repositoryクラスは、データベースのテーブルごとに作成されるクラスで、テーブルへのアクセスや操作を行うためのメソッドを提供します。
from core.SQL.models.model import User, TimeLog

class UserRepository:
    def __init__(self, session):
        self.session = session

    def get_by_id(self, user_id):
        return self.session.get(User, user_id)

    def get_name(self, user_id):
        user = self.get_by_id(user_id)
        return user.name if user else None
    
    def get_usertype(self, user_id):
        user = self.get_by_id(user_id)
        return user.user_type if user else None
    
    def get_embedding(self, user_id):
        user = self.get_by_id(user_id)
        return user.embedding if user else None
    
    def get_embedding_table(self):
        return self.session.query(User.user_id, User.embedding).all()
    
<<<<<<< HEAD
    def get_present_users(self, name):
        # 現在在室しているユーザーのリストを取得する
        session = self.SessionLocal()
        try:
            present_users = session.query(User).filter(User.status == True).all()
=======
    def get_present_users(self):
        # 現在在室しているユーザーのリストを取得する
        try:
            present_users = self.session.query(User).filter(User.status == True).all()
>>>>>>> origin
            names = [user.name for user in present_users]
            return names
        except Exception as e:
            print(f"データ取得エラー: {e}")
            return []
<<<<<<< HEAD
        finally :
            session.close()
=======
>>>>>>> origin

    def add(self, user):
        self.session.add(user)

    def delete(self, user):
        self.session.delete(user)
            
            
class TimeLogRepository:
    def __init__(self, session):
        self.session = session

    def add(self, log):
        self.session.add(log)
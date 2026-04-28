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

    def add(self, user):
        self.session.add(user)

    def delete(self, user):
        self.session.delete(user)
            
            
class TimeLogRepository:
    def __init__(self, session):
        self.session = session

    def add(self, log):
        self.session.add(log)
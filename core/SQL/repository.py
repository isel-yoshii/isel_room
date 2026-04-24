# Repositoryクラスは、データベースのテーブルごとに作成されるクラスで、テーブルへのアクセスや操作を行うためのメソッドを提供します。
from model import User, TimeLog

class UserRepository:
    def __init__(self, session):
        self.session = session

    def get_by_id(self, user_id):
        return self.session.get(User, user_id)

    def get_name(self, user_id):
        user = self.get_by_id(user_id)
        return user.name if user else None

    def add(self, user):
        self.session.add(user)

    def delete(self, user_id):
        user = self.get_by_id(user_id)
        if user:
            self.session.delete(user)
            
            
class TimeLogRepository:
    def __init__(self, session):
        self.session = session

    def add(self, log):
        self.session.add(log)
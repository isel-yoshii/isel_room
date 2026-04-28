from core.SQL.models.model import User

# Userテーブルを使用した処理を行うクラス
class UserService:
    def __init__(self, user_repo, session):
        self.user_repo = user_repo
        self.session = session

    def add_user(self, name, user_type, embedding):
        user = User(name=name, user_type=user_type, embedding=embedding)
        self.user_repo.add(user)
        self.session.commit()   # commit()でDBに反映させる
        return user

    def delete_user(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        if user:
            self.user_repo.delete(user_id)
        self.session.commit()
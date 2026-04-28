from core.SQL.models.model import User
from sqlalchemy.exc import SQLAlchemyError

# Userテーブルを使用した処理を行うクラス
class UserService:
    def __init__(self, user_repo, session):
        self.user_repo = user_repo
        self.session = session

    def add_user(self, name, user_type, embedding):
        user = User(name=name, user_type=user_type, embedding=embedding)
        try:
            self.user_repo.add(user)
            self.session.commit()   # commit()でDBに反映させる
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def delete_user(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        if user:
            try:
                self.user_repo.delete(user)
                self.session.commit()
            except SQLAlchemyError as e:
                self.session.rollback()
                raise e
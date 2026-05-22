from __future__ import annotations
from sqlalchemy.orm import Session as DbSession
from isel.db.models import User


class UserRepository:
    def __init__(self, session: DbSession) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_name(self, user_id: int) -> str | None:
        user = self.get_by_id(user_id)
        return user.name if user else None

    def get_usertype(self, user_id: int) -> str | None:
        user = self.get_by_id(user_id)
        return user.user_type if user else None

    def get_embedding(self, user_id: int) -> list | None:
        user = self.get_by_id(user_id)
        return user.embedding if user else None

    def get_all(self) -> list[User]:
        from sqlalchemy import select
        return list(self.session.execute(select(User)).scalars().all())

    def get_embedding_table(self) -> list[tuple[int, list]]:
        from sqlalchemy import select
        rows = self.session.execute(select(User.user_id, User.embedding)).all()
        return list(rows)

    def add(self, user: User) -> None:
        self.session.add(user)

    def delete(self, user: User) -> None:
        self.session.delete(user)

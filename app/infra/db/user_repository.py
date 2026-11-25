from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.infra.db.models import User


MAX_SEARCH_TERMS = 5


class UserRepository:

    def __init__(self, session: Session):
        self.session = session

    @staticmethod # does not need to access self.session or any other instance attribute.
    def _matching(statement, q: str | None):
        """Match every search term against username or full name."""

        terms = (q or "").lower().split()[:MAX_SEARCH_TERMS]

        for term in terms:
            statement = statement.where(
                or_(
                    func.lower(User.username).contains(
                        term, autoescape=True
                    ),
                    func.lower(User.full_name).contains(
                        term, autoescape=True
                    ),
                )
            )

        return statement

    def list_users(
        self,
        q: str | None,
        after_id: int | None,
        limit: int,
    ) -> list[User]:

        statement = self._matching(select(User), q)

        if after_id is not None:
            statement = statement.where(User.id > after_id)

        return self.session.exec(
            statement.order_by(User.id).limit(limit)
        ).all()

    def count_users(self, q: str | None) -> int:

        statement = self._matching(
            select(func.count()).select_from(User),
            q,
        )

        return self.session.exec(statement).one()

    def email_taken(
        self,
        email: str | None,
        except_id: int | None = None,
    ) -> bool:

        if email is None:
            return False

        statement = select(User.id).where(User.email == email)

        if except_id is not None:
            statement = statement.where(User.id != except_id)

        return self.session.exec(statement).first() is not None

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def has_other_active_admin(self, user_id: int) -> bool:
        statement = select(User).where(
            User.role == "admin",
            User.is_active == True,  # noqa: E712
            User.id != user_id,
        )

        return self.session.exec(statement).first() is not None

    def delete(self, user: User) -> None:
        self.session.delete(user)

    def get_by_username(self, username: str) -> User | None:
        return self.session.exec(select(User).where(User.username == username)).first()

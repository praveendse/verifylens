"""Isolated tests; never modify data/search_history.db."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine, select

from app.infra.db.models import User
from security.passwords import hash_password, verify_password


def test_password_hashing():
    password = "a-strong-test-password-123"
    stored = hash_password(password)
    assert stored != password
    assert verify_password(password, stored)
    assert not verify_password("incorrect-password", stored)


def test_user_creation_and_unique_username(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test_auth.db'}")
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            admin = User(
                username="admin",
                hashed_password=hash_password("another-test-password-123"),
                role="admin",
            )
            session.add(admin)
            session.commit()
            admin_id = admin.id

        with Session(engine) as session:
            stored = session.exec(select(User).where(User.username == "admin")).one()
            assert stored.id == admin_id
            assert stored.role == "admin"
            assert stored.is_active is True
            assert stored.hashed_password != "another-test-password-123"

            session.add(User(username="admin", hashed_password="hashed-value", role="user"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()

"""Interactively create the FIRST admin account; safe to run as a module.

Usage (from the task03 project root):
    python -m scripts.bootstrap_admin --username admin

Never pass passwords as command-line arguments: they are prompted privately.
"""

import argparse
import getpass
import re

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.infra.db.database import create_db_and_tables, engine
from app.infra.db.models import User
from security.passwords import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first VerifyLens admin")
    parser.add_argument("--username", default="admin", help="3-32 letters, numbers, underscore, period or hyphen")
    args = parser.parse_args()

    username = args.username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,32}", username):
        parser.error("Username must be 3-32 characters: a-z, 0-9, _, . or -")

    create_db_and_tables()

    with Session(engine) as session:
        if session.exec(select(User).where(User.role == "admin")).first():
            raise SystemExit("An admin account already exists. Bootstrap will not create another.")
        if session.exec(select(User).where(User.username == username)).first():
            raise SystemExit("That username already exists.")

        password = getpass.getpass("Choose an admin password (12+ characters): ")
        confirm = getpass.getpass("Confirm admin password: ")

        if len(password) < 12:
            raise SystemExit("Password must contain at least 12 characters.")
        if password != confirm:
            raise SystemExit("Passwords do not match.")
        if username in password.lower():
            raise SystemExit("Password must not contain the username.")

        user = User(
            username=username,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise SystemExit("Username already exists; admin account was not created.") from exc
        session.refresh(user)
        print(f"First admin created: username={user.username}, id={user.id}")
        print("Password was hashed; login endpoints are NOT implemented yet.")


if __name__ == "__main__":
    main()

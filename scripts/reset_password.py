"""Reset any account's password from the server (e.g. the only admin forgot it).

Usage (from the task03 root, or inside the container):
    python -m scripts.reset_password --username admin
    python -m scripts.reset_password --username alice --temporary

The password is prompted privately, never passed on the command line.
All existing sessions of that account are logged out. With --temporary the
user must choose a new password at next login (same as an admin reset).
Requires shell access to the server, which is the trust boundary here.
"""
import argparse
import getpass
import sys

from sqlmodel import Session, select

from app.db.database import engine
from app.db.migrations import upgrade_schema
from app.db.models import User
from app.services.password_reset_service import cancel_unused_tokens
from security.password_policy import password_problem
from security.passwords import hash_password


def reset(username: str, password: str, temporary: bool) -> User:
    username = username.strip().lower()
    problem = password_problem(username, password)
    if problem:
        raise ValueError(problem)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            raise LookupError(f"No account named {username!r}")
        user.hashed_password = hash_password(password)
        user.must_change_password = temporary
        user.token_version += 1
        cancel_unused_tokens(session, user.id)  # old reset links stop working
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset an account's password")
    parser.add_argument("--username", required=True)
    parser.add_argument("--temporary", action="store_true", help="force a change at next login")
    args = parser.parse_args(argv)

    upgrade_schema(engine)  # in case the app hasn't started since an upgrade

    password = getpass.getpass("New password (12+ characters): ")
    if password != getpass.getpass("Confirm new password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        user = reset(args.username, password, args.temporary)
    except (ValueError, LookupError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    state = "must change it at next login" if args.temporary else "can log in with it now"
    print(f"Password reset for {user.username} ({user.role}); they {state}.")
    if not user.is_active:
        print("Note: this account is INACTIVE and still cannot log in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

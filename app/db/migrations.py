"""Idempotent, additive schema upgrades for existing SQLite databases.

Runs at app startup. It only creates missing tables and adds missing columns
(with defaults), so existing rows are kept and it is safe to run repeatedly.
Anything destructive (drop/rename/type change) must NOT go here; take a
backup (scripts/backup_db.py) and write a dedicated script for that.
"""
import logging

from sqlalchemy import Engine, text

from app.db import models  # noqa: F401  (registers tables on SQLModel.metadata)
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# (table, column, column definition)
ADDED_COLUMNS = (
    ("user", "full_name", "TEXT"),
    ("user", "token_version", "INTEGER NOT NULL DEFAULT 0"),
    ("user", "must_change_password", "BOOLEAN NOT NULL DEFAULT 0"),
    ("searchrecord", "user_id", "INTEGER REFERENCES user(id)"),
    ("user", "email", "TEXT"),
)


def upgrade_schema(engine: Engine) -> list[str]:
    """Bring the database up to date. Returns the columns it added."""
    SQLModel.metadata.create_all(engine)  # new tables only; never alters
    added = []
    with engine.begin() as conn:
        for table, column, definition in ADDED_COLUMNS:
            existing = {row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))}
            if column not in existing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}'))
                added.append(f"{table}.{column}")
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_searchrecord_user_id ON searchrecord(user_id)"))
        # Same name as the Index in models.User, so new and upgraded databases match.
        conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ux_user_email ON "user"(email)'))
    if added:
        logger.warning("Database schema upgraded, added: %s", ", ".join(added))
    return added

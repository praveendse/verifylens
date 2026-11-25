from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine

from app.config import Settings

DB_FILE = Settings().database_path.expanduser().resolve()

DB_FILE.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    # WAL: readers don't block the writer, so history pages stay responsive
    # while a search is being saved. Requires a local disk (not NFS/SMB).
    cursor.execute("PRAGMA journal_mode=WAL")
    # Wait up to 5s for a lock instead of failing with "database is locked".
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def get_session_factory():
    """For work that runs after the response (background tasks), when the
    request's own session is already closed. Overridden in tests."""
    return lambda: Session(engine)

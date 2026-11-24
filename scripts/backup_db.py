"""Safe online backup of the SQLite database.

Usage (from the task03 root, app may keep running):
    python -m scripts.backup_db                       # -> backups/, keep 14
    python -m scripts.backup_db --dest /mnt/backups --keep 30

Do NOT back up by copying search_history.db with cp: in WAL mode recent
writes live in the -wal file, and a copy taken mid-write can be corrupt.
This uses SQLite's backup API, which produces a consistent snapshot, then
runs an integrity check on the copy before keeping it.

Schedule it, e.g. daily at 02:00 via cron:
    0 2 * * * cd /path/to/task03 && /path/to/python -m scripts.backup_db

Restore: stop the app, copy a backup file over DATABASE_PATH, delete any
leftover search_history.db-wal / -shm files, start the app.

Backups contain user password hashes and search history: store them with
the same access restrictions as the live database.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PREFIX = "search_history-"
SUFFIX = ".db"


def backup(src: Path, dest_dir: Path, keep: int) -> Path:
    if not src.is_file():
        raise FileNotFoundError(f"Database not found: {src}")
    if keep < 1:
        raise ValueError("--keep must be at least 1")

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    final = dest_dir / f"{PREFIX}{stamp}{SUFFIX}"
    tmp = final.with_suffix(".tmp")

    try:
        source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        try:
            target = sqlite3.connect(tmp)
            try:
                source.backup(target)
                result = target.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise RuntimeError(f"Integrity check failed on backup: {result}")
            finally:
                target.close()
        finally:
            source.close()
        os.chmod(tmp, 0o600)  # contains password hashes
        tmp.replace(final)  # only complete, verified files get the final name
    finally:
        tmp.unlink(missing_ok=True)

    old = sorted(dest_dir.glob(f"{PREFIX}*{SUFFIX}"))[:-keep]
    for path in old:
        path.unlink()
    return final


def main(argv: list[str] | None = None) -> int:
    from app.config import Settings

    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, default=Settings().database_path)
    # BACKUP_DIR is set to /backups in the Docker image (a mounted folder).
    default_dest = Path(os.environ.get("BACKUP_DIR") or root / "backups")
    parser.add_argument("--dest", type=Path, default=default_dest)
    parser.add_argument("--keep", type=int, default=14, help="number of backups to keep")
    args = parser.parse_args(argv)

    try:
        path = backup(args.src, args.dest, args.keep)
    except Exception as exc:  # non-zero exit so cron/monitoring notices
        print(f"BACKUP FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Backup written: {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import sqlite3
from pathlib import Path

import pytest

from scripts.backup_db import backup, main


def make_db(path: Path, rows: int) -> None:
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS t (n INTEGER)")
    con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(rows)])
    con.commit()
    con.close()


def count(path: Path) -> int:
    con = sqlite3.connect(path)
    try:
        return con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    finally:
        con.close()


def test_backup_includes_uncheckpointed_wal_writes(tmp_path):
    src = tmp_path / "live.db"
    make_db(src, 3)

    # Keep a writer open so recent rows sit in the -wal file, as in production.
    writer = sqlite3.connect(src)
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO t VALUES (99)")
    writer.commit()
    try:
        out = backup(src, tmp_path / "bk", keep=5)
    finally:
        writer.close()

    assert count(out) == 4
    assert oct(out.stat().st_mode & 0o777) == "0o600"
    assert not list((tmp_path / "bk").glob("*.tmp"))


def test_keeps_only_newest_n(tmp_path):
    src = tmp_path / "live.db"
    make_db(src, 1)
    dest = tmp_path / "bk"
    made = [backup(src, dest, keep=2) for _ in range(4)]

    remaining = sorted(dest.glob("*.db"))
    assert remaining == sorted(made[-2:])


def test_missing_source_fails_with_exit_code(tmp_path, capsys):
    code = main(["--src", str(tmp_path / "nope.db"), "--dest", str(tmp_path / "bk")])
    assert code == 1
    assert "BACKUP FAILED" in capsys.readouterr().err
    assert not (tmp_path / "bk").exists() or not list((tmp_path / "bk").iterdir())


def test_rejects_keep_zero(tmp_path):
    src = tmp_path / "live.db"
    make_db(src, 1)
    with pytest.raises(ValueError):
        backup(src, tmp_path / "bk", keep=0)

# -*- coding: utf-8 -*-
"""Tests für den SQLite-Betrieb: WAL-Modus und Backup (``backend.backup``).

Aufruf aus dem Projekt-Root:  python tests/test_backup.py

Nutzt eine temporäre SQLite-Datei; die Anwendungsdatenbank (housing.db) wird
nicht angefasst.
"""
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP = tempfile.mkdtemp()
DB_FILE = Path(TMP) / "housing.db"
# Muss vor dem Import von backend.database gesetzt sein.
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.as_posix()}"

from sqlalchemy import text  # noqa: E402

from backend import backup, database, migrate, models  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def test_sqlite_settings():
    print("SQLite-Einstellungen")
    migrate.upgrade()
    with database.engine.connect() as conn:
        check("WAL-Modus aktiv", conn.execute(text("PRAGMA journal_mode")).scalar() == "wal")
        check("busy_timeout gesetzt",
              conn.execute(text("PRAGMA busy_timeout")).scalar() == database.SQLITE_BUSY_TIMEOUT_MS)


def test_backup_while_running():
    print("Backup bei offener Verbindung")
    db = database.SessionLocal()
    db.add(models.Household(name="Backup-Test"))
    db.commit()
    # Die Sitzung bleibt offen, wie im laufenden Dienst; die Änderung steht noch im WAL.
    target_dir = Path(TMP) / "backups"
    path = backup.create_backup(target_dir, label="daily")
    db.close()

    check("Datei angelegt", path.exists() and path.name.startswith("housing-daily-"))
    with sqlite3.connect(path) as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM households")]
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    check("enthält die Daten aus dem WAL", "Backup-Test" in names, str(names))
    check("enthält die Migrationsrevision", revision == migrate.head_revision())
    check("keine Teildatei übrig", not list(target_dir.glob("*.partial")))


def test_prune():
    print("Aufbewahrung")
    target_dir = Path(TMP) / "prune"
    target_dir.mkdir()
    old_daily = target_dir / "housing-daily-20000101-000000.db"
    old_pre = target_dir / "housing-pre-migration-20000101-000000.db"
    for path in (old_daily, old_pre):
        path.write_bytes(b"")
        past = time.time() - 30 * 86400
        os.utime(path, (past, past))
    fresh = backup.create_backup(target_dir, label="daily")

    removed = backup.prune_backups(target_dir, "daily", keep_days=14)
    check("altes Backup desselben Labels gelöscht", removed == [old_daily], str(removed))
    check("anderes Label bleibt", old_pre.exists())
    check("neues Backup bleibt", fresh.exists())


def test_missing_database():
    print("Fehlende Datenbank")
    try:
        backup.create_backup(Path(TMP) / "missing", url=f"sqlite:///{(Path(TMP) / 'gibtsnicht.db').as_posix()}")
        check("fehlende Datei wird gemeldet", False)
    except RuntimeError:
        check("fehlende Datei wird gemeldet", True)


if __name__ == "__main__":
    test_sqlite_settings()
    test_backup_while_running()
    test_prune()
    test_missing_database()
    database.engine.dispose()
    if failures:
        print(f"\n{len(failures)} Fehler")
        sys.exit(1)
    print("\nAlle Tests bestanden")

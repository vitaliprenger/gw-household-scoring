"""Konsistentes Backup der SQLite-Datenbank.

Aufruf aus dem Projekt-Root::

    python -m backend.backup <verzeichnis> [--label daily] [--keep-days 14]

Die Datenbank kommt wie in der Anwendung aus ``DATABASE_URL``. Das Backup nutzt die
Backup-API von SQLite und ist deshalb auch bei laufendem Dienst konsistent -- ein
einfaches Kopieren der Datei ist es im WAL-Modus nicht.

Ergebnis ist ``<verzeichnis>/housing-<label>-<JJJJMMTT-HHMMSS>.db``; der Pfad wird auf
stdout ausgegeben. Mit ``--keep-days`` werden ältere Backups **desselben Labels**
gelöscht. Exit-Code 0 bei Erfolg, sonst ungleich 0.
"""
import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from . import database


def database_path(url: str | None = None) -> Path:
    return Path(make_url(url or database.SQLALCHEMY_DATABASE_URL).database).resolve()


def create_backup(target_dir: Path, label: str = "manual", url: str | None = None) -> Path:
    source_path = database_path(url)
    if not source_path.exists():
        raise RuntimeError(f"Datenbank {source_path} existiert nicht.")

    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"housing-{label}-{stamp}.db"
    partial = target.with_suffix(".db.partial")

    # Kein mode=ro: im WAL-Modus braucht auch ein Leser Schreibzugriff auf die -shm-Datei.
    source = sqlite3.connect(source_path, timeout=database.SQLITE_BUSY_TIMEOUT_MS / 1000)
    try:
        dest = sqlite3.connect(partial)
        try:
            source.backup(dest)
            result = dest.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dest.close()
    finally:
        source.close()

    if result != "ok":
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Integritätsprüfung des Backups fehlgeschlagen: {result}")
    os.chmod(partial, 0o600)
    partial.replace(target)
    return target


def prune_backups(target_dir: Path, label: str, keep_days: int) -> list[Path]:
    cutoff = time.time() - keep_days * 86400
    removed = []
    for path in target_dir.glob(f"housing-{label}-*.db"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path, help="Zielverzeichnis")
    parser.add_argument("--label", default="manual", help="Teil des Dateinamens, z. B. daily oder pre-migration")
    parser.add_argument("--keep-days", type=int, default=None, help="ältere Backups dieses Labels löschen")
    args = parser.parse_args(argv)

    target = create_backup(args.directory, args.label)
    print(target)
    if args.keep_days is not None:
        for path in prune_backups(args.directory, args.label, args.keep_days):
            print(f"gelöscht: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Datenbankmigrationen über Alembic.

Aufruf aus dem Projekt-Root::

    python -m backend.migrate            # Datenbank auf den neuesten Stand heben
    python -m backend.migrate --check    # Exit-Code 1, wenn Migrationen ausstehen
    python -m backend.migrate --current  # aktuelle und neueste Revision ausgeben

Die Datenbank-URL kommt wie in der Anwendung aus ``DATABASE_URL``.

Drei Ausgangslagen werden erkannt:

- **leere Datenbank** -- alle Revisionen laufen ab der Ausgangsrevision,
- **Datenbank unter Alembic** (Tabelle ``alembic_version``) -- nur ausstehende Revisionen laufen,
- **SQLite-Entwicklungsdatenbank aus der Zeit vor Alembic** -- die Altmigration
  (``legacy_migrations``) hebt sie auf die Ausgangsrevision, danach wird gestempelt.
"""
import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from . import database, legacy_migrations

BASELINE_REVISION = "0001_baseline"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(engine: Engine | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Die Engine wird durchgereicht, damit Tests eine eigene Datenbank migrieren können.
    cfg.attributes["engine"] = engine or database.engine
    return cfg


def head_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(engine: Engine | None = None) -> str | None:
    with (engine or database.engine).connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def upgrade(engine: Engine | None = None) -> None:
    engine = engine or database.engine
    cfg = alembic_config(engine)
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    if tables and current_revision(engine) is None:
        legacy_migrations.upgrade_legacy_sqlite(engine)
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")


def ensure_up_to_date(engine: Engine | None = None) -> None:
    current, head = current_revision(engine), head_revision()
    if current != head:
        raise RuntimeError(
            f"Datenbank steht auf Revision {current}, erwartet wird {head}. "
            "Zuerst 'python -m backend.migrate' ausführen."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="nur prüfen, ob Migrationen ausstehen")
    group.add_argument("--current", action="store_true", help="aktuelle und neueste Revision ausgeben")
    args = parser.parse_args(argv)

    if args.current:
        print(f"current={current_revision()} head={head_revision()}")
        return 0
    if args.check:
        current, head = current_revision(), head_revision()
        if current != head:
            print(f"Migrationen ausstehend: current={current} head={head}")
            return 1
        print(f"Datenbank aktuell: {head}")
        return 0

    before = current_revision()
    upgrade()
    after = current_revision()
    print(f"Migration abgeschlossen: {before} -> {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

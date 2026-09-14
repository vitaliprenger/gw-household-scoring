# -*- coding: utf-8 -*-
"""Tests für die Datenbankmigrationen (``backend.migrate``).

Aufruf aus dem Projekt-Root:  python tests/test_migrations.py

Nutzt temporäre SQLite-Dateien; die Anwendungsdatenbank (housing.db) wird
nicht angefasst.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend import migrate, models, scoring, services

failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def make_engine(tmpdir: str, name: str):
    return create_engine(f"sqlite:///{os.path.join(tmpdir, name)}")


def schema_diff(engine) -> list:
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), models.Base.metadata)


def test_empty_database(tmpdir):
    print("Leere Datenbank")
    engine = make_engine(tmpdir, "empty.db")
    migrate.upgrade(engine)
    check("steht auf der neuesten Revision",
          migrate.current_revision(engine) == migrate.head_revision())
    diff = schema_diff(engine)
    check("Schema entspricht den Modellen", not diff, str(diff))

    migrate.upgrade(engine)
    check("zweiter Lauf ist ein No-op", migrate.current_revision(engine) == migrate.head_revision())
    migrate.ensure_up_to_date(engine)
    engine.dispose()


def test_legacy_database(tmpdir):
    print("SQLite-Datenbank aus der Zeit vor Alembic")
    engine = make_engine(tmpdir, "legacy.db")
    # Alter Stand: Wohnungswunsch am Haushalt, Bewerbung mit Wohnungs-Link.
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE households (id INTEGER PRIMARY KEY, name TEXT, application_date DATETIME,"
            " engagement_score REAL, total_score REAL, is_resident BOOLEAN DEFAULT 0,"
            " desired_apartment_size TEXT, desired_apartment_type TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE people (id INTEGER PRIMARY KEY, household_id INTEGER, first_name TEXT,"
            " last_name TEXT, birth_date DATETIME, gender TEXT, occupation_type TEXT,"
            " education_level TEXT, cultural_background TEXT, special_needs BOOLEAN)"
        ))
        conn.execute(text(
            "CREATE TABLE apartments (id INTEGER PRIMARY KEY, unit_number TEXT UNIQUE,"
            " size_rooms REAL, funding_type TEXT, apartment_type TEXT, floor TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE applications (id INTEGER PRIMARY KEY, household_id INTEGER,"
            " apartment_id INTEGER REFERENCES apartments(id), status TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO households (id, name, is_resident, desired_apartment_size, desired_apartment_type)"
            " VALUES (1, 'Muster', 0, '3', 'Standard Wohnungstypen')"
        ))
        conn.execute(text(
            "INSERT INTO people (id, household_id, first_name, last_name, special_needs)"
            " VALUES (1, 1, 'Anna', 'Muster', 1)"
        ))
        conn.execute(text(
            "INSERT INTO apartments (id, unit_number, size_rooms, funding_type, apartment_type)"
            " VALUES (1, 'P.101', 3.5, 'WBS A', 'Mini WG')"
        ))

    migrate.upgrade(engine)
    check("gestempelt und auf neuester Revision",
          migrate.current_revision(engine) == migrate.head_revision())
    # Typnamen weichen bei alten SQLite-Tabellen ab (TEXT statt VARCHAR); maßgeblich
    # ist, dass alle Tabellen und Spalten der Modelle vorhanden sind.
    inspector = inspect(engine)
    missing = [
        f"{table.name}.{column.name}"
        for table in models.Base.metadata.sorted_tables
        for column in table.columns
        if column.name not in {c["name"] for c in inspector.get_columns(table.name)}
    ]
    check("alle Spalten der Modelle vorhanden", not missing, str(missing))

    with engine.connect() as conn:
        check("Personendaten bleiben erhalten",
              conn.execute(text("SELECT special_needs FROM people WHERE id = 1")).scalar() == "Ja")
        check("Wohnungsdaten werden umgesetzt",
              conn.execute(text("SELECT size_rooms, is_small FROM apartments WHERE id = 1")).one()
              == (3, 1))
        check("Wunsch wandert in die Bewerbung",
              conn.execute(text("SELECT count(*) FROM applications WHERE household_id = 1")).scalar() == 1)
    check("Altspalten am Haushalt entfernt",
          "desired_apartment_size" not in {c["name"] for c in inspect(engine).get_columns("households")})
    engine.dispose()


def test_application_starts_on_migrated_database(tmpdir):
    print("Startinitialisierung auf migrierter Datenbank")
    engine = make_engine(tmpdir, "start.db")
    migrate.upgrade(engine)
    db = sessionmaker(bind=engine)()
    scoring.initialize_config(db)
    services.seed_apartments(db)
    check("Wohnungsstammdaten angelegt", db.query(models.Apartment).count() > 0)
    check("Konfiguration angelegt", db.query(models.ScoringConfig).count() > 0)
    db.close()
    engine.dispose()


def test_outdated_database_is_detected(tmpdir):
    print("Veraltete Datenbank")
    engine = make_engine(tmpdir, "outdated.db")
    try:
        migrate.ensure_up_to_date(engine)
        check("fehlende Migration wird erkannt", False)
    except RuntimeError:
        check("fehlende Migration wird erkannt", True)
    engine.dispose()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        test_empty_database(tmp)
        test_legacy_database(tmp)
        test_application_starts_on_migrated_database(tmp)
        test_outdated_database_is_detected(tmp)
    if failures:
        print(f"\n{len(failures)} Fehler")
        sys.exit(1)
    print("\nAlle Tests bestanden")

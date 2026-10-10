# -*- coding: utf-8 -*-
"""Tests für das Anlegen einer Person von Hand.

Aufruf aus dem Projekt-Root:  python tests/test_persons.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, schemas, services

failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def check_equal(label: str, actual, expected):
    check(label, actual == expected, f"(erwartet {expected!r}, war {actual!r})")


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    # Wie die Anwendung (backend/database.py): ohne Autoflush.
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


# ---------------------------------------------------------------------------

def test_create_person_without_household():
    print("\n== Person anlegen: ohne Haushalt ==")
    db = make_session()

    person = services.create_person(db, schemas.PersonCreate(
        first_name="Ines", last_name="Ebert", member_number="301",
        birth_date=datetime(1991, 4, 12), member_since=datetime(2025, 10, 1)))

    stored = db.query(models.Person).one()
    check_equal("gespeichert", stored.id, person.id)
    check_equal("Name", (stored.first_name, stored.last_name), ("Ines", "Ebert"))
    check_equal("optionale Angaben",
                (stored.member_number, stored.birth_date, stored.member_since),
                ("301", datetime(1991, 4, 12), datetime(2025, 10, 1)))
    check_equal("ohne Haushalt", stored.household_id, None)
    check("Zeitpunkt der letzten Bearbeitung gesetzt", stored.updated_at is not None)
    db.close()


def test_create_person_in_household():
    print("\n== Person anlegen: direkt im Haushalt ==")
    db = make_session()
    household = models.Household(name="Sommer")
    db.add(household)
    db.commit()

    person = services.create_person(db, schemas.PersonCreate(
        first_name="Mia", last_name="Sommer", household_id=household.id))

    db.refresh(household)
    check_equal("gehört zum Haushalt", person.household_id, household.id)
    check_equal("Haushaltsgröße stimmt sofort", services.member_count(household), 1)
    db.close()


def test_create_person_in_unknown_household():
    print("\n== Person anlegen: unbekannter Haushalt ==")
    db = make_session()

    try:
        services.create_person(db, schemas.PersonCreate(
            first_name="Mia", last_name="Sommer", household_id=999))
        check("unbekannter Haushalt ist ein Fehler", False)
    except ValueError:
        check("unbekannter Haushalt ist ein Fehler", True)
    check_equal("nichts gespeichert", db.query(models.Person).count(), 0)
    db.close()


def test_create_person_needs_both_names():
    print("\n== Person anlegen: Vor- und Nachname sind Pflicht ==")
    for label, names in [("ohne Vornamen", {"first_name": "  ", "last_name": "Sommer"}),
                         ("ohne Nachnamen", {"first_name": "Mia", "last_name": ""})]:
        try:
            schemas.PersonCreate(**names)
            check(f"{label} ist ein Fehler", False)
        except ValueError:
            check(f"{label} ist ein Fehler", True)

    created = schemas.PersonCreate(first_name=" Mia ", last_name=" Sommer ")
    check_equal("Leerzeichen am Rand entfallen",
                (created.first_name, created.last_name), ("Mia", "Sommer"))


if __name__ == "__main__":
    test_create_person_without_household()
    test_create_person_in_household()
    test_create_person_in_unknown_household()
    test_create_person_needs_both_names()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

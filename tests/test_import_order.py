# -*- coding: utf-8 -*-
"""Tests für die Reihenfolge der Importe.

1. vCard  – legt Personen an, Haushalte nur bei Wohnungszuordnung
2. Individualbogen – ergänzt vorhandene Personen, legt keine an
3. Haushaltsbogen  – ergänzt vorhandene Haushalte, legt keine an

Aufruf aus dem Projekt-Root:  python tests/test_import_order.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import import_service, models, schemas, services
from backend import vcf_import_service as V
from backend.import_service import ImportSession, import_sessions

from test_vcf_import import SAMPLE  # noqa: E402  (gleiche vCard-Beispieldatei)

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
    return sessionmaker(bind=engine)()


def wizard_decisions(analysis: schemas.VcfAnalysisResponse) -> list[schemas.VcfDecision]:
    """Die Vorbelegung des Import-Assistenten nachbilden."""
    decisions = []
    for hh in analysis.households:
        if hh.already_imported:
            action = "skip"
        elif hh.match_result.matched_household_id:
            action = "update"
        else:
            action = "create"
        decisions.append(schemas.VcfDecision(
            temp_id=hh.temp_id,
            action=action,
            target_household_id=hh.match_result.matched_household_id,
            excluded_person_temp_ids=[],
        ))
    return decisions


def import_sample(db) -> schemas.VcfCommitResponse:
    analysis = V.analyze_vcf(SAMPLE.encode("utf-8"), db)
    return V.commit_vcf(
        schemas.VcfCommitRequest(
            session_id=analysis.session_id,
            decisions=wizard_decisions(analysis),
        ),
        db,
    )


def person(db, first_name: str):
    return db.query(models.Person).filter(models.Person.first_name == first_name).first()


# ---------------------------------------------------------------------------
# 1. vCard-Import
# ---------------------------------------------------------------------------

def test_vcf_creates_every_person():
    print("\n== vCard: alle Personen anlegen ==")
    db = make_session()
    services.seed_apartments(db)
    result = import_sample(db)

    people = db.query(models.Person).all()
    # Gregor, Fredericke + 2 Kinder (W.002); Nina; Olaf + Mads + Jarle
    check_equal("acht Personen angelegt", len(people), 8)
    check_equal("Zähler persons_created", result.persons_created, 8)

    check_equal("genau ein Haushalt", db.query(models.Household).count(), 1)
    check_equal("Haushalte angelegt (Zähler)", result.households_created, 1)

    hh = db.query(models.Household).first()
    check_equal("Haushalt trägt die Wohnungsnummer", hh.apartment_unit, "W.002")
    check_equal("vier Personen im Haushalt", len(hh.people), 4)
    check_equal(
        "Wohnung W.002 zugeordnet",
        db.query(models.Apartment).filter(
            models.Apartment.unit_number == "W.002").first().household_id,
        hh.id,
    )
    check("Haushalt ist Bewohner", hh.is_resident)

    ohne_haushalt = [p for p in people if p.household_id is None]
    check_equal(
        "Personen ohne Wohnungszuordnung bleiben ohne Haushalt",
        sorted(p.first_name for p in ohne_haushalt),
        ["Jarle", "Mads", "Nina", "Olaf"],
    )
    check_equal("Zähler persons_without_household", result.persons_without_household, 4)


def test_vcf_creates_children_from_notes():
    print("\n== vCard: Kinder aus den Kontaktnotizen ==")
    db = make_session()
    import_sample(db)

    jonathan = person(db, "Jonathan Rye")
    check("Kind aus der Notiz angelegt", jonathan is not None)
    if jonathan:
        check_equal("Geburtsdatum des Kindes", jonathan.birth_date, datetime(2021, 1, 30))
        check("Kind gehört zum Haushalt", jonathan.household_id is not None)
        check_equal("Kind ohne Mitgliedsnummer", jonathan.member_number, None)

    # Kinder ohne Wohnungszuordnung entstehen ebenfalls, nur ohne Haushalt
    mads = person(db, "Mads")
    check("Kind ohne Wohnung angelegt", mads is not None)
    if mads:
        check_equal("Kind ohne Wohnung hat keinen Haushalt", mads.household_id, None)


def test_vcf_overwrites_but_keeps_missing():
    print("\n== vCard: überschreibt, löscht aber nichts ==")
    db = make_session()
    db.add(models.Person(
        first_name="Gregor", last_name="Matt",
        member_number="359",
        gender="f",                       # falsch -> wird überschrieben
        birth_date=datetime(1970, 1, 1),  # falsch -> wird überschrieben
        occupation_type="5",              # nicht in der vCard -> bleibt
        education_level="7",              # nicht in der vCard -> bleibt
    ))
    db.commit()

    result = import_sample(db)

    gregor = person(db, "Gregor")
    check_equal("keine Dublette angelegt", db.query(models.Person).filter(
        models.Person.first_name == "Gregor").count(), 1)
    check_equal("Geschlecht überschrieben", gregor.gender, "m")
    check_equal("Geburtsdatum überschrieben", gregor.birth_date, datetime(1989, 5, 3))
    check_equal("Mitglied seit ergänzt", gregor.member_since, datetime(2023, 1, 28))
    check_equal("Haupttätigkeit bleibt erhalten", gregor.occupation_type, "5")
    check_equal("Bildungsabschluss bleibt erhalten", gregor.education_level, "7")
    check("vorhandene Person dem Haushalt zugeordnet", gregor.household_id is not None)
    check_equal("Zähler persons_assigned", result.persons_assigned, 1)
    check_equal("nur sieben Personen neu", result.persons_created, 7)


def test_vcf_is_idempotent():
    print("\n== vCard: zweiter Lauf legt nichts doppelt an ==")
    db = make_session()
    import_sample(db)
    before = db.query(models.Person).count()
    households_before = db.query(models.Household).count()

    import_sample(db)

    check_equal("Personenzahl unverändert", db.query(models.Person).count(), before)
    check_equal("Haushaltszahl unverändert",
                db.query(models.Household).count(), households_before)


# ---------------------------------------------------------------------------
# 2. Individualbogen
# ---------------------------------------------------------------------------

def individual_row(**overrides) -> dict:
    row = {
        "temp_id": str(uuid.uuid4()),
        "name": "Nina Beispiel",
        "first_name": "Nina",
        "last_name": "Beispiel",
        "member_number": None,
        "birth_date": "1990-07-15",
        "timestamp_str": "2026-02-01 10:00",
        "timestamp": datetime(2026, 2, 1, 10, 0),
        "gender": "f",
        "occupation": "2",
        "education": "6",
        "life_situation": "nein",
        "social_diversity": None,
    }
    row.update(overrides)
    return row


def test_individual_matches_person_without_household():
    print("\n== Individualbogen: findet Personen ohne Haushalt ==")
    db = make_session()
    import_sample(db)

    nina = person(db, "Nina")
    check_equal("Nina hat keinen Haushalt", nina.household_id, None)

    match = import_service.match_individual_to_person(individual_row(), db)
    check_equal("Person ohne Haushalt wird gefunden", match.matched_household_id, nina.id)


def test_individual_never_creates():
    print("\n== Individualbogen: legt keine Personen an ==")
    db = make_session()
    import_sample(db)
    before = db.query(models.Person).count()

    matched = individual_row()
    unmatched = individual_row(name="Frieda Fremd", first_name="Frieda",
                               last_name="Fremd", birth_date="1975-03-03")
    session = ImportSession("individual", [matched, unmatched], {})
    import_sessions[session.id] = session

    nina = person(db, "Nina")
    result = import_service.commit_individual_bogen(schemas.IndividualCommitRequest(
        session_id=session.id,
        decisions=[
            schemas.IndividualDecision(
                temp_id=matched["temp_id"], action="update", target_person_id=nina.id),
            # Ohne Treffer: der Assistent kann nur noch überspringen
            schemas.IndividualDecision(temp_id=unmatched["temp_id"], action="update"),
        ],
    ), db)

    check_equal("keine neue Person", db.query(models.Person).count(), before)
    check_equal("eine Person ergänzt", result.updated, 1)
    check_equal("ohne Treffer nicht übernommen", result.skipped_no_match, 1)

    nina = person(db, "Nina")
    check_equal("Geschlecht ergänzt", nina.gender, "f")
    check_equal("Haupttätigkeit ergänzt", nina.occupation_type, "2")
    check_equal("Bildungsabschluss ergänzt", nina.education_level, "6")


# ---------------------------------------------------------------------------
# 3. Haushaltsbogen
# ---------------------------------------------------------------------------

def household_row(**overrides) -> dict:
    row = {
        "temp_id": str(uuid.uuid4()),
        "timestamp_str": "2026-02-01 10:00",
        "timestamp": datetime(2026, 2, 1, 10, 0),
        "wbs_status": "WBS A",
        "financial_status": "knapp",
        "declared_member_count": 4,
        "wheelchair_accessible": False,
        "desired_apartment_type": ["Standard Wohnungstypen"],
        "desired_apartment_size": "4 Zimmer",
        "pets_count": 1,
        "pets_info": "Katze",
        "persons": [
            {"name": "Gregor Matt", "first_name": "Gregor", "last_name": "Matt",
             "member_number": "359", "birth_date": "1989-05-03"},
        ],
    }
    row.update(overrides)
    return row


def test_household_bogen_never_creates():
    print("\n== Haushaltsbogen: legt keine Haushalte an ==")
    db = make_session()
    import_sample(db)
    before = db.query(models.Household).count()

    matched = household_row()
    unmatched = household_row(persons=[
        {"name": "Frieda Fremd", "first_name": "Frieda", "last_name": "Fremd",
         "member_number": None, "birth_date": None},
    ])
    session = ImportSession("household", [matched, unmatched], {})
    import_sessions[session.id] = session

    hh = db.query(models.Household).first()
    result = import_service.commit_household_bogen(schemas.HHCommitRequest(
        session_id=session.id,
        decisions=[
            schemas.HouseholdDecision(
                temp_id=matched["temp_id"], action="update", target_household_id=hh.id),
            schemas.HouseholdDecision(temp_id=unmatched["temp_id"], action="update"),
        ],
    ), db)

    check_equal("kein neuer Haushalt", db.query(models.Household).count(), before)
    check_equal("ein Haushalt ergänzt", result.updated, 1)
    check_equal("ohne Treffer nicht übernommen", result.skipped_no_match, 1)

    hh = db.query(models.Household).first()
    check_equal("WBS-Status ergänzt", hh.wbs_status, "WBS A")
    check_equal("Wohnungswunsch ergänzt", hh.desired_apartment_size, "4 Zimmer")
    check_equal("Haustiere ergänzt", hh.pets_count, 1)


def test_household_bogen_reuses_existing_persons():
    print("\n== Haushaltsbogen: keine Personendubletten ==")
    db = make_session()
    import_sample(db)
    hh = db.query(models.Household).first()
    before = len(hh.people)

    # Andere Schreibweise des Vornamens, gleiche Mitgliedsnummer
    raw = household_row(persons=[
        {"name": "G. Matt", "first_name": "Gregor Ludwig", "last_name": "Matt",
         "member_number": "359", "birth_date": "1989-05-03"},
    ])
    session = ImportSession("household", [raw], {})
    import_sessions[session.id] = session

    import_service.commit_household_bogen(schemas.HHCommitRequest(
        session_id=session.id,
        decisions=[schemas.HouseholdDecision(
            temp_id=raw["temp_id"], action="update", target_household_id=hh.id)],
    ), db)

    db.refresh(hh)
    check_equal("Haushaltsgröße unverändert", len(hh.people), before)


# ---------------------------------------------------------------------------

def run_tests():
    print("--- Tests zur Import-Reihenfolge ---")
    for test in (
        test_vcf_creates_every_person,
        test_vcf_creates_children_from_notes,
        test_vcf_overwrites_but_keeps_missing,
        test_vcf_is_idempotent,
        test_individual_matches_person_without_household,
        test_individual_never_creates,
        test_household_bogen_never_creates,
        test_household_bogen_reuses_existing_persons,
    ):
        test()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Alle Tests bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())

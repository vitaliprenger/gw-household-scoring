# -*- coding: utf-8 -*-
"""Tests für den Import des Haushaltsbogens.

Geprüft wird über Analyse und Übernehmen: Eine Exportdatei entsteht im
Speicher, die Analyse liefert die Vorschau, und nach dem Übernehmen der
Entscheidungen zählt der Datenbestand. Die Anwendungsdatenbank (housing.db)
wird nicht angefasst.

Aufruf aus dem Projekt-Root:  python tests/test_household_bogen.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import import_service, models, schemas, services

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


def household_xlsx(*rows: dict) -> bytes:
    """Export des Haushaltsbogens mit den Spalten des Fragebogens."""
    frame = pd.DataFrame([{
        "Zeitstempel": "2026-09-01T10:00:00+02:00",
        "Datenschutzhinweis": "Mir ist klar, dass meine Angaben gespeichert werden.",
        "Person 1 (Name)": "",
        "Person 1 (Mitgliedsnummer)": "",
        "Person 1 (Geburtsdatum)": "",
        "Haushaltsmitglieder": "1",
        "Wohnberechtigungsschein": "kein WBS",
        "Wohnungsgröße": "",
        "Wohnungsart": "",
        "Absenden?": "Ja",
        **row,
    } for row in rows])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def analyze(db, *rows: dict) -> schemas.HHAnalysisResponse:
    return import_service.analyze_household_bogen(household_xlsx(*rows), db)


def commit(db, analysis, *decisions) -> schemas.HHCommitResponse:
    return import_service.commit_household_bogen(schemas.HHCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.HouseholdDecision(**decision) for decision in decisions],
    ), db)


def add_household(db, name: str, *people: dict, apartment: str | None = None) -> models.Household:
    household = models.Household(name=name)
    db.add(household)
    db.flush()
    for fields in people:
        db.add(models.Person(household_id=household.id, **fields))
    if apartment:
        unit = models.Apartment(unit_number=apartment, size_rooms=3, funding_type="frei")
        db.add(unit)
        db.flush()
        services.assign_household(db, unit, household.id)
    db.commit()
    return household


def applications_of(db, household) -> list[models.Application]:
    return db.query(models.Application).filter(
        models.Application.household_id == household.id).all()


# ---------------------------------------------------------------------------

def test_resident_household_gets_no_application():
    print("\n== Haushaltsbogen: Bewohner-Haushalt bekommt keine Bewerbung ==")
    db = make_session()
    residents = add_household(
        db, "Ebert", {"first_name": "Ines", "last_name": "Ebert", "member_number": "301"},
        apartment="A.104")

    analysis = analyze(db, {
        "Person 1 (Name)": "Ebert, Ines", "Person 1 (Mitgliedsnummer)": "301",
        "Wohnberechtigungsschein": "Einkommensgruppe A", "Wohnungsgröße": "3 Zimmer"})
    preview = analysis.households[0]
    check("Vorschau weist den nicht übernommenen Wunsch aus", preview.wish_not_applied)

    result = commit(db, analysis, {
        "temp_id": preview.temp_id, "action": "update", "target_household_id": residents.id})

    db.refresh(residents)
    check_equal("Selbstauskunft übernommen", residents.wbs_status, "WBS A")
    check_equal("keine Bewerbung angelegt", applications_of(db, residents), [])
    check_equal("Zusammenfassung nennt den Haushalt", result.wishes_not_applied, ["Ebert"])
    db.close()


def test_resident_household_keeps_existing_application():
    print("\n== Haushaltsbogen: vorhandene Bewerbung eines Bewohner-Haushalts bleibt ==")
    db = make_session()
    residents = add_household(
        db, "Ebert", {"first_name": "Ines", "last_name": "Ebert", "member_number": "301"},
        apartment="A.104")
    old_wishes = [{"size_rooms": 2, "funding_type": None, "apartment_category": None}]
    db.add(models.Application(household_id=residents.id, kind="wartepool",
                              status="offen", wishes=old_wishes))
    db.commit()

    # Ein Bogen ohne Wunsch würde bei einem Wartepool-Haushalt den Wunsch entfernen.
    analysis = analyze(db, {
        "Person 1 (Name)": "Ebert, Ines", "Person 1 (Mitgliedsnummer)": "301"})
    preview = analysis.households[0]
    changes = preview.existing_data_changes
    check("keine Löschung des Wunsches angekündigt",
          not changes or all(c.field != import_service.WISH_LABEL for c in changes.data_removals))
    check("ohne Wunsch im Bogen kein Hinweis", not preview.wish_not_applied)

    with_wish = analyze(db, {
        "Zeitstempel": "2026-09-02T10:00:00+02:00",
        "Person 1 (Name)": "Ebert, Ines", "Person 1 (Mitgliedsnummer)": "301",
        "Wohnungsgröße": "4 Zimmer"})
    commit(db, with_wish, {
        "temp_id": with_wish.households[0].temp_id, "action": "update",
        "target_household_id": residents.id})

    application = applications_of(db, residents)[0]
    check_equal("Wunsch der vorhandenen Bewerbung unverändert", application.wishes, old_wishes)
    check_equal("keine zweite Bewerbung", len(applications_of(db, residents)), 1)
    db.close()


def test_household_without_apartment_gets_wartepool_application():
    print("\n== Haushaltsbogen: Haushalt ohne Wohnung bekommt die Wartepool-Bewerbung ==")
    db = make_session()
    waiting = add_household(
        db, "Kramer", {"first_name": "Stefan", "last_name": "Kramer", "member_number": "302"})

    analysis = analyze(db, {
        "Person 1 (Name)": "Kramer, Stefan", "Person 1 (Mitgliedsnummer)": "302",
        "Wohnungsgröße": "3 Zimmer"})
    preview = analysis.households[0]
    check("kein Hinweis bei einem Haushalt ohne Wohnung", not preview.wish_not_applied)

    result = commit(db, analysis, {
        "temp_id": preview.temp_id, "action": "update", "target_household_id": waiting.id})

    applications = applications_of(db, waiting)
    check_equal("eine Bewerbung angelegt", len(applications), 1)
    check_equal("Bewerbungsart Wartepool", applications[0].kind, "wartepool")
    check_equal("Wunsch aus dem Bogen", [w["size_rooms"] for w in applications[0].wishes], [3])
    check_equal("Zusammenfassung ohne Hinweis", result.wishes_not_applied, [])
    db.close()


if __name__ == "__main__":
    test_resident_household_gets_no_application()
    test_resident_household_keeps_existing_application()
    test_household_without_apartment_gets_wartepool_application()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

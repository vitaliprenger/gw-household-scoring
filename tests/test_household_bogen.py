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
from datetime import datetime

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


def match_of(db, **row) -> schemas.MatchResult:
    """Haushaltstreffer, den die Analyse für eine Zeile meldet."""
    return analyze(db, row).households[0].match_result


def test_household_match_same_name_in_any_spelling():
    print("\n== Haushaltsbogen: Haushaltstreffer trotz anderer Namensschreibweise ==")
    db = make_session()
    # So legt der Haushaltsbogen "Anna Maria Berger" an: erstes Wort = Vorname.
    berger = add_household(db, "Berger", {"first_name": "Anna", "last_name": "Maria Berger"})
    tamm = add_household(db, "Tamm", {"first_name": "Renate", "last_name": "Tamm"})

    split = match_of(db, **{"Person 1 (Name)": "Berger, Anna Maria"})
    check_equal("anders aufgeteilter Name trifft den Haushalt",
                split.matched_household_id, berger.id)
    check("anders aufgeteilter Name ist sicher", split.is_certain, f"(typ {split.type})")

    swapped = match_of(db, **{"Person 1 (Name)": "Tamm Renate"})
    check_equal("vertauschter Name trifft den Haushalt", swapped.matched_household_id, tamm.id)
    check("vertauschter Name ist sicher", swapped.is_certain, f"(typ {swapped.type})")
    db.close()


def test_household_match_needs_unique_name_and_consistent_birth_date():
    print("\n== Haushaltsbogen: Name nur eindeutig und ohne Widerspruch sicher ==")
    db = make_session()
    add_household(db, "Hoffmann", {"first_name": "Jürgen", "last_name": "Hoffmann"})
    add_household(db, "Hoffmann 2", {"first_name": "Jürgen", "last_name": "Hoffmann"})
    kramer = add_household(db, "Kramer", {
        "first_name": "Stefan", "last_name": "Kramer", "birth_date": datetime(1985, 3, 14)})

    ambiguous = match_of(db, **{"Person 1 (Name)": "Hoffmann, Jürgen"})
    check("Name, den zwei Personen tragen, ist NICHT sicher", not ambiguous.is_certain,
          f"(typ {ambiguous.type})")

    conflict = match_of(db, **{
        "Person 1 (Name)": "Kramer, Stefan", "Person 1 (Geburtsdatum)": "1990-01-01"})
    check("widersprüchliches Geburtsdatum ist NICHT sicher", not conflict.is_certain,
          f"(typ {conflict.type})")

    without_birth_date = match_of(db, **{"Person 1 (Name)": "Kramer, Stefan"})
    check_equal("Geburtsdatum fehlt im Bogen: Treffer",
                without_birth_date.matched_household_id, kramer.id)
    check("Geburtsdatum fehlt im Bogen: sicher", without_birth_date.is_certain)
    db.close()


def test_household_match_member_number_needs_matching_person():
    print("\n== Haushaltsbogen: Mitgliedsnummer nur mit passender Person sicher ==")
    db = make_session()
    kern = add_household(db, "Kern", {
        "first_name": "Agathe", "last_name": "Kern", "member_number": "412",
        "birth_date": datetime(1970, 2, 3)})

    own = match_of(db, **{
        "Person 1 (Name)": "Kern, Agathe Maria", "Person 1 (Mitgliedsnummer)": "412"})
    check_equal("Nummer mit passendem Namen trifft den Haushalt",
                own.matched_household_id, kern.id)
    check("Nummer mit passendem Namen ist sicher", own.is_certain)

    foreign = match_of(db, **{
        "Person 1 (Name)": "Bauer, Moritz", "Person 1 (Mitgliedsnummer)": "412"})
    check("Nummer mit fremdem Namen ist NICHT sicher", not foreign.is_certain,
          f"(typ {foreign.type})")
    check_equal("Nummer mit fremdem Namen bleibt ein Vorschlag",
                foreign.matched_household_id, kern.id)

    child = match_of(db, **{
        "Person 1 (Name)": "Kern, Lina", "Person 1 (Mitgliedsnummer)": "412",
        "Person 1 (Geburtsdatum)": "2015-03-02"})
    check("Nummer mit widersprüchlichem Geburtsdatum ist NICHT sicher",
          not child.is_certain, f"(typ {child.type})")
    db.close()


def test_household_match_persons_in_two_households():
    print("\n== Haushaltsbogen: Personen des Bogens stehen in zwei Haushalten ==")
    db = make_session()
    add_household(db, "Ebert", {
        "first_name": "Ines", "last_name": "Ebert", "member_number": "301"})
    add_household(db, "Kramer", {
        "first_name": "Stefan", "last_name": "Kramer", "member_number": "302"})

    # Zusammenzug: beide stehen sicher im Datenbestand, aber in zwei Haushalten.
    moving_in = match_of(db, **{
        "Person 1 (Name)": "Ebert, Ines", "Person 1 (Mitgliedsnummer)": "301",
        "Person 2 (Name)": "Kramer, Stefan", "Person 2 (Mitgliedsnummer)": "302"})
    check("kein sicherer Haushaltstreffer", not moving_in.is_certain,
          f"(typ {moving_in.type})")
    db.close()


def update_household(db, household, **row) -> schemas.HHCommitResponse:
    """Liest eine Zeile ein und übernimmt sie für ``household``."""
    analysis = analyze(db, row)
    result = commit(db, analysis, {
        "temp_id": analysis.households[0].temp_id, "action": "update",
        "target_household_id": household.id})
    db.refresh(household)
    return result


def first_names(household) -> list[str]:
    return sorted(p.first_name for p in household.people)


TWINS = {
    "Person 2 (Name)": "Dreyer, Karl", "Person 2 (Geburtsdatum)": "2019-04-04",
    "Person 3 (Name)": "Dreyer, Emil", "Person 3 (Geburtsdatum)": "2019-04-04",
}


def test_twins_stay_two_persons():
    print("\n== Haushaltsbogen: Zwillinge bleiben zwei Personen ==")
    db = make_session()
    household = add_household(
        db, "Dreyer", {"first_name": "Olaf", "last_name": "Dreyer", "member_number": "360"})

    update_household(db, household, **{
        "Person 1 (Name)": "Dreyer, Olaf", "Person 1 (Mitgliedsnummer)": "360", **TWINS})

    check_equal("beide Zwillinge angelegt", first_names(household), ["Emil", "Karl", "Olaf"])
    db.close()


def test_twin_of_an_existing_person_is_added():
    print("\n== Haushaltsbogen: ein Zwilling steht schon im Haushalt ==")
    db = make_session()
    household = add_household(
        db, "Dreyer",
        {"first_name": "Olaf", "last_name": "Dreyer", "member_number": "360"},
        {"first_name": "Karl", "last_name": "Dreyer", "birth_date": datetime(2019, 4, 4),
         "gender": "m"})

    # Der neue Zwilling steht im Bogen vor dem vorhandenen.
    update_household(db, household, **{
        "Person 1 (Name)": "Dreyer, Olaf", "Person 1 (Mitgliedsnummer)": "360",
        "Person 2 (Name)": "Dreyer, Emil", "Person 2 (Geburtsdatum)": "2019-04-04",
        "Person 3 (Name)": "Dreyer, Karl", "Person 3 (Geburtsdatum)": "2019-04-04"})

    check_equal("der andere Zwilling ist neu angelegt",
                first_names(household), ["Emil", "Karl", "Olaf"])
    karl = next(p for p in household.people if p.first_name == "Karl")
    check_equal("die Angaben des vorhandenen Zwillings bleiben seine", karl.gender, "m")
    db.close()


def test_call_name_matches_within_the_household():
    print("\n== Haushaltsbogen: Rufname trifft im Haushalt, wenn er eindeutig ist ==")
    db = make_session()
    household = add_household(
        db, "Dreyer",
        {"first_name": "Olaf", "last_name": "Dreyer", "member_number": "360"},
        {"first_name": "Jakob Finn", "last_name": "Dreyer"})

    update_household(db, household, **{
        "Person 1 (Name)": "Dreyer, Olaf", "Person 1 (Mitgliedsnummer)": "360",
        "Person 2 (Name)": "Dreyer, Jakob", "Person 2 (Geburtsdatum)": "2021-03-14"})

    check_equal("keine Dublette zum Rufnamen", first_names(household), ["Jakob Finn", "Olaf"])
    jakob = next(p for p in household.people if p.first_name == "Jakob Finn")
    check_equal("Geburtsdatum ergänzt", jakob.birth_date, datetime(2021, 3, 14))

    # Zwei Personen mit demselben Rufnamen: Der Bogen meint keine eindeutig.
    db.add(models.Person(household_id=household.id, first_name="Jakob Bo", last_name="Dreyer"))
    db.commit()
    update_household(db, household, **{
        "Zeitstempel": "2026-09-02T10:00:00+02:00",
        "Person 1 (Name)": "Dreyer, Olaf", "Person 1 (Mitgliedsnummer)": "360",
        "Person 2 (Name)": "Dreyer, Jakob"})
    check_equal("mehrdeutiger Rufname wird nicht zugeordnet", first_names(household),
                ["Jakob", "Jakob Bo", "Jakob Finn", "Olaf"])
    db.close()


if __name__ == "__main__":
    test_resident_household_gets_no_application()
    test_resident_household_keeps_existing_application()
    test_household_without_apartment_gets_wartepool_application()
    test_household_match_same_name_in_any_spelling()
    test_household_match_needs_unique_name_and_consistent_birth_date()
    test_household_match_member_number_needs_matching_person()
    test_household_match_persons_in_two_households()
    test_twins_stay_two_persons()
    test_twin_of_an_existing_person_is_added()
    test_call_name_matches_within_the_household()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

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
    # Wie die Anwendung (backend/database.py): ohne Autoflush. Was ein Import
    # im selben Durchgang anlegt, sieht eine Abfrage erst nach dem Speichern.
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


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
    check_equal("Treffer-Art nennt den Grund", moving_in.type, "several_households")
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


PARENT = {"Person 1 (Name)": "Sommer, Ole", "Person 1 (Mitgliedsnummer)": "360"}
TWINS = {
    "Person 2 (Name)": "Sommer, Mia", "Person 2 (Geburtsdatum)": "2019-04-04",
    "Person 3 (Name)": "Sommer, Jule", "Person 3 (Geburtsdatum)": "2019-04-04",
}


def sommer_household(db, *more_people: dict) -> models.Household:
    return add_household(
        db, "Sommer",
        {"first_name": "Ole", "last_name": "Sommer", "member_number": "360"}, *more_people)


def test_twins_stay_two_persons():
    print("\n== Haushaltsbogen: Zwillinge bleiben zwei Personen ==")
    db = make_session()
    household = sommer_household(db)

    update_household(db, household, **PARENT, **TWINS)

    check_equal("beide Zwillinge angelegt", first_names(household), ["Jule", "Mia", "Ole"])
    db.close()


def test_twin_of_an_existing_person_is_added():
    print("\n== Haushaltsbogen: ein Zwilling steht schon im Haushalt ==")
    db = make_session()
    household = sommer_household(
        db, {"first_name": "Mia", "last_name": "Sommer", "birth_date": datetime(2019, 4, 4)})
    mia_id = next(p.id for p in household.people if p.first_name == "Mia")

    # Der neue Zwilling steht im Bogen vor dem vorhandenen.
    update_household(db, household, **PARENT, **{
        "Person 2 (Name)": "Sommer, Jule", "Person 2 (Geburtsdatum)": "2019-04-04",
        "Person 3 (Name)": "Sommer, Mia", "Person 3 (Geburtsdatum)": "2019-04-04"})

    check_equal("der andere Zwilling ist neu angelegt",
                first_names(household), ["Jule", "Mia", "Ole"])
    check_equal("der vorhandene Zwilling ist dieselbe Person geblieben",
                [p.id for p in household.people if p.first_name == "Mia"], [mia_id])
    db.close()


def test_call_name_matches_within_the_household():
    print("\n== Haushaltsbogen: Rufname trifft im Haushalt, wenn er eindeutig ist ==")
    db = make_session()
    household = sommer_household(db, {"first_name": "Jonas Emil", "last_name": "Sommer"})

    update_household(db, household, **PARENT, **{
        "Person 2 (Name)": "Sommer, Jonas", "Person 2 (Geburtsdatum)": "2020-02-02"})

    check_equal("keine Dublette zum Rufnamen", first_names(household), ["Jonas Emil", "Ole"])
    jonas = next(p for p in household.people if p.first_name == "Jonas Emil")
    check_equal("Geburtsdatum ergänzt", jonas.birth_date, datetime(2020, 2, 2))

    # Zwei Personen mit demselben Rufnamen: Der Bogen meint keine eindeutig.
    db.add(models.Person(household_id=household.id, first_name="Jonas Finn", last_name="Sommer"))
    db.commit()
    update_household(db, household, **PARENT, **{
        "Zeitstempel": "2026-09-02T10:00:00+02:00", "Person 2 (Name)": "Sommer, Jonas"})
    check_equal("mehrdeutiger Rufname wird nicht zugeordnet", first_names(household),
                ["Jonas", "Jonas Emil", "Jonas Finn", "Ole"])
    db.close()


def test_name_beats_member_number_within_the_household():
    print("\n== Haushaltsbogen: Kind trägt im Bogen die Nummer des Elternteils ==")
    db = make_session()
    household = sommer_household(db)

    # Das Kind steht vor dem Elternteil, dessen Geburtsdatum nicht bekannt ist.
    update_household(db, household, **{
        "Person 1 (Name)": "Sommer, Mia", "Person 1 (Mitgliedsnummer)": "360",
        "Person 1 (Geburtsdatum)": "2019-04-04",
        "Person 2 (Name)": "Sommer, Ole", "Person 2 (Mitgliedsnummer)": "360"})

    check_equal("das Kind ist eine eigene Person", first_names(household), ["Mia", "Ole"])
    ole = next(p for p in household.people if p.first_name == "Ole")
    check_equal("der Elternteil bekommt nicht das Geburtsdatum des Kindes", ole.birth_date, None)
    db.close()


def test_wartepool_wish_is_replaced():
    print("\n== Haushaltsbogen: Wunsch der offenen Wartepool-Bewerbung wird ersetzt ==")
    db = make_session()
    waiting = add_household(
        db, "Kramer", {"first_name": "Stefan", "last_name": "Kramer", "member_number": "302"})
    db.add(models.Application(
        household_id=waiting.id, kind="wartepool", status="offen",
        wishes=[{"size_rooms": 2, "funding_type": None, "apartment_category": None}]))
    db.commit()

    update_household(db, waiting, **{
        "Person 1 (Name)": "Kramer, Stefan", "Person 1 (Mitgliedsnummer)": "302",
        "Wohnungsgröße": "4 Zimmer"})

    applications = applications_of(db, waiting)
    check_equal("keine zweite Bewerbung", len(applications), 1)
    check_equal("Wunsch ersetzt", [w["size_rooms"] for w in applications[0].wishes], [4])
    db.close()


def add_person(db, first_name, last_name, **fields) -> models.Person:
    """Person ohne Haushalt, wie sie von Hand oder aus der Mitgliederliste entsteht."""
    person = models.Person(first_name=first_name, last_name=last_name, **fields)
    db.add(person)
    db.commit()
    return person


def test_person_without_household_is_assigned():
    print("\n== Haushaltsbogen: Person ohne Haushalt wird zugeordnet statt dupliziert ==")
    db = make_session()
    household = sommer_household(db)
    partner = add_person(db, "Nele", "Sommer", member_number="361",
                         member_since=datetime(2023, 3, 11))

    result = update_household(db, household, **PARENT, **{
        "Person 2 (Name)": "Sommer, Nele", "Person 2 (Mitgliedsnummer)": "361"})

    db.refresh(partner)
    check_equal("die vorhandene Person gehört jetzt zum Haushalt",
                partner.household_id, household.id)
    check_equal("keine Dublette", db.query(models.Person).count(), 2)
    check_equal("Eintrittsdatum bleibt", partner.member_since, datetime(2023, 3, 11))
    check_equal("Zähler: zugeordnet", result.persons_assigned, 1)
    check_equal("Zähler: neu angelegt", result.persons_created, 0)
    db.close()


def person_previews(db, **row) -> dict:
    """Vorschau je Person des Bogens, nach dem Namen im Bogen."""
    return {p.name: p for p in analyze(db, row).households[0].persons}


def test_person_of_another_household_stays_there():
    print("\n== Haushaltsbogen: Person aus einem anderen Haushalt bleibt dort ==")
    db = make_session()
    household = sommer_household(db)
    parents = add_household(
        db, "Vogel", {"first_name": "Antje", "last_name": "Vogel", "member_number": "455"})
    antje = parents.people[0]
    row = {**PARENT, "Person 2 (Name)": "Vogel, Antje", "Person 2 (Mitgliedsnummer)": "455"}

    preview = person_previews(db, **row)["Vogel, Antje"]
    check_equal("Vorschau: steht in einem anderen Haushalt", preview.status, "other_household")
    check_equal("Vorschau nennt den Haushalt", preview.other_household, "Vogel")

    # Von Hand dem Haushalt Sommer zugeordnet, obwohl Antje im Haushalt Vogel steht.
    result = update_household(db, household, **row)

    db.refresh(antje)
    check_equal("die Person ist nicht verschoben", antje.household_id, parents.id)
    check_equal("und nicht doppelt angelegt", db.query(models.Person).count(), 2)
    check_equal("Zusammenfassung nennt Person und bisherigen Haushalt",
                [(n.person, n.household) for n in result.persons_not_taken_over],
                [("Antje Vogel", "Vogel")])
    db.close()


def test_preview_shows_what_happens_to_each_person():
    print("\n== Haushaltsbogen: Vorschau je Person ==")
    db = make_session()
    sommer_household(db)
    add_person(db, "Nele", "Sommer", member_number="361")

    previews = person_previews(db, **PARENT, **{
        "Person 2 (Name)": "Sommer, Nele", "Person 2 (Mitgliedsnummer)": "361",
        "Person 3 (Name)": "Mia Lotta Sommer"})

    check_equal("steht schon im Haushalt", previews["Sommer, Ole"].status, "in_household")
    check_equal("steht ohne Haushalt im Datenbestand", previews["Sommer, Nele"].status, "assign")
    child = previews["Mia Lotta Sommer"]
    check_equal("wird neu angelegt", child.status, "new")
    check_equal("Vor- und Nachname so, wie sie gespeichert würden",
                (child.first_name, child.last_name), ("Mia", "Lotta Sommer"))
    db.close()


def test_similar_person_is_pointed_out():
    print("\n== Haushaltsbogen: ähnliche Person im Datenbestand ==")
    db = make_session()
    household = sommer_household(db)
    add_household(db, "Kern", {
        "first_name": "Agathe", "last_name": "Kern", "member_number": "412"})
    add_person(db, "Jürgen", "Hoffmann")
    add_person(db, "Jürgen", "Hoffmann")
    add_person(db, "Mia-Sophie", "Sommer", birth_date=datetime(2019, 4, 4))
    add_person(db, "Lars", "Sommer")
    row = {
        **PARENT,
        # Nummer einer Person mit ganz anderem Namen
        "Person 2 (Name)": "Bauer, Moritz", "Person 2 (Mitgliedsnummer)": "412",
        # Name, den zwei Personen tragen
        "Person 3 (Name)": "Hoffmann, Jürgen",
        # gleiches Geburtsdatum und gemeinsamer Namensbestandteil
        "Person 4 (Name)": "Sommer, Mia", "Person 4 (Geburtsdatum)": "2019-04-04",
        # nur der Nachname gemeinsam
        "Person 5 (Name)": "Sommer, Finn",
    }

    previews = person_previews(db, **row)
    def similar(name):
        return [(s.reason, s.name, s.household) for s in previews[name].similar]

    check_equal("Nummer mit unpassendem Namen",
                similar("Bauer, Moritz"), [("member_number", "Agathe Kern", "Kern")])
    check_equal("mehrdeutiger Name", similar("Hoffmann, Jürgen"),
                [("same_name", "Jürgen Hoffmann", None), ("same_name", "Jürgen Hoffmann", None)])
    check_equal("gleiches Geburtsdatum und gemeinsamer Namensbestandteil",
                similar("Sommer, Mia"), [("birth_date", "Mia-Sophie Sommer", None)])
    check_equal("gleicher Nachname allein ist kein Hinweis", similar("Sommer, Finn"), [])
    check_equal("alle vier werden neu angelegt",
                [previews[name].status for name in
                 ("Bauer, Moritz", "Hoffmann, Jürgen", "Sommer, Mia", "Sommer, Finn")],
                ["new"] * 4)

    result = update_household(db, household, **row)
    check_equal("die Personen sind trotzdem angelegt", result.persons_created, 4)
    check_equal("Zusammenfassung nennt die Personen mit ähnlichen im Datenbestand",
                sorted(n.person for n in result.similar_persons),
                ["Jürgen Hoffmann", "Mia Sommer", "Moritz Bauer"])
    db.close()


def test_member_number_someone_else_holds_is_not_stored():
    print("\n== Haushaltsbogen: vergebene Mitgliedsnummer wird nicht gespeichert ==")
    db = make_session()
    household = sommer_household(db)
    add_household(db, "Kern", {
        "first_name": "Agathe", "last_name": "Kern", "member_number": "412"})
    row = {**PARENT, "Person 2 (Name)": "Bauer, Moritz", "Person 2 (Mitgliedsnummer)": "412"}

    check_equal("Vorschau nennt, wer die Nummer trägt",
                person_previews(db, **row)["Bauer, Moritz"].member_number_holder, "Agathe Kern")

    result = update_household(db, household, **row)

    moritz = next(p for p in household.people if p.first_name == "Moritz")
    check_equal("die neue Person entsteht ohne Nummer", moritz.member_number, None)
    check_equal("Zusammenfassung nennt Person, Nummer und Träger",
                [(c.person, c.member_number, c.holder) for c in result.member_numbers_not_stored],
                [("Moritz Bauer", "412", "Agathe Kern")])
    db.close()


NEWCOMERS = {
    "Zeitstempel": "2026-09-03T08:30:00+02:00",
    "Person 1 (Name)": "Yilmaz, Deniz", "Person 1 (Mitgliedsnummer)": "501",
    "Person 1 (Geburtsdatum)": "1990-05-06",
    "Person 2 (Name)": "Berger, Anna",
    "Haushaltsmitglieder": "2",
    "Wohnberechtigungsschein": "Einkommensgruppe B",
    "Wohnungsgröße": "3 Zimmer",
}


def create_household(db, **row) -> schemas.HHCommitResponse:
    """Liest eine Zeile ein und wählt für sie „Neu anlegen“."""
    analysis = analyze(db, row)
    return commit(db, analysis, {
        "temp_id": analysis.households[0].temp_id, "action": "create"})


def test_row_without_match_does_nothing_until_decided():
    print("\n== Haushaltsbogen: Zeile ohne Treffer bewirkt ohne Entscheidung nichts ==")
    db = make_session()
    analysis = analyze(db, NEWCOMERS)
    preview = analysis.households[0]
    check("kein Treffer", preview.match_result.matched_household_id is None)
    check("„Neu anlegen“ ist zulässig", preview.create_allowed)

    # Der Assistent belegt solche Zeilen mit „Überspringen“ vor; auch eine
    # unbekannte Aktion wirkt so.
    unknown = analyze(db, NEWCOMERS)
    commit(db, unknown, {"temp_id": unknown.households[0].temp_id, "action": "undecided"})
    result = commit(db, analysis, {"temp_id": preview.temp_id, "action": "skip"})

    check_equal("kein Haushalt", db.query(models.Household).count(), 0)
    check_equal("keine Person", db.query(models.Person).count(), 0)
    check_equal("als übersprungen gezählt", result.skipped, 1)
    db.close()


def test_create_household_from_bogen():
    print("\n== Haushaltsbogen: „Neu anlegen“ ==")
    db = make_session()
    known = add_person(db, "Anna", "Berger", member_since=datetime(2024, 3, 1))

    preview = analyze(db, NEWCOMERS).households[0]
    check_equal("vorgeschlagener Haushaltsname", preview.suggested_household_name,
                "Yilmaz / Berger")
    check_equal("Vorschau für den neuen Haushalt",
                [p.status for p in preview.persons_if_created], ["new", "assign"])

    result = create_household(db, **NEWCOMERS)

    household = db.query(models.Household).one()
    check_equal("Haushaltsname aus den Nachnamen", household.name, "Yilmaz / Berger")
    check_equal("Selbstauskunft übernommen", household.wbs_status, "WBS B")
    check_equal("angegebene Haushaltsgröße", household.household_member_count, 2)
    check_equal("Import-Zeitstempel des Bogens",
                household.import_timestamp, datetime(2026, 9, 3, 8, 30))
    check("kein Bewohner-Haushalt", not household.is_resident)
    check_equal("beide Personen im Haushalt", first_names(household), ["Anna", "Deniz"])
    deniz = next(p for p in household.people if p.first_name == "Deniz")
    check_equal("neue Person mit Mitgliedsnummer und Geburtsdatum",
                (deniz.member_number, deniz.birth_date), ("501", datetime(1990, 5, 6)))
    db.refresh(known)
    check_equal("vorhandene Person zugeordnet, nicht dupliziert",
                (known.household_id, db.query(models.Person).count()), (household.id, 2))
    check_equal("ihr Eintrittsdatum bleibt", known.member_since, datetime(2024, 3, 1))

    application = applications_of(db, household)[0]
    check_equal("Wartepool-Bewerbung", (application.kind, application.status),
                ("wartepool", "offen"))
    check_equal("Datum des Wunsches ist der Zeitstempel des Bogens",
                application.requested_at, datetime(2026, 9, 3, 8, 30))
    check_equal("Wunsch aus dem Bogen", [w["size_rooms"] for w in application.wishes], [3])

    check_equal("Zähler", (result.households_created, result.persons_created,
                           result.persons_assigned, result.applications_created),
                (1, 1, 1, 1))
    db.close()


def test_create_household_without_wish_and_with_one_person():
    print("\n== Haushaltsbogen: „Neu anlegen“ ohne Wunsch, eine Person ==")
    db = make_session()
    row = {"Person 1 (Name)": "Kramer, Stefan", "Person 1 (Mitgliedsnummer)": "302"}
    check("Hinweis „keine Mitgliedsnummer“ nicht gesetzt",
          not analyze(db, row).households[0].no_member_number)

    result = create_household(db, **row)

    household = db.query(models.Household).one()
    check_equal("Haushalt heißt wie der Nachname der einen Person", household.name, "Kramer")
    check_equal("ohne Wunsch keine Bewerbung", applications_of(db, household), [])
    check_equal("Zähler Bewerbungen", result.applications_created, 0)
    db.close()


def test_no_member_number_is_pointed_out():
    print("\n== Haushaltsbogen: Hinweis „keine Mitgliedsnummer angegeben“ ==")
    db = make_session()
    preview = analyze(db, {"Person 1 (Name)": "Kramer, Stefan",
                           "Person 2 (Name)": "Kramer, Ida"}).households[0]
    check("Hinweis gesetzt, wenn keine Person eine Nummer nennt", preview.no_member_number)
    check("„Neu anlegen“ bleibt zulässig", preview.create_allowed)
    db.close()


def test_create_is_not_allowed_without_a_person():
    print("\n== Haushaltsbogen: kein neuer Haushalt ohne Person ==")
    db = make_session()
    add_household(db, "Ebert", {
        "first_name": "Ines", "last_name": "Ebert", "member_number": "301"})
    add_household(db, "Kramer", {
        "first_name": "Stefan", "last_name": "Kramer", "member_number": "302"})
    row = {"Person 1 (Name)": "Ebert, Ines", "Person 1 (Mitgliedsnummer)": "301",
           "Person 2 (Name)": "Kramer, Stefan", "Person 2 (Mitgliedsnummer)": "302",
           "Wohnungsgröße": "3 Zimmer"}

    preview = analyze(db, row).households[0]
    check("„Neu anlegen“ ist nicht zulässig", not preview.create_allowed)

    result = create_household(db, **row)

    check_equal("kein dritter Haushalt", db.query(models.Household).count(), 2)
    check_equal("keine Bewerbung", db.query(models.Application).count(), 0)
    check_equal("als übersprungen gezählt", (result.households_created, result.skipped), (0, 1))
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
    test_name_beats_member_number_within_the_household()
    test_wartepool_wish_is_replaced()
    test_person_without_household_is_assigned()
    test_person_of_another_household_stays_there()
    test_preview_shows_what_happens_to_each_person()
    test_similar_person_is_pointed_out()
    test_member_number_someone_else_holds_is_not_stored()
    test_row_without_match_does_nothing_until_decided()
    test_create_household_from_bogen()
    test_create_household_without_wish_and_with_one_person()
    test_no_member_number_is_pointed_out()
    test_create_is_not_allowed_without_a_person()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

# -*- coding: utf-8 -*-
"""Tests für die Zuordnungssicherheit beim Import.

Regel: **Nur ein eindeutiger Treffer wird automatisch zugeordnet** — eindeutige
Mitgliedsnummer oder exakt übereinstimmender Name (mit oder ohne bestätigendes
Geburtsdatum). Ein nur *ähnlicher* Name bleibt ein
Vorschlag, über den ein Mensch entscheidet. Maßgeblich ist
``schemas.MatchResult.is_certain``, abgeleitet aus
``schemas.CERTAIN_MATCH_TYPES``; die Commit-Endpunkte behandeln außerdem jede
unbekannte Aktion wie "Überspringen", damit eine unentschiedene Zeile auch
versehentlich nichts bewirken kann.

Aufruf aus dem Projekt-Root:  python tests/test_matching.py
"""
import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, schemas, import_service, vcf_import_service

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


def seed(db):
    hh = models.Household(name="Maja Van Daal")
    db.add(hh)
    db.flush()
    db.add(models.Person(
        household_id=hh.id, first_name="Maja", last_name="Van Daal",
        member_number="042", birth_date=datetime(1980, 5, 3),
    ))
    db.commit()
    return hh


def person(**overrides):
    data = {"first_name": "Maja", "last_name": "Van Daal",
            "member_number": None, "birth_date": None}
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------

def test_is_certain_derivation():
    print("\n== Ableitung von is_certain ==")
    for match_type in sorted(schemas.CERTAIN_MATCH_TYPES):
        result = schemas.MatchResult(type=match_type, matched_household_id=1, confidence=1.0)
        check(f"{match_type} ist eindeutig", result.is_certain)

    # Derselbe Treffertyp, nur ohne bestaetigendes Geburtsdatum: wird zugeordnet.
    name_only = schemas.MatchResult(type="exact_name_dob", matched_household_id=1,
                                    confidence=0.9)
    check("exakter Name ohne Geburtsdatum ist eindeutig", name_only.is_certain)

    # Entscheidend ist die Treffer-Art, nicht die Zahl: ein unscharfer
    # Namensvergleich erreicht muehelos 0.9 und mehr.
    for confidence in (0.7, 0.9, 0.97):
        result = schemas.MatchResult(type="fuzzy", matched_household_id=1,
                                     confidence=confidence)
        check(f"aehnlicher Name mit {confidence} ist NICHT eindeutig", not result.is_certain)

    check("ohne Treffer nicht eindeutig",
          not schemas.MatchResult(type="exact_member_nr", confidence=1.0).is_certain)
    # Das Feld wird immer berechnet, nie übernommen -- sonst ließe es sich umgehen.
    forged = schemas.MatchResult(type="fuzzy", matched_household_id=1,
                                 confidence=0.7, is_certain=True)
    check("mitgeliefertes is_certain wird überschrieben", not forged.is_certain)


def test_household_matching_confidence():
    print("\n== Haushalts-Matching ==")
    db = make_session()
    hh = seed(db)

    by_number = import_service.match_household({"persons": [person(member_number="42")]}, db)
    check_equal("Mitgliedsnummer trifft", by_number.matched_household_id, hh.id)
    check("Mitgliedsnummer wird zugeordnet", by_number.is_certain)

    by_dob = import_service.match_household(
        {"persons": [person(birth_date="1980-05-03")]}, db)
    check_equal("Name + Geburtsdatum trifft", by_dob.matched_household_id, hh.id)
    check("Name + Geburtsdatum wird zugeordnet", by_dob.is_certain)

    by_name = import_service.match_household({"persons": [person()]}, db)
    check_equal("Name ohne Geburtsdatum trifft", by_name.matched_household_id, hh.id)
    check("exakter Name ohne Geburtsdatum wird zugeordnet", by_name.is_certain,
          f"(typ {by_name.type}, confidence {by_name.confidence})")

    fuzzy = import_service.match_household(
        {"persons": [person(first_name="Maja", last_name="Van Dahl")]}, db)
    check("ähnlicher Name wird NICHT zugeordnet", not fuzzy.is_certain,
          f"(typ {fuzzy.type}, confidence {fuzzy.confidence})")

    none = import_service.match_household(
        {"persons": [person(first_name="Ganz", last_name="Anders")]}, db)
    check("ohne Treffer keine Zuordnung", not none.is_certain)
    db.close()


def test_individual_matching_confidence():
    print("\n== Personen-Matching (Individualbogen) ==")
    db = make_session()
    seed(db)

    by_number = import_service.match_individual_to_person(person(member_number="42"), db)
    check("Mitgliedsnummer wird zugeordnet", by_number.is_certain)

    by_name = import_service.match_individual_to_person(person(), db)
    check("exakter Name ohne Geburtsdatum wird zugeordnet", by_name.is_certain,
          f"(typ {by_name.type}, confidence {by_name.confidence})")

    fuzzy = import_service.match_individual_to_person(
        person(first_name="Maja", last_name="Van Dahl"), db)
    check("ähnlicher Name wird NICHT zugeordnet", not fuzzy.is_certain,
          f"(typ {fuzzy.type}, confidence {fuzzy.confidence})")
    db.close()


def individual_xlsx(*rows: dict) -> bytes:
    """Export des Individualbogens mit den Spalten des Fragebogens."""
    frame = pd.DataFrame([{
        "Zeitstempel": "2026-09-01T10:00:00+02:00",
        "Datenschutz": "Mir ist klar, dass meine Angaben gespeichert werden.",
        "Mitgliedsnummer": "",
        "Nachname, Vorname": "",
        "Geburtsdatum": "",
        "Geschlecht": "weiblich",
        "Absenden?": "Ja",
        **row,
    } for row in rows])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def analyze_individual(db, **row) -> schemas.MatchResult:
    """Treffer, den die Analyse des Individualbogens für eine Zeile meldet."""
    analysis = import_service.analyze_individual_bogen(individual_xlsx(row), db)
    return analysis.individuals[0].match_result


def add_person(db, first_name, last_name, **fields) -> models.Person:
    new_person = models.Person(first_name=first_name, last_name=last_name, **fields)
    db.add(new_person)
    db.commit()
    return new_person


def test_individual_same_name_in_any_spelling():
    print("\n== Individualbogen: gleicher Name trotz anderer Schreibweise ==")
    db = make_session()
    # So legt der Haushaltsbogen "Anna Maria Berger" an: erstes Wort = Vorname.
    anna = add_person(db, "Anna", "Maria Berger")
    renate = add_person(db, "Renate", "Tamm")
    add_person(db, "Lea", "Sommer-Vogel")

    split = analyze_individual(db, **{"Nachname, Vorname": "Berger, Anna Maria"})
    check_equal("anders aufgeteilter Name trifft", split.matched_household_id, anna.id)
    check("anders aufgeteilter Name ist sicher", split.is_certain, f"(typ {split.type})")

    swapped = analyze_individual(db, **{"Nachname, Vorname": "TAMM renate"})
    check_equal("vertauschter Name ohne Komma trifft",
                swapped.matched_household_id, renate.id)
    check("vertauschter Name in anderer Großschreibung ist sicher", swapped.is_certain)

    hyphen = analyze_individual(db, **{"Nachname, Vorname": "Sommer Vogel, Lea"})
    check("Name mit Bindestrich ist ein Bestandteil, getrennt geschrieben NICHT sicher",
          not hyphen.is_certain, f"(typ {hyphen.type})")
    db.close()


def test_individual_name_needs_unique_person_and_consistent_birth_date():
    print("\n== Individualbogen: Name nur eindeutig und ohne Widerspruch sicher ==")
    db = make_session()
    without_birth_date = add_person(db, "Ines", "Ebert")
    with_birth_date = add_person(db, "Stefan", "Kramer", birth_date=datetime(1985, 3, 14))
    add_person(db, "Jonas Emil", "Sommer", birth_date=datetime(2020, 2, 2))
    add_person(db, "Jürgen", "Hoffmann")
    add_person(db, "Jürgen", "Hoffmann")

    result = analyze_individual(
        db, **{"Nachname, Vorname": "Ebert, Ines", "Geburtsdatum": "1991-04-12"})
    check_equal("Geburtsdatum fehlt bei der Person: Treffer",
                result.matched_household_id, without_birth_date.id)
    check("Geburtsdatum fehlt bei der Person: sicher", result.is_certain,
          f"(typ {result.type})")

    result = analyze_individual(db, **{"Nachname, Vorname": "Kramer, Stefan"})
    check_equal("Geburtsdatum fehlt im Bogen: Treffer",
                result.matched_household_id, with_birth_date.id)
    check("Geburtsdatum fehlt im Bogen: sicher", result.is_certain)

    result = analyze_individual(
        db, **{"Nachname, Vorname": "Kramer, Stefan", "Geburtsdatum": "1990-01-01"})
    check("widersprüchliches Geburtsdatum ist NICHT sicher", not result.is_certain,
          f"(typ {result.type})")

    result = analyze_individual(db, **{"Nachname, Vorname": "Hoffmann, Jürgen"})
    check("Name, den zwei Personen tragen, ist NICHT sicher", not result.is_certain,
          f"(typ {result.type})")

    result = analyze_individual(
        db, **{"Nachname, Vorname": "Sommer, Jonas", "Geburtsdatum": "2020-02-02"})
    check("bloßer Rufname ist NICHT sicher", not result.is_certain, f"(typ {result.type})")
    db.close()


def test_individual_member_number_needs_matching_name():
    print("\n== Individualbogen: Mitgliedsnummer nur mit passendem Namen sicher ==")
    db = make_session()
    agathe = add_person(db, "Agathe", "Kern", member_number="412")

    own_number = analyze_individual(
        db, **{"Nachname, Vorname": "Kern, Agathe Maria", "Mitgliedsnummer": "412"})
    check_equal("Nummer mit passendem Namen trifft", own_number.matched_household_id, agathe.id)
    check("Nummer mit passendem Namen ist sicher", own_number.is_certain)

    foreign = analyze_individual(
        db, **{"Nachname, Vorname": "Bauer, Moritz", "Mitgliedsnummer": "412"})
    check("Nummer mit ganz anderem Namen ist NICHT sicher", not foreign.is_certain,
          f"(typ {foreign.type})")
    check_equal("Nummer mit ganz anderem Namen bleibt ein Vorschlag",
                foreign.matched_household_id, agathe.id)
    db.close()


def test_individual_member_number_of_a_parent():
    print("\n== Individualbogen: Kind trägt die Nummer eines Elternteils ein ==")
    db = make_session()
    add_person(db, "Moritz", "Bauer", member_number="431",
               birth_date=datetime(1984, 6, 2))

    child = analyze_individual(db, **{
        "Nachname, Vorname": "Bauer, Lina", "Mitgliedsnummer": "431",
        "Geburtsdatum": "2015-03-02"})
    check("gleicher Nachname, anderes Geburtsdatum ist NICHT sicher",
          not child.is_certain, f"(typ {child.type})")
    db.close()


def test_individual_member_number_needs_a_shared_first_name():
    print("\n== Individualbogen: Mitgliedsnummer braucht einen gemeinsamen Vornamen ==")
    db = make_session()
    # Der Elternteil hat kein Geburtsdatum, und das Kind ist noch nicht erfasst:
    # Der gemeinsame Nachname allein darf die Nummer nicht bestätigen.
    moritz = add_person(db, "Moritz", "Bauer", member_number="431")

    child = analyze_individual(db, **{
        "Nachname, Vorname": "Bauer, Lina", "Mitgliedsnummer": "431"})
    check("nur der Nachname gemeinsam ist NICHT sicher", not child.is_certain,
          f"(typ {child.type})")

    renamed = analyze_individual(db, **{
        "Nachname, Vorname": "Schulze, Moritz", "Mitgliedsnummer": "431"})
    check_equal("neuer Nachname, gleicher Vorname trifft", renamed.matched_household_id, moritz.id)
    check("neuer Nachname, gleicher Vorname ist sicher", renamed.is_certain,
          f"(typ {renamed.type})")
    db.close()


def test_individual_same_name_beats_member_number():
    print("\n== Individualbogen: Name und Mitgliedsnummer zeigen auf verschiedene Personen ==")
    db = make_session()
    # Der Elternteil hat kein Geburtsdatum, das dem Kind widersprechen könnte.
    add_person(db, "Moritz", "Bauer", member_number="431")
    lina = add_person(db, "Lina", "Bauer")

    child = analyze_individual(db, **{
        "Nachname, Vorname": "Bauer, Lina", "Mitgliedsnummer": "431",
        "Geburtsdatum": "2015-03-02"})
    check_equal("die Person mit dem gleichen Namen wird getroffen",
                child.matched_household_id, lina.id)
    check("der gleiche Name ist sicher", child.is_certain, f"(typ {child.type})")
    db.close()


def test_individual_member_number_held_by_several_persons():
    print("\n== Individualbogen: Mitgliedsnummer, die mehrere Personen tragen ==")
    db = make_session()
    first = add_person(db, "Antje", "Vogel", member_number="455")
    second = add_person(db, "Björn", "Vogel", member_number="455")

    result = analyze_individual(
        db, **{"Nachname, Vorname": "Vogel, A.", "Mitgliedsnummer": "455"})
    check("mehrfach vergebene Nummer ist NICHT sicher", not result.is_certain,
          f"(typ {result.type})")
    offered = {c.household_id for c in result.fuzzy_candidates}
    check("alle Personen mit der Nummer stehen zur Auswahl",
          {first.id, second.id} <= offered, f"(angeboten {offered})")
    db.close()


def test_individual_member_number_ignores_name_particles():
    print("\n== Individualbogen: Namenszusatz bestätigt keine Mitgliedsnummer ==")
    db = make_session()
    add_person(db, "Dan", "Van Daal", member_number="377")

    result = analyze_individual(
        db, **{"Nachname, Vorname": "van Bergen, Ines", "Mitgliedsnummer": "377"})
    check("nur der Zusatz „van“ gemeinsam ist NICHT sicher", not result.is_certain,
          f"(typ {result.type})")
    db.close()


def test_undecided_action_does_nothing():
    print("\n== Unentschiedene Zeile bewirkt nichts ==")

    # --- Haushaltsbogen ---
    db = make_session()
    hh = seed(db)
    raw = {
        "temp_id": "t1", "timestamp": datetime(2026, 1, 1), "wbs_status": "WBS A",
        "pets_count": 0, "pets_info": None, "wheelchair_accessible": False,
        "financial_status": None, "declared_member_count": 1,
        "wishes": [], "unparsed_wishes": [], "persons": [],
    }
    session = import_service.ImportSession("household", [raw], {})
    import_service.import_sessions[session.id] = session
    result = import_service.commit_household_bogen(schemas.HHCommitRequest(
        session_id=session.id,
        decisions=[schemas.HouseholdDecision(
            temp_id="t1", action="undecided", target_household_id=hh.id)],
    ), db)
    check_equal("Haushaltsbogen: nichts aktualisiert", result.updated, 0)
    check_equal("Haushaltsbogen: als übersprungen gezählt", result.skipped, 1)
    check("Haushaltsbogen: WBS unverändert", hh.wbs_status is None)
    db.close()

    # --- Individualbogen ---
    db = make_session()
    seed(db)
    target = db.query(models.Person).first()
    raw = {"temp_id": "t1", "first_name": "Maja", "last_name": "Van Daal",
           "birth_date": None, "member_number": None, "timestamp": datetime(2026, 1, 1),
           "gender": "f", "occupation": "2", "education": "6",
           "life_situation": None, "social_diversity": None}
    session = import_service.ImportSession("individual", [raw], {})
    import_service.import_sessions[session.id] = session
    ind_result = import_service.commit_individual_bogen(schemas.IndividualCommitRequest(
        session_id=session.id,
        decisions=[schemas.IndividualDecision(
            temp_id="t1", action="undecided", target_person_id=target.id)],
    ), db)
    check_equal("Individualbogen: nichts aktualisiert", ind_result.updated, 0)
    check("Individualbogen: Geschlecht unverändert", target.gender is None)
    db.close()

    # --- vCard ---
    db = make_session()
    hh = seed(db)
    before_households = db.query(models.Household).count()
    before_persons = db.query(models.Person).count()
    raw = {
        "temp_id": "t1", "name": "Neu Jemand", "apartment_unit": "W.001",
        "address": None, "timestamp": None,
        "persons": [{"temp_id": "p1", "first_name": "Neu", "last_name": "Jemand",
                     "name": "Neu Jemand", "birth_date": None, "gender": None,
                     "member_number": None, "member_since": None,
                     "apartment_unit": "W.001", "role": "member", "source": "contact",
                     "mentioned_by": None}],
    }
    session = import_service.ImportSession("vcf", [raw], {})
    import_service.import_sessions[session.id] = session
    vcf_result = vcf_import_service.commit_vcf(schemas.VcfCommitRequest(
        session_id=session.id,
        decisions=[schemas.VcfDecision(temp_id="t1", action="undecided")],
    ), db)
    check_equal("vCard: kein Haushalt angelegt", vcf_result.households_created, 0)
    check_equal("vCard: als übersprungen gezählt", vcf_result.households_skipped, 1)
    check_equal("vCard: Bestand unverändert",
                (db.query(models.Household).count(), db.query(models.Person).count()),
                (before_households, before_persons))
    db.close()


if __name__ == "__main__":
    test_is_certain_derivation()
    test_household_matching_confidence()
    test_individual_matching_confidence()
    test_individual_same_name_in_any_spelling()
    test_individual_name_needs_unique_person_and_consistent_birth_date()
    test_individual_member_number_needs_matching_name()
    test_individual_member_number_of_a_parent()
    test_individual_member_number_needs_a_shared_first_name()
    test_individual_same_name_beats_member_number()
    test_individual_member_number_held_by_several_persons()
    test_individual_member_number_ignores_name_particles()
    test_undecided_action_does_nothing()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

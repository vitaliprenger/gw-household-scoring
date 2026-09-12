# -*- coding: utf-8 -*-
"""Tests für die Zuordnungssicherheit beim Import.

Regel: **Nur ein eindeutiger Treffer wird automatisch zugeordnet** — eindeutige
Mitgliedsnummer, exakt übereinstimmender Name (mit oder ohne bestätigendes
Geburtsdatum) oder die Wohnungsnummer. Ein nur *ähnlicher* Name bleibt ein
Vorschlag, über den ein Mensch entscheidet. Maßgeblich ist
``schemas.MatchResult.is_certain``, abgeleitet aus
``schemas.CERTAIN_MATCH_TYPES``; die Commit-Endpunkte behandeln außerdem jede
unbekannte Aktion wie "Überspringen", damit eine unentschiedene Zeile auch
versehentlich nichts bewirken kann.

Aufruf aus dem Projekt-Root:  python tests/test_matching.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, schemas, import_service, vcf_import_service
from backend import application_import_service as ais

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
    hh = models.Household(name="Maja Van Loey")
    db.add(hh)
    db.flush()
    db.add(models.Person(
        household_id=hh.id, first_name="Maja", last_name="Van Loey",
        member_number="042", birth_date=datetime(1980, 5, 3),
    ))
    db.commit()
    return hh


def person(**overrides):
    data = {"first_name": "Maja", "last_name": "Van Loey",
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
    check("Aehnlichkeit des Haushaltsnamens ist NICHT eindeutig",
          not schemas.MatchResult(type="household_name", matched_household_id=1,
                                  confidence=0.95).is_certain)
    check("heutiger Bewohner der Wohnung ist NICHT eindeutig",
          not schemas.MatchResult(type="apartment_occupant", matched_household_id=1,
                                  confidence=1.0).is_certain)

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
        {"persons": [person(first_name="Maja", last_name="Van Looy")]}, db)
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
        person(first_name="Maja", last_name="Van Looy"), db)
    check("ähnlicher Name wird NICHT zugeordnet", not fuzzy.is_certain,
          f"(typ {fuzzy.type}, confidence {fuzzy.confidence})")
    db.close()


def test_application_matching_confidence():
    print("\n== Bewerbungslisten-Matching ==")
    db = make_session()
    hh = seed(db)
    apt = models.Apartment(unit_number="R.106", size_rooms=1, funding_type="WBS A",
                           household_id=hh.id)
    db.add(apt)
    hh.is_resident = True
    hh.apartment_unit = "R.106"
    db.commit()

    by_unit = ais._match_row(
        {"raw_current_unit": "R.106", "person_names": ["Maja Van Loey"],
         "raw_household": "Maja Van Loey"}, db)
    check_equal("Name + Wohnung treffen denselben Haushalt",
                by_unit.matched_household_id, hh.id)
    check_equal("Wohnung bestätigt den Namen", by_unit.type, "apartment_unit")
    check("bestätigter Treffer wird zugeordnet", by_unit.is_certain)

    by_name = ais._match_row(
        {"raw_current_unit": None, "person_names": ["Maja Van Loey"],
         "raw_household": "Maja Van Loey"}, db)
    check_equal("Name trifft", by_name.matched_household_id, hh.id)
    check("exakter Name wird zugeordnet", by_name.is_certain,
          f"(typ {by_name.type}, confidence {by_name.confidence})")

    fuzzy = ais._match_row(
        {"raw_current_unit": None, "person_names": ["Maja Van Looy"],
         "raw_household": "Maja Van Looy"}, db)
    check("ähnlicher Name wird NICHT zugeordnet", not fuzzy.is_certain,
          f"(typ {fuzzy.type}, confidence {fuzzy.confidence})")

    # Haushalt ohne passende Person: der eindeutige Haushaltsname zählt.
    db.add(models.Household(name="Familie Sonderbar"))
    db.commit()
    by_hh_name = ais._match_row(
        {"raw_current_unit": None, "person_names": ["Familie Sonderbar"],
         "raw_household": "Familie Sonderbar"}, db)
    check_equal("eindeutiger Haushaltsname", by_hh_name.type, "exact_household_name")
    check("eindeutiger Haushaltsname wird zugeordnet", by_hh_name.is_certain)
    db.close()


def test_application_matching_uses_names_not_apartment():
    print("\n== Wohnung bestätigt nur, sie identifiziert nicht ==")
    db = make_session()
    # Ausgangslage wie in den echten Daten: Der Bewerber ist aus R.106 in R.213
    # gezogen (Bewerbung erfüllt), in R.106 wohnt inzwischen jemand anderes.
    mover = seed(db)                                     # "Maja Van Loey"
    newcomer = models.Household(name="Michaela Andere", is_resident=True)
    db.add(newcomer)
    db.flush()
    db.add(models.Person(household_id=newcomer.id,
                         first_name="Michaela", last_name="Andere"))
    db.add(models.Apartment(unit_number="R.106", size_rooms=1,
                            funding_type="WBS A", household_id=newcomer.id))
    db.add(models.Apartment(unit_number="R.213", size_rooms=2,
                            funding_type="WBS A", household_id=mover.id))
    mover.is_resident = True
    mover.apartment_unit = "R.213"
    newcomer.apartment_unit = "R.106"
    db.commit()

    row = {
        "raw_current_unit": "R.106", "raw_new_unit": "R.213", "status": "erfuellt",
        "person_names": ["Maja Van Loey"], "raw_household": "Maja Van Loey",
    }
    result = ais._match_row(row, db)
    check_equal("der Bewerber wird getroffen, nicht der heutige Bewohner",
                result.matched_household_name, "Maja Van Loey")
    check("Treffer ist eindeutig", result.is_certain, f"(typ {result.type})")

    # Passt der Name zu niemandem, bleibt der heutige Bewohner ein bloßer Hinweis.
    unknown = ais._match_row({
        "raw_current_unit": "R.106", "raw_new_unit": None, "status": "erfuellt",
        "person_names": ["Voellig Unbekannt"], "raw_household": "Voellig Unbekannt",
    }, db)
    check_equal("heutiger Bewohner nur als Hinweis", unknown.type, "apartment_occupant")
    check_equal("Hinweis nennt den heutigen Bewohner",
                unknown.matched_household_name, "Michaela Andere")
    check("Hinweis wird NICHT automatisch zugeordnet", not unknown.is_certain)
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
    raw = {"temp_id": "t1", "first_name": "Maja", "last_name": "Van Loey",
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

    # --- Bewerbungsliste ---
    db = make_session()
    hh = seed(db)
    raw = {
        "temp_id": "t1", "row": 2, "raw_household": "Maja Van Loey", "person_names": [],
        "kind": "wartepool", "raw_kind": None, "requested_at": None,
        "wishes": [], "unparsed_wishes": [], "status": "offen", "raw_status": None,
        "note": None, "raw_current_type": None, "raw_current_unit": None,
        "raw_new_unit": None,
    }
    session = import_service.ImportSession("applications", [raw], {})
    import_service.import_sessions[session.id] = session
    app_result = ais.commit_application_list(schemas.ApplicationCommitRequest(
        session_id=session.id,
        decisions=[schemas.ApplicationDecision(
            temp_id="t1", action="undecided", target_household_id=hh.id)],
    ), db)
    check_equal("Bewerbungsliste: keine Bewerbung angelegt", app_result.applications_created, 0)
    check_equal("Bewerbungsliste: kein Haushalt angelegt", app_result.households_created, 0)
    check_equal("Bewerbungsliste: als übersprungen gezählt", app_result.skipped, 1)
    check_equal("Bewerbungsliste: Bestand unverändert",
                db.query(models.Application).count(), 0)
    db.close()


if __name__ == "__main__":
    test_is_certain_derivation()
    test_household_matching_confidence()
    test_individual_matching_confidence()
    test_application_matching_confidence()
    test_application_matching_uses_names_not_apartment()
    test_undecided_action_does_nothing()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

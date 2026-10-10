# -*- coding: utf-8 -*-
"""Tests für die Importkette im Regelbetrieb (ADR 0011).

1. Haushaltsbogen  – legt auf Entscheidung Haushalt, Personen und
                     Wartepool-Bewerbung an
2. Individualbogen – findet diese Personen wieder und ergänzt ihre Angaben
3. Mitgliederliste – Nebenfunktion: füllt, was dann noch fehlt

Aufruf aus dem Projekt-Root:  python tests/test_import_order.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import import_service, models, person_matching, schemas
from backend import vcf_import_service as member_list

from test_household_bogen import household_xlsx  # noqa: E402
from test_matching import individual_xlsx  # noqa: E402
from test_member_list import card  # noqa: E402

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


def person(db, first_name: str):
    return db.query(models.Person).filter(models.Person.first_name == first_name).first()


def take_over_certain_individuals(db, analysis) -> schemas.IndividualCommitResponse:
    """Die Vorbelegung des Assistenten: sichere Treffer übernehmen, alles andere überspringen."""
    return import_service.commit_individual_bogen(schemas.IndividualCommitRequest(
        session_id=analysis.session_id,
        decisions=[
            schemas.IndividualDecision(
                temp_id=preview.temp_id,
                action="update" if preview.match_result.is_certain else "skip",
                target_person_id=(
                    preview.match_result.matched_household_id
                    if preview.match_result.is_certain else None
                ),
            )
            for preview in analysis.individuals
        ],
    ), db)


# ---------------------------------------------------------------------------
# Die Kette
# ---------------------------------------------------------------------------

def test_chain_household_then_individual_then_member_list():
    print("\n== Importkette: Haushaltsbogen → Individualbogen → Mitgliederliste ==")
    db = make_session()

    # 1. Haushaltsbogen: neue Bewerbende, die Belegungskommission wählt „Neu anlegen“.
    households = import_service.analyze_household_bogen(household_xlsx({
        "Zeitstempel": "2026-09-03T08:30:00+02:00",
        "Person 1 (Name)": "Yilmaz, Deniz", "Person 1 (Mitgliedsnummer)": "501",
        "Person 1 (Geburtsdatum)": "1990-05-06",
        "Person 2 (Name)": "Anna Maria Berger",
        "Haushaltsmitglieder": "2", "Wohnungsgröße": "3 Zimmer",
    }), db)
    preview = households.households[0]
    check("Haushaltsbogen: ohne Treffer nichts vorausgewählt",
          not preview.match_result.is_certain)
    created = import_service.commit_household_bogen(schemas.HHCommitRequest(
        session_id=households.session_id,
        decisions=[schemas.HouseholdDecision(temp_id=preview.temp_id, action="create")],
    ), db)
    check_equal("Haushaltsbogen: Haushalt, Personen und Bewerbung angelegt",
                (created.households_created, created.persons_created,
                 created.applications_created), (1, 2, 1))

    # 2. Individualbogen: schreibt den Namen anders als der Haushaltsbogen.
    individuals = import_service.analyze_individual_bogen(individual_xlsx(
        {"Nachname, Vorname": "Yilmaz, Deniz", "Mitgliedsnummer": "501",
         "Geschlecht": "männlich", "Mitglied seit": "2025-10-01"},
        {"Zeitstempel": "2026-09-04T09:00:00+02:00",
         "Nachname, Vorname": "Berger, Anna Maria", "Geschlecht": "weiblich"},
    ), db)
    check("Individualbogen: findet beide Personen des Haushaltsbogens sicher",
          all(p.match_result.is_certain for p in individuals.individuals),
          str([p.match_result.type for p in individuals.individuals]))
    updated = take_over_certain_individuals(db, individuals)
    check_equal("Individualbogen: beide ergänzt", updated.updated, 2)
    check_equal("Individualbogen: keine Person angelegt", db.query(models.Person).count(), 2)

    deniz, anna = person(db, "Deniz"), person(db, "Anna")
    check_equal("Individualbogen: Geschlecht ergänzt", (deniz.gender, anna.gender), ("m", "f"))
    check_equal("Individualbogen: „Mitglied seit“ aus der Selbstauskunft",
                deniz.member_since, datetime(2025, 10, 1))

    # 3. Mitgliederliste: füllt nur, was jetzt noch fehlt.
    cards = "".join([
        card("Deniz", "Yilmaz", "X-WEILERID:501", "NOTE:Aufnahmegespräch am 15.09.2025"),
        card("Anna Maria", "Berger", "X-WEILERID:502", "BDAY:19920708",
             "NOTE:Aufnahmegespräch am 25.03.2023"),
    ]).encode("utf-8")
    summary = member_list.analyze_vcf(cards, db)
    check_equal("Mitgliederliste: genaueres Eintrittsdatum nur gelistet",
                [(d.person, d.stored, d.member_list) for d in summary.member_since_deviations],
                [("Deniz Yilmaz", "2025-10-01", "2025-09-15")])
    member_list.commit_vcf(schemas.VcfCommitRequest(session_id=summary.session_id), db)

    db.refresh(deniz)
    db.refresh(anna)
    check_equal("Mitgliederliste: Selbstauskunft nicht überschrieben",
                deniz.member_since, datetime(2025, 10, 1))
    check_equal("Mitgliederliste: Lücken gefüllt",
                (anna.member_number, anna.birth_date, anna.member_since),
                ("502", datetime(1992, 7, 8), datetime(2023, 3, 25)))
    check_equal("am Ende ein Haushalt mit zwei Personen",
                (db.query(models.Household).count(), db.query(models.Person).count()), (1, 2))
    db.close()


# ---------------------------------------------------------------------------
# Die Fragebögen legen ohne Entscheidung nichts an
# ---------------------------------------------------------------------------

def test_individual_never_creates():
    print("\n== Individualbogen: legt keine Personen an ==")
    db = make_session()
    db.add(models.Person(first_name="Ines", last_name="Ebert"))
    db.commit()

    analysis = import_service.analyze_individual_bogen(individual_xlsx(
        {"Nachname, Vorname": "Ebert, Ines"},
        {"Zeitstempel": "2026-09-04T09:00:00+02:00", "Nachname, Vorname": "Kramer, Stefan"},
    ), db)
    result = import_service.commit_individual_bogen(schemas.IndividualCommitRequest(
        session_id=analysis.session_id,
        decisions=[
            schemas.IndividualDecision(
                temp_id=preview.temp_id, action="update",
                target_person_id=preview.match_result.matched_household_id)
            for preview in analysis.individuals
        ],
    ), db)

    check_equal("keine neue Person", db.query(models.Person).count(), 1)
    check_equal("eine Person ergänzt", result.updated, 1)
    check_equal("ohne Treffer nicht übernommen", result.skipped_no_match, 1)
    db.close()


def test_household_bogen_update_needs_a_household():
    print("\n== Haushaltsbogen: „Aktualisieren“ ohne Haushalt legt nichts an ==")
    db = make_session()

    analysis = import_service.analyze_household_bogen(household_xlsx({
        "Person 1 (Name)": "Kramer, Stefan", "Wohnungsgröße": "3 Zimmer"}), db)
    result = import_service.commit_household_bogen(schemas.HHCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.HouseholdDecision(
            temp_id=analysis.households[0].temp_id, action="update")],
    ), db)

    check_equal("kein Haushalt", db.query(models.Household).count(), 0)
    check_equal("keine Bewerbung", db.query(models.Application).count(), 0)
    check_equal("ohne Treffer nicht übernommen", result.skipped_no_match, 1)
    db.close()


# ---------------------------------------------------------------------------
# Mitgliedsnummern mit und ohne führende Nullen
# ---------------------------------------------------------------------------

def test_member_number_leading_zeros():
    print("\n== Mitgliedsnummer: 3 = 003, 20 = 020 ==")
    norm = import_service.normalize_member_number
    check_equal("3 → 003", norm("3"), "003")
    check_equal("003 bleibt 003", norm("003"), "003")
    check_equal("20 → 020", norm("20"), "020")
    check_equal("Zahl aus Excel (20.0) → 020", norm(20.0), "020")
    check_equal("0003 → 003", norm("0003"), "003")
    check_equal("vierstellig unverändert", norm("1234"), "1234")
    check_equal("leer → None", norm(""), None)

    db = make_session()
    hh = models.Household(name="Nuller")
    db.add(hh)
    db.flush()
    # Altbestand: ohne bzw. mit führenden Nullen gespeichert
    drei = models.Person(first_name="Dora", last_name="Drei",
                         member_number="3", household_id=hh.id)
    zwanzig = models.Person(first_name="Zeno", last_name="Zwanzig", member_number="020")
    db.add_all([drei, zwanzig])
    db.commit()

    # Individualbogen: abweichende Schreibweise des Namens, die Nummer entscheidet
    match = import_service.match_individual_to_person(
        {"first_name": "Dora", "last_name": "D.", "member_number": "003"}, db)
    check_equal("Individualbogen: 003 findet 3", match.matched_household_id, drei.id)
    check("Individualbogen: 003 ist ein sicherer Treffer", match.is_certain)
    match = import_service.match_individual_to_person(
        {"first_name": "Zeno", "last_name": "Z.", "member_number": "20"}, db)
    check_equal("Individualbogen: 20 findet 020", match.matched_household_id, zwanzig.id)

    # Haushaltsbogen: Haushalt und Person über die Nummer
    raw = {"persons": [{"first_name": "Dora", "last_name": "D.", "member_number": "003"}]}
    household_match = import_service.match_household(raw, db)
    check_equal("Haushaltsbogen: Haushalt über 003", household_match.matched_household_id, hh.id)
    check("Haushaltsbogen: 003 ist ein sicherer Treffer", household_match.is_certain)
    check_equal("Haushaltsbogen: Person im Haushalt über 003",
                person_matching.match_household_persons(hh.people, raw["persons"]), [drei])

    # Mitgliederliste: Die Karte mit „20“ trifft die Person mit „020“.
    summary = member_list.analyze_vcf(
        card("Zeno", "Z.", "X-WEILERID:20", "BDAY:19800101").encode("utf-8"), db)
    check_equal("Mitgliederliste: 20 findet 020",
                (summary.unmatched_cards, summary.fills.birth_date), (0, 1))
    db.close()


# ---------------------------------------------------------------------------

def run_tests():
    print("--- Tests zur Importkette ---")
    for test in (
        test_chain_household_then_individual_then_member_list,
        test_individual_never_creates,
        test_household_bogen_update_needs_a_household,
        test_member_number_leading_zeros,
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

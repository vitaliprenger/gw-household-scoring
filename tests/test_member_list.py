# -*- coding: utf-8 -*-
"""Tests für den Import der Mitgliederliste (vCard).

Die Mitgliederliste füllt nur leere Angaben vorhandener Personen (ADR 0011).
Geprüft wird über Analyse und Übernehmen: Die vCard entsteht im Speicher, die
Analyse liefert die Zusammenfassung, und nach dem Übernehmen zählt der
Datenbestand. Der Parser selbst steht in ``test_vcf_import.py``.

Aufruf aus dem Projekt-Root:  python tests/test_member_list.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, schemas
from backend import vcf_import_service as member_list

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


def card(first_name: str, last_name: str, *lines: str) -> str:
    return "\n".join([
        "BEGIN:VCARD", "VERSION:3.0",
        f"FN:{first_name} {last_name}", f"N:{last_name};{first_name};;;",
        *lines, "END:VCARD", "",
    ])


#: Karte mit allen Angaben; das Eintrittsdatum steht nur im Notizfeld.
INES = card(
    "Ines", "Ebert",
    "BDAY:19910412", "GENDER:F", "X-WEILERID:301",
    "ADR;TYPE=HOME:;A.104;Beispielweg 1;Musterstadt;;12345;Deutschland",
    "NOTE:Infoveranstaltung am 14.01.2023\\nAufnahmegespräch am 28.01.2023\\n\\n"
    "Partner: Stefan Kramer\\nKinder: Mia Ebert (04.04.2019)",
)


def analyze(db, *cards: str) -> schemas.VcfAnalysisResponse:
    return member_list.analyze_vcf("".join(cards).encode("utf-8"), db)


def take_over(db, *cards: str) -> schemas.VcfCommitResponse:
    analysis = analyze(db, *cards)
    return member_list.commit_vcf(schemas.VcfCommitRequest(session_id=analysis.session_id), db)


def add_person(db, first_name, last_name, **fields) -> models.Person:
    person = models.Person(first_name=first_name, last_name=last_name, **fields)
    db.add(person)
    db.commit()
    return person


# ---------------------------------------------------------------------------

def test_fills_gaps():
    print("\n== Mitgliederliste: füllt leere Angaben ==")
    db = make_session()
    ines = add_person(db, "Ines", "Ebert")

    analysis = analyze(db, INES)
    check_equal("Zusammenfassung: eine Person bekommt Angaben", analysis.fills.persons, 1)
    check_equal("Zusammenfassung je Angabe",
                (analysis.fills.birth_date, analysis.fills.member_since,
                 analysis.fills.member_number, analysis.fills.gender), (1, 1, 1, 1))
    db.refresh(ines)
    check_equal("die Analyse schreibt nichts", ines.member_number, None)

    result = take_over(db, INES)

    db.refresh(ines)
    check_equal("Geburtsdatum", ines.birth_date, datetime(1991, 4, 12))
    check_equal("„Mitglied seit“ aus dem Notizfeld", ines.member_since, datetime(2023, 1, 28))
    check_equal("Mitgliedsnummer", ines.member_number, "301")
    check_equal("Geschlecht", ines.gender, "f")
    check_equal("Zähler nach dem Übernehmen", result.fills.persons, 1)
    db.close()


def test_never_overwrites():
    print("\n== Mitgliederliste: vorhandene Werte bleiben, auch wenn sie abweichen ==")
    db = make_session()
    ines = add_person(
        db, "Ines", "Ebert", member_number="301", gender="d",
        birth_date=datetime(1991, 4, 12), member_since=datetime(2023, 1, 1))

    analysis = analyze(db, INES)
    check_equal("nichts zu füllen", analysis.fills.persons, 0)
    check_equal("abweichendes „Mitglied seit“ wird gelistet",
                [(d.person, d.stored, d.member_list, d.days)
                 for d in analysis.member_since_deviations],
                [("Ines Ebert", "2023-01-01", "2023-01-28", 27)])

    take_over(db, INES)

    db.refresh(ines)
    check_equal("„Mitglied seit“ nicht überschrieben", ines.member_since, datetime(2023, 1, 1))
    check_equal("Geschlecht nicht überschrieben", ines.gender, "d")
    db.close()


def test_creates_nothing_and_leaves_households_alone():
    print("\n== Mitgliederliste: legt nichts an und fasst keine Haushalte an ==")
    db = make_session()
    household = models.Household(name="Unser Name für Ebert")
    db.add(household)
    db.flush()
    add_person(db, "Ines", "Ebert", household_id=household.id)
    stranger = card("Stefan", "Kramer", "X-WEILERID:302", "BDAY:19850314")

    analysis = analyze(db, INES, stranger)
    check_equal("Karte ohne Treffer wird gezählt", analysis.unmatched_cards, 1)

    take_over(db, INES, stranger)

    db.refresh(household)
    check_equal("keine Person angelegt (auch kein Kind, kein Partner aus der Notiz)",
                sorted(p.first_name for p in db.query(models.Person).all()), ["Ines"])
    check_equal("kein Haushalt angelegt", db.query(models.Household).count(), 1)
    check_equal("Haushaltsname unverändert", household.name, "Unser Name für Ebert")
    check_equal("keine Wohnungsnummer gesetzt", household.apartment_unit, None)
    check("kein Bewohner-Haushalt geworden", not household.is_resident)
    db.close()


def test_member_number_someone_else_holds_is_not_stored():
    print("\n== Mitgliederliste: vergebene Mitgliedsnummer wird nicht gespeichert ==")
    db = make_session()
    ines = add_person(db, "Ines", "Ebert")
    add_person(db, "Antje", "Vogel", member_number="301")

    analysis = analyze(db, INES)
    check_equal("Zusammenfassung nennt Person, Nummer und Träger",
                [(c.person, c.member_number, c.holder) for c in analysis.member_numbers_not_stored],
                [("Ines Ebert", "301", "Antje Vogel")])

    result = take_over(db, INES)

    db.refresh(ines)
    check_equal("Nummer nicht gespeichert", ines.member_number, None)
    check_equal("die übrigen Lücken sind gefüllt", ines.birth_date, datetime(1991, 4, 12))
    check_equal("auch das Ergebnis nennt Person, Nummer und Träger",
                [(c.person, c.member_number, c.holder) for c in result.member_numbers_not_stored],
                [("Ines Ebert", "301", "Antje Vogel")])
    db.close()


def test_two_cards_for_one_person_fill_nothing():
    print("\n== Mitgliederliste: zwei Karten für eine Person füllen nichts ==")
    db = make_session()
    hanna = add_person(db, "Hanna", "Kern")
    # Zwei Mitglieder gleichen Namens, im Datenbestand steht nur eines davon.
    first = card("Hanna", "Kern", "X-WEILERID:101", "NOTE:Aufnahmegespräch am 28.01.2023")
    second = card("Hanna", "Kern", "BDAY:19800101", "GENDER:F")

    analysis = analyze(db, first, second)
    check_equal("nichts zu füllen", analysis.fills.persons, 0)
    check_equal("beide Karten gelten als nicht zugeordnet", analysis.unmatched_cards, 2)

    take_over(db, first, second)

    db.refresh(hanna)
    check_equal("keine Angabe aus einer der Karten",
                (hanna.member_number, hanna.member_since, hanna.birth_date, hanna.gender),
                (None, None, None, None))
    db.close()


def test_additional_first_names_belong_to_the_name():
    print("\n== Mitgliederliste: weitere Vornamen gehören zum Namen ==")
    db = make_session()
    anna = add_person(db, "Anna Maria", "Berger")
    with_second_name = "\n".join([
        "BEGIN:VCARD", "VERSION:3.0", "FN:Anna Berger", "N:Berger;Anna;Maria;;",
        "BDAY:19920708", "END:VCARD", ""])

    take_over(db, with_second_name)

    db.refresh(anna)
    check_equal("Karte trifft die Person", anna.birth_date, datetime(1992, 7, 8))
    db.close()


def test_cards_without_effect_are_counted():
    print("\n== Mitgliederliste: Karten ohne Änderung werden gezählt ==")
    db = make_session()
    add_person(db, "Ines", "Ebert", member_number="301", gender="f",
               birth_date=datetime(1991, 4, 12), member_since=datetime(2023, 1, 28))
    add_person(db, "Hanna", "Kern")
    with_gap = card("Hanna", "Kern", "BDAY:19800101")

    analysis = analyze(db, INES, with_gap)
    check_equal("eine Karte füllt, eine ändert nichts",
                (analysis.fills.persons, analysis.unchanged_cards, analysis.unmatched_cards),
                (1, 1, 0))
    db.close()


def test_second_run_changes_nothing():
    print("\n== Mitgliederliste: zweites Einlesen ändert nichts ==")
    db = make_session()
    ines = add_person(db, "Ines", "Ebert")
    take_over(db, INES)
    db.refresh(ines)
    first_run = (ines.birth_date, ines.member_since, ines.member_number, ines.gender,
                 ines.updated_at)

    again = analyze(db, INES)
    check_equal("nichts mehr zu füllen", again.fills.persons, 0)
    take_over(db, INES)

    db.refresh(ines)
    check_equal("Person unverändert",
                (ines.birth_date, ines.member_since, ines.member_number, ines.gender,
                 ines.updated_at), first_run)
    db.close()


if __name__ == "__main__":
    test_fills_gaps()
    test_never_overwrites()
    test_creates_nothing_and_leaves_households_alone()
    test_member_number_someone_else_holds_is_not_stored()
    test_two_cards_for_one_person_fill_nothing()
    test_additional_first_names_belong_to_the_name()
    test_cards_without_effect_are_counted()
    test_second_run_changes_nothing()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

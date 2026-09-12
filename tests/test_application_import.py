# -*- coding: utf-8 -*-
"""Tests für den Import der gepflegten Bewerbungsliste.

Aufruf aus dem Projekt-Root:  python tests/test_application_import.py

Die Testdatei wird im Speicher erzeugt; es wird keine Datei gelesen und die
Anwendungsdatenbank (housing.db) nicht angefasst.
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

from backend import models, schemas, services, application_import_service as ais

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


COLUMNS = [
    "Haushalt", "Typ", "Aktueller Typ", "Aktuelle Wohnung", "(Wechsel-)Wunsch",
    "Mail / Info von", "Status", "neue Wohnung", "Kommentar",
]


def build_xlsx(rows: list[dict]) -> bytes:
    df = pd.DataFrame([{c: r.get(c, "") for c in COLUMNS} for r in rows])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


def seed(db):
    """Ein Bewohner-Haushalt in R.106 und eine Person ohne Haushalt."""
    apt = models.Apartment(unit_number="R.106", size_rooms=1, funding_type="WBS A",
                           apartment_category="Standard Wohnungstypen")
    target = models.Apartment(unit_number="W.204", size_rooms=2, funding_type="WBS A",
                              apartment_category="Standard Wohnungstypen")
    hh = models.Household(name="Claudia Heemann", is_resident=True)
    db.add_all([apt, target, hh])
    db.flush()
    db.add(models.Person(household_id=hh.id, first_name="Claudia", last_name="Heemann"))
    db.add(models.Person(first_name="Jenny", last_name="Settmann"))  # ohne Haushalt
    apt.household_id = hh.id
    hh.apartment_unit = "R.106"
    db.commit()
    return hh


# ---------------------------------------------------------------------------

def test_parse_kind_and_status():
    print("\n== Typ und Status ==")
    check_equal("Wechselwunsch", ais.parse_kind("Wechselwunsch"), "wechselwunsch")
    check_equal("Wartepool", ais.parse_kind("Wartepool"), "wartepool")
    check_equal("Joker", ais.parse_kind("Joker"), "joker")
    check_equal("leer", ais.parse_kind(""), None)

    check_equal("offen", ais.parse_status("offen"), "offen")
    check_equal("erfüllt", ais.parse_status("erfüllt"), "erfuellt")
    # Die Liste bricht das Wort über zwei Zeilen um
    check_equal("zurück-\\ngezogen", ais.parse_status("zurück-\ngezogen"), "zurueckgezogen")
    check_equal("zurückgezogen", ais.parse_status("zurückgezogen"), "zurueckgezogen")
    check_equal("leer", ais.parse_status(""), None)


def test_split_person_names():
    print("\n== Namen der Spalte 'Haushalt' ==")
    check_equal("einzelner Name",
                ais.split_person_names("Annette Schulte Bocholt"), ["Annette Schulte Bocholt"])
    check_equal("Paar mit gemeinsamem Nachnamen",
                ais.split_person_names("Christine (Tine) und Simon Langkamp"),
                ["Christine Langkamp", "Simon Langkamp"])
    check_equal("Paar mit eigenen Nachnamen",
                ais.split_person_names("Dan Van Loey und Sarah Kiesgen"),
                ["Dan Van Loey", "Sarah Kiesgen"])
    check_equal("leer", ais.split_person_names(""), [])


def test_analyze_matches_by_apartment():
    print("\n== Zuordnung über die Wohnungsnummer ==")
    db = make_session()
    hh = seed(db)
    contents = build_xlsx([
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch", "Aktueller Typ": "1,5 A",
         "Aktuelle Wohnung": "R.106", "(Wechsel-)Wunsch": "2,5 A",
         "Mail / Info von": "21.03.2021", "Status": "offen",
         "Kommentar": "Möchte gerne eine Wohnung im obersten Stockwerk."},
    ])
    result = ais.analyze_application_list(contents, db)
    preview = result.households[0]

    check_equal("ein Datensatz", len(result.households), 1)
    check_equal("Haushalt über die Wohnungsnummer gefunden",
                preview.match_result.matched_household_id, hh.id)
    check_equal("Bewerbungsart erkannt", preview.kind, "wechselwunsch")
    check_equal("Wunschdatum erkannt", preview.requested_at, "2021-03-21")
    check_equal("Wunsch strukturiert",
                [w.model_dump() for w in preview.wishes],
                [{"size_rooms": 2, "funding_type": "WBS A", "apartment_category": None}])
    check("Kommentar übernommen", preview.note.startswith("Möchte gerne"))
    check("keine Wohnungsabweichung", not preview.apartment_mismatch)
    check("keine unbekannte Wohnung", not preview.unknown_apartment)
    db.close()


def test_analyze_flags_mismatch_and_unparsed():
    print("\n== Warnungen im Assistenten ==")
    db = make_session()
    seed(db)
    contents = build_xlsx([
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch",
         "Aktuelle Wohnung": "P.999", "(Wechsel-)Wunsch": "2,5 A, ter",
         "Status": "offen"},
    ])
    preview = ais.analyze_application_list(contents, db).households[0]
    check("unbekannte Wohnungsnummer gemeldet", preview.unknown_apartment)
    check_equal("nicht erkannter Wunschteil gemeldet", preview.unparsed_wishes, ["ter"])
    db.close()


def test_commit_creates_household():
    print("\n== Haushalt neu anlegen ==")
    db = make_session()
    seed(db)
    person = db.query(models.Person).filter(models.Person.household_id.is_(None)).first()
    contents = build_xlsx([
        {"Haushalt": "Jenny Settmann", "Typ": "Wartepool", "(Wechsel-)Wunsch": "2,5 A",
         "Mail / Info von": "26.07.2023", "Status": "offen",
         "Kommentar": "Wohnungsamt hat den ersten WBS erteilt."},
    ])
    analysis = ais.analyze_application_list(contents, db)
    preview = analysis.households[0]
    check("Person ohne Haushalt vorgeschlagen",
          person.id in [c.person_id for c in preview.person_candidates],
          str([c.name for c in preview.person_candidates]))

    result = ais.commit_application_list(schemas.ApplicationCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.ApplicationDecision(
            temp_id=preview.temp_id, action="create_household",
            household_name="Jenny Settmann", person_ids=[person.id],
        )],
    ), db)

    check_equal("ein Haushalt angelegt", result.households_created, 1)
    check_equal("eine Person zugeordnet", result.persons_assigned, 1)
    check_equal("eine Bewerbung angelegt", result.applications_created, 1)

    hh = db.query(models.Household).filter(models.Household.name == "Jenny Settmann").first()
    check("Person hängt am neuen Haushalt", person.household_id == hh.id)
    application = services.open_applications(db, hh.id)[0]
    check_equal("Art", application.kind, "wartepool")
    check_equal("Datum", application.requested_at, datetime(2023, 7, 26))
    check_equal("Wunsch", application.wishes,
                [{"size_rooms": 2, "funding_type": "WBS A", "apartment_category": None}])
    check("Kommentar gespeichert", application.note.startswith("Wohnungsamt"))
    check("Sonderfall wird nicht automatisch gesetzt", not application.special_case)
    db.close()


def test_commit_updates_existing_application():
    print("\n== Bestehende Bewerbung aktualisieren ==")
    db = make_session()
    hh = seed(db)
    db.add(models.Application(household_id=hh.id, kind="wechselwunsch", status="offen",
                             wishes=[], requested_at=datetime(2020, 1, 1)))
    db.commit()

    contents = build_xlsx([
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch", "Aktuelle Wohnung": "R.106",
         "(Wechsel-)Wunsch": "2,5 A", "Mail / Info von": "21.03.2021", "Status": "offen"},
    ])
    analysis = ais.analyze_application_list(contents, db)
    preview = analysis.households[0]
    check("bestehende offene Bewerbung erkannt", preview.existing_application_id is not None)

    result = ais.commit_application_list(schemas.ApplicationCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.ApplicationDecision(
            temp_id=preview.temp_id, action="update", target_household_id=hh.id)],
    ), db)
    check_equal("aktualisiert statt angelegt", result.applications_updated, 1)
    check_equal("keine neue Bewerbung", result.applications_created, 0)
    check_equal("nur eine offene Bewerbung", len(services.open_applications(db, hh.id)), 1)
    db.close()


def test_commit_links_fulfilled_apartment():
    print("\n== Erfüllte Bewerbung ==")
    db = make_session()
    hh = seed(db)
    contents = build_xlsx([
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch", "Aktuelle Wohnung": "R.106",
         "(Wechsel-)Wunsch": "2,5 A", "Mail / Info von": "21.03.2021",
         "Status": "erfüllt", "neue Wohnung": "W.204"},
    ])
    analysis = ais.analyze_application_list(contents, db)
    preview = analysis.households[0]
    ais.commit_application_list(schemas.ApplicationCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.ApplicationDecision(
            temp_id=preview.temp_id, action="create", target_household_id=hh.id)],
    ), db)

    application = db.query(models.Application).first()
    check_equal("Status erfüllt", application.status, "erfuellt")
    check("neue Wohnung verknüpft",
          application.fulfilled_apartment is not None
          and application.fulfilled_apartment.unit_number == "W.204")
    check_equal("keine offene Bewerbung mehr", len(services.open_applications(db, hh.id)), 0)
    db.close()


def test_column_header_variants():
    """Die gepflegte Liste schreibt ihre Kopfzeile nicht buchstabengetreu.

    "(Wechsel-) Wunsch" mit Leerzeichen hinter dem Bindestrich, "Mail / Info
    vom" statt "von": Wird eine Spalte dabei nicht erkannt, fällt sie
    **stillschweigend** aus dem Import -- so blieb der Wunsch leer.
    """
    print("\n== Schreibweisen der Kopfzeile ==")
    db = make_session()
    seed(db)
    df = pd.DataFrame([{
        "Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch",
        "Aktueller Typ": "1,5 A", "Aktuelle Wohnung": "R.106",
        "(Wechsel-) Wunsch": "1,5 A\n1,5 B", "Mail / Info vom": "19.04.2021",
        "Status": "offen", "neue Wohnung": "", "Kommentar": "",
    }])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)

    columns = ais._column_map(df)
    check_equal("Wunsch-Spalte erkannt", columns.get("wish"), "(Wechsel-) Wunsch")
    check_equal("Datums-Spalte erkannt", columns.get("requested_at"), "Mail / Info vom")
    check_equal("Typ-Spalte nicht mit 'Aktueller Typ' verwechselt", columns.get("kind"), "Typ")
    check_equal("Aktueller Typ eigenständig", columns.get("current_type"), "Aktueller Typ")

    preview = ais.analyze_application_list(buffer.getvalue(), db).households[0]
    check_equal("Wunsch übernommen",
                [x.model_dump() for x in preview.wishes],
                [{"size_rooms": 1, "funding_type": "WBS A", "apartment_category": None},
                 {"size_rooms": 1, "funding_type": "WBS B", "apartment_category": None}])
    check_equal("Datum übernommen", preview.requested_at, "2021-04-19")
    db.close()


def test_reimport_updates_history_rows():
    """Die Liste wird wiederholt eingelesen -- ohne Dubletten zu erzeugen.

    Gälte nur eine **offene** Bewerbung als vorhanden, legte jeder erneute
    Import für jede erfüllte oder zurückgezogene Zeile eine weitere Bewerbung an.
    Kennung ist deshalb Haushalt + Art + Zeitpunkt des Wunsches.
    """
    print("\n== Erneuter Import derselben Liste ==")
    db = make_session()
    hh = seed(db)
    rows = [
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch", "Aktuelle Wohnung": "R.106",
         "(Wechsel-)Wunsch": "2,5 A", "Mail / Info von": "21.03.2021",
         "Status": "zurück-gezogen"},
    ]

    def run(contents):
        analysis = ais.analyze_application_list(contents, db)
        preview = analysis.households[0]
        action = "update" if preview.existing_application_id else "create"
        result = ais.commit_application_list(schemas.ApplicationCommitRequest(
            session_id=analysis.session_id,
            decisions=[schemas.ApplicationDecision(
                temp_id=preview.temp_id, action=action, target_household_id=hh.id)],
        ), db)
        return preview, result

    preview, result = run(build_xlsx(rows))
    check("beim ersten Import nichts vorhanden", preview.existing_application_id is None)
    check_equal("angelegt", result.applications_created, 1)

    # Zweiter Durchlauf mit korrigiertem Wunsch
    rows[0]["(Wechsel-)Wunsch"] = "2,5 A\n2,5 B"
    preview, result = run(build_xlsx(rows))
    check("zurückgezogene Bewerbung wird wiedererkannt",
          preview.existing_application_id is not None)
    check_equal("aktualisiert statt angelegt", result.applications_updated, 1)
    check_equal("keine Dublette", db.query(models.Application).count(), 1)
    check_equal("korrigierter Wunsch übernommen",
                db.query(models.Application).first().wishes,
                [{"size_rooms": 2, "funding_type": "WBS A", "apartment_category": None},
                 {"size_rooms": 2, "funding_type": "WBS B", "apartment_category": None}])

    # Eine zweite Zeile desselben Haushalts mit anderem Datum ist eine eigene
    # Bewerbung -- die Liste führt Wechselwünsche über die Jahre.
    rows.append({"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch",
                 "Aktuelle Wohnung": "R.106", "(Wechsel-)Wunsch": "3,5 B",
                 "Mail / Info von": "05.08.2024", "Status": "offen"})
    analysis = ais.analyze_application_list(build_xlsx(rows), db)
    second = analysis.households[1]
    check("zweite Zeile gilt als neu", second.existing_application_id is None)
    db.close()


def test_two_rows_without_date_stay_two_applications():
    """Mehrere gleichartige Zeilen eines Haushalts ohne Datum bleiben getrennt.

    Die Liste führt Bewerbungen, deren „Mail / Info von" leer ist. Ohne Datum ist
    der Status das einzige Unterscheidungsmerkmal — und keine Bewerbung darf von
    zwei Zeilen beschrieben werden, sonst löschen sie sich gegenseitig aus.
    """
    print("\n== Zwei Zeilen ohne Datum ==")
    db = make_session()
    hh = seed(db)
    rows = [
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch", "Aktuelle Wohnung": "R.106",
         "(Wechsel-)Wunsch": "2,5 A", "Status": "erfüllt", "neue Wohnung": "W.204"},
        {"Haushalt": "Claudia Heemann", "Typ": "Wechselwunsch", "Aktuelle Wohnung": "R.106",
         "(Wechsel-)Wunsch": "3,5 B", "Status": "offen"},
    ]

    def run():
        analysis = ais.analyze_application_list(build_xlsx(rows), db)
        decisions = [
            schemas.ApplicationDecision(
                temp_id=p.temp_id,
                action="update" if p.existing_application_id else "create",
                target_household_id=hh.id,
            )
            for p in analysis.households
        ]
        return analysis, ais.commit_application_list(schemas.ApplicationCommitRequest(
            session_id=analysis.session_id, decisions=decisions), db)

    analysis, result = run()
    check_equal("erster Import: zwei Bewerbungen", result.applications_created, 2)

    analysis, result = run()
    check_equal("zweiter Import: beide wiedererkannt", result.applications_updated, 2)
    check_equal("zweiter Import: nichts angelegt", result.applications_created, 0)
    check_equal("insgesamt zwei Bewerbungen", db.query(models.Application).count(), 2)
    wishes_by_status = {
        a.status: a.wishes for a in db.query(models.Application).all()
    }
    check_equal("erfüllte Zeile behält ihren Wunsch",
                wishes_by_status.get("erfuellt"),
                [{"size_rooms": 2, "funding_type": "WBS A", "apartment_category": None}])
    check_equal("offene Zeile behält ihren Wunsch",
                wishes_by_status.get("offen"),
                [{"size_rooms": 3, "funding_type": "WBS B", "apartment_category": None}])
    db.close()


def test_commit_skips():
    print("\n== Überspringen ==")
    db = make_session()
    seed(db)
    contents = build_xlsx([
        {"Haushalt": "Unbekannt Jemand", "Typ": "Wartepool", "(Wechsel-)Wunsch": "2,5 A"},
    ])
    analysis = ais.analyze_application_list(contents, db)
    result = ais.commit_application_list(schemas.ApplicationCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.ApplicationDecision(
            temp_id=analysis.households[0].temp_id, action="skip")],
    ), db)
    check_equal("übersprungen", result.skipped, 1)
    check_equal("nichts angelegt", db.query(models.Application).count(), 0)
    db.close()


if __name__ == "__main__":
    test_parse_kind_and_status()
    test_split_person_names()
    test_analyze_matches_by_apartment()
    test_analyze_flags_mismatch_and_unparsed()
    test_commit_creates_household()
    test_commit_updates_existing_application()
    test_commit_links_fulfilled_apartment()
    test_column_header_variants()
    test_reimport_updates_history_rows()
    test_two_rows_without_date_stay_two_applications()
    test_commit_skips()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

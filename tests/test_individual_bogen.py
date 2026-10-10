# -*- coding: utf-8 -*-
"""Tests für das, was der Individualbogen bei einer Person einträgt.

Geprüft wird über Analyse und Übernehmen: Eine Exportdatei entsteht im
Speicher, die Analyse liefert die Vorschau, und nach dem Übernehmen der
Entscheidungen zählt der Datenbestand. Die Treffersicherheit steht in
``test_matching.py``.

Aufruf aus dem Projekt-Root:  python tests/test_individual_bogen.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import import_service, schemas

from test_matching import add_person, individual_xlsx, make_session  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def check_equal(label: str, actual, expected):
    check(label, actual == expected, f"(erwartet {expected!r}, war {actual!r})")


def analyze(db, *rows: dict) -> schemas.IndividualAnalysisResponse:
    return import_service.analyze_individual_bogen(individual_xlsx(*rows), db)


def commit_to(db, analysis, person) -> schemas.IndividualCommitResponse:
    """Übernimmt die erste Zeile der Analyse für ``person``."""
    return import_service.commit_individual_bogen(schemas.IndividualCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.IndividualDecision(
            temp_id=analysis.individuals[0].temp_id, action="update",
            target_person_id=person.id)],
    ), db)


# ---------------------------------------------------------------------------

def test_fills_gaps_and_overwrites_diversity_answers():
    print("\n== Individualbogen: ergänzt Lücken, überschreibt die Angaben zur Durchmischung ==")
    db = make_session()
    newcomer = add_person(db, "Ines", "Ebert", gender="m")

    analysis = analyze(db, {
        "Nachname, Vorname": "Ebert, Ines", "Mitgliedsnummer": "301",
        "Geburtsdatum": "1991-04-12", "Mitglied seit": "2025-10-01",
        "Geschlecht": "weiblich"})
    check_equal("Vorschau zeigt „Mitglied seit“",
                analysis.individuals[0].member_since, "2025-10-01")
    commit_to(db, analysis, newcomer)

    db.refresh(newcomer)
    check_equal("„Mitglied seit“ ergänzt", newcomer.member_since, datetime(2025, 10, 1))
    check_equal("Geburtsdatum ergänzt", newcomer.birth_date, datetime(1991, 4, 12))
    check_equal("Mitgliedsnummer ergänzt", newcomer.member_number, "301")
    check_equal("Geschlecht überschrieben", newcomer.gender, "f")
    check_equal("Name unverändert", (newcomer.first_name, newcomer.last_name), ("Ines", "Ebert"))
    db.close()


def test_keeps_existing_values():
    print("\n== Individualbogen: vorhandene Werte bleiben ==")
    db = make_session()
    member = add_person(
        db, "Stefan", "Kramer", member_number="302",
        birth_date=datetime(1985, 3, 14), member_since=datetime(2023, 3, 11))

    # Gerundetes Eintrittsdatum und abweichende Nummer aus der Selbstauskunft
    analysis = analyze(db, {
        "Nachname, Vorname": "Kramer, Stefan", "Mitgliedsnummer": "320",
        "Mitglied seit": "2023-01-01"})
    commit_to(db, analysis, member)

    db.refresh(member)
    check_equal("„Mitglied seit“ bleibt", member.member_since, datetime(2023, 3, 11))
    check_equal("Mitgliedsnummer bleibt", member.member_number, "302")
    check_equal("Geburtsdatum bleibt", member.birth_date, datetime(1985, 3, 14))
    db.close()


def test_rejects_implausible_member_since():
    print("\n== Individualbogen: unplausibles „Mitglied seit“ wird nicht übernommen ==")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    for label, value in (("reine Jahreszahl", "2019"), ("Datum in der Zukunft", tomorrow)):
        db = make_session()
        newcomer = add_person(db, "Ines", "Ebert")

        analysis = analyze(db, {"Nachname, Vorname": "Ebert, Ines", "Mitglied seit": value})
        preview = analysis.individuals[0]
        check_equal(f"{label}: Vorschau ohne Datum", preview.member_since, None)
        check_equal(f"{label}: Hinweis nennt den Wert", preview.member_since_rejected, value)
        commit_to(db, analysis, newcomer)

        db.refresh(newcomer)
        check_equal(f"{label}: nichts gespeichert", newcomer.member_since, None)
        db.close()


def test_does_not_store_a_member_number_someone_else_holds():
    print("\n== Individualbogen: vergebene Mitgliedsnummer wird nicht ergänzt ==")
    db = make_session()
    add_person(db, "Moritz", "Bauer", member_number="431")
    child = add_person(db, "Lina", "Bauer")

    analysis = analyze(db, {"Nachname, Vorname": "Bauer, Lina", "Mitgliedsnummer": "431"})
    preview = analysis.individuals[0]
    check_equal("Hinweis nennt, wer die Nummer trägt",
                preview.member_number_holder, "Moritz Bauer")
    commit_to(db, analysis, child)

    db.refresh(child)
    check_equal("Nummer nicht gespeichert", child.member_number, None)

    own = analyze(db, {
        "Zeitstempel": "2026-09-02T10:00:00+02:00",
        "Nachname, Vorname": "Bauer, Moritz", "Mitgliedsnummer": "431"})
    check_equal("kein Hinweis bei der eigenen Nummer",
                own.individuals[0].member_number_holder, None)
    db.close()


def test_without_member_since_column():
    print("\n== Individualbogen: Datei ohne Spalte „Mitglied seit“ ==")
    db = make_session()
    newcomer = add_person(db, "Ines", "Ebert")

    analysis = analyze(db, {"Nachname, Vorname": "Ebert, Ines"})
    preview = analysis.individuals[0]
    check_equal("Vorschau ohne Datum", preview.member_since, None)
    check_equal("kein Hinweis", preview.member_since_rejected, None)
    commit_to(db, analysis, newcomer)

    db.refresh(newcomer)
    check_equal("Geschlecht übernommen", newcomer.gender, "f")
    check_equal("kein Eintrittsdatum", newcomer.member_since, None)
    db.close()


if __name__ == "__main__":
    test_fills_gaps_and_overwrites_diversity_answers()
    test_keeps_existing_values()
    test_rejects_implausible_member_since()
    test_does_not_store_a_member_number_someone_else_holds()
    test_without_member_since_column()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

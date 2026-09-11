# -*- coding: utf-8 -*-
"""Tests für die Ist-Statistik der aktuellen Bewohner.

Aufruf aus dem Projekt-Root:  python tests/test_statistics.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import import_service, models, schemas, scoring

import example_data

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
    db = sessionmaker(bind=engine)()
    scoring.initialize_config(db)
    return db


def birth_date_for_age(years: int) -> datetime:
    now = datetime.now()
    return datetime(now.year - years, 1, 1)


def add_household(db, name, people, is_resident=True, archived=False):
    hh = models.Household(name=name, is_resident=is_resident, archived=archived)
    db.add(hh)
    db.flush()
    for kwargs in people:
        db.add(models.Person(**{"household_id": hh.id, "first_name": "P", "last_name": name, **kwargs}))
    db.flush()
    return hh


def category(stats: dict, key: str) -> dict:
    return next(c for c in stats["categories"] if c["key"] == key)


def group(stats: dict, cat_key: str, group_key: str) -> dict:
    return next(g for g in category(stats, cat_key)["groups"] if g["key"] == group_key)


def excluded(stats: dict, cat_key: str, group_key: str) -> dict:
    return next(g for g in category(stats, cat_key)["excluded_groups"] if g["key"] == group_key)


def missing_of(entry: dict, dimension: str) -> dict | None:
    return next((m for m in entry["missing"] if m["dimension"] == dimension), None)


def entry_for(entries: list, first_name: str) -> dict | None:
    return next((e for e in entries if e["first_name"] == first_name), None)


def test_counts_only_residents():
    print("\n== Bezugsmenge ==")
    db = make_session()
    add_household(db, "Bewohner", [
        {"birth_date": birth_date_for_age(35), "gender": "w", "occupation_type": "4", "education_level": "6"},
        {"birth_date": birth_date_for_age(42), "gender": "m", "occupation_type": "5", "education_level": "7"},
    ])
    add_household(db, "Bewerber", [
        {"birth_date": birth_date_for_age(30), "gender": "w"},
    ], is_resident=False)
    add_household(db, "Archiviert", [
        {"birth_date": birth_date_for_age(60), "gender": "m"},
    ], archived=True)

    stats = scoring.calculate_resident_statistics(db)
    check("nur Bewohner-Haushalte", stats["household_count"] == 1, f"war {stats['household_count']}")
    check("nur Bewohner-Personen", stats["person_count"] == 2, f"war {stats['person_count']}")
    check("Altersgruppe 30 bis 39 absolut", group(stats, "age", "30_39")["count"] == 1)
    check("Altersgruppe 40 bis 49 absolut", group(stats, "age", "40_49")["count"] == 1)
    check("Geschlecht weiblich relativ", group(stats, "gender", "f")["ratio"] == 0.5)


def test_archived_person_excluded():
    print("\n== Archivierte Personen ==")
    db = make_session()
    add_household(db, "Bewohner", [
        {"birth_date": birth_date_for_age(35), "gender": "w"},
        {"birth_date": birth_date_for_age(35), "gender": "m", "archived": True},
    ])

    stats = scoring.calculate_resident_statistics(db)
    check("archivierte Person zählt nicht", stats["person_count"] == 1, f"war {stats['person_count']}")
    check("Geschlecht männlich bleibt leer", group(stats, "gender", "m")["count"] == 0)


def test_missing_values_are_ignored():
    print("\n== Fehlende Angaben werden ignoriert ==")
    db = make_session()
    add_household(db, "Bewohner", [
        {"birth_date": None, "gender": None, "occupation_type": "0", "education_level": ""},
        {"birth_date": birth_date_for_age(45), "gender": "divers", "occupation_type": "3", "education_level": "8"},
    ])

    stats = scoring.calculate_resident_statistics(db)
    check("keine Ausprägung 'keine Angabe' mehr",
          all(g["key"] != scoring.UNKNOWN_GROUP for c in stats["categories"] for g in c["groups"]))
    check_equal("fehlendes Geburtsdatum als ohne Angabe gezählt",
                category(stats, "age")["unknown_count"], 1)
    check("fehlendes Geburtsdatum landet nicht bei 'über 89'",
          group(stats, "age", "over_89")["count"] == 0)
    check_equal("fehlendes Geschlecht als ohne Angabe gezählt",
                category(stats, "gender")["unknown_count"], 1)
    check_equal("Berufskategorie 0 gilt als keine Angabe",
                category(stats, "occupation")["unknown_count"], 1)
    check_equal("leerer Bildungsabschluss gilt als keine Angabe",
                category(stats, "education")["unknown_count"], 1)
    check_equal("Bezugsgröße nur Personen mit Angabe", category(stats, "gender")["total"], 1)
    check_equal("divers: 1 von 1 Person mit Angabe", group(stats, "gender", "d")["ratio"], 1.0)
    check_equal("Personenzahl bleibt vollständig", stats["person_count"], 2)
    check_equal("eine Person mit fehlenden Angaben", stats["incomplete_person_count"], 1)


def test_ratios_ignore_missing():
    print("\n== Anteile ohne Datensätze ohne Angabe ==")
    db = make_session()
    # 2 Frauen, 1 Mann, 1 Person ohne Geschlecht
    add_household(db, "A", [
        {"birth_date": birth_date_for_age(35), "gender": "w"},
        {"birth_date": birth_date_for_age(36), "gender": "w"},
    ])
    add_household(db, "B", [
        {"birth_date": birth_date_for_age(50), "gender": "m"},
        {"birth_date": birth_date_for_age(52), "gender": None},
    ])

    stats = scoring.calculate_resident_statistics(db)
    check("weiblich 2 von 3 (nicht 2 von 4)",
          abs(group(stats, "gender", "f")["ratio"] - 2 / 3) < 1e-9, f"war {group(stats, 'gender', 'f')['ratio']}")
    check("männlich 1 von 3", abs(group(stats, "gender", "m")["ratio"] - 1 / 3) < 1e-9)
    target = scoring.DEFAULT_CONFIG["target_gender_f"]["value"]
    check("absoluter Zielwert bezieht sich auf Personen mit Angabe",
          abs(group(stats, "gender", "f")["target_count"] - target * 3) < 1e-9)
    check_equal("Altersgruppen unberührt: alle 4 mit Angabe", category(stats, "age")["total"], 4)

    ratios = scoring.calculate_resident_stats(db)
    check("IST-Verteilung des Scorings ebenso", abs(ratios["ratio_gender_f"] - 2 / 3) < 1e-9,
          f"war {ratios['ratio_gender_f']}")
    check("kein Anteil für 'ohne Angabe' im Scoring",
          not any(k.endswith(f"_{scoring.UNKNOWN_GROUP}") for k in ratios))


def test_groups_sum_up():
    print("\n== Summen ==")
    db = make_session()
    add_household(db, "A", [
        {"birth_date": birth_date_for_age(25), "gender": "w", "occupation_type": "1", "education_level": "4"},
        {"birth_date": birth_date_for_age(15), "gender": "m"},
        {"birth_date": None, "gender": "Frau", "occupation_type": "Handwerker", "education_level": "0"},
    ])
    add_household(db, "B", [
        {"birth_date": birth_date_for_age(95), "gender": "m", "occupation_type": "9", "education_level": "8"},
    ])

    stats = scoring.calculate_resident_statistics(db)
    for cat in stats["categories"]:
        total_count = sum(g["count"] for g in cat["groups"])
        total_ratio = sum(g["ratio"] for g in cat["groups"])
        check(f"{cat['label']}: absolute Zahlen ergeben die Bezugsgröße",
              total_count == cat["total"], f"{total_count} != {cat['total']}")
        check(f"{cat['label']}: Anteile ergeben 100 %",
              abs(total_ratio - 1.0) < 1e-9, f"war {total_ratio}")
        if cat["basis"] == "person":
            outside = sum(g["count"] for g in cat["excluded_groups"])
            check(f"{cat['label']}: Bezugsgröße + ohne Angabe + ausgenommen = alle Personen",
                  cat["total"] + cat["unknown_count"] + outside == stats["person_count"])
    check_equal("Altersgruppen: nur 25- und 95-Jährige in der Bezugsgröße",
                category(stats, "age")["total"], 2)
    check_equal("unter 20 nachrichtlich ausgewiesen", excluded(stats, "age", "under_20")["count"], 1)
    check("über 89 wird ausgewiesen", group(stats, "age", "over_89")["count"] == 1)


def test_targets_attached():
    print("\n== Zielwerte ==")
    db = make_session()
    add_household(db, "A", [
        {"birth_date": birth_date_for_age(35), "gender": "w"},
        {"birth_date": birth_date_for_age(36), "gender": "w"},
    ])

    stats = scoring.calculate_resident_statistics(db)
    thirties = group(stats, "age", "30_39")
    target = scoring.DEFAULT_CONFIG["target_age_30_39"]["value"]
    check("Zielwert je Altersgruppe geliefert", thirties["target_ratio"] == target,
          f"war {thirties['target_ratio']}")
    check("Zielwert auch absolut geliefert",
          abs(thirties["target_count"] - target * 2) < 1e-9, f"war {thirties['target_count']}")
    check("jede Altersgruppe hat einen Zielwert",
          all(g["target_ratio"] is not None for g in category(stats, "age")["groups"]))
    check("Haushaltsgröße ohne Zielwert",
          all(g["target_ratio"] is None for g in category(stats, "household_size")["groups"]))


def test_under_20_excluded():
    print("\n== Altersgruppen: Personen unter 20 ausgenommen ==")
    db = make_session()
    add_household(db, "Familie", [
        {"birth_date": birth_date_for_age(35), "gender": "w"},
        {"birth_date": birth_date_for_age(36), "gender": "m"},
        {"birth_date": birth_date_for_age(8), "gender": "w"},
        {"birth_date": birth_date_for_age(12), "gender": "m"},
    ])

    stats = scoring.calculate_resident_statistics(db)
    age = category(stats, "age")
    check("'unter 20' ist keine Ausprägung der Altersgruppen",
          all(g["key"] != "under_20" for g in age["groups"]))
    check_equal("Bezugsgröße: nur Personen ab 20", age["total"], 2)
    check_equal("unter 20 nachrichtlich ausgewiesen", excluded(stats, "age", "under_20")["count"], 2)
    check_equal("30 bis 39: 2 von 2 (nicht 2 von 4)", group(stats, "age", "30_39")["ratio"], 1.0)
    check("Anteile der Altersgruppen ergeben 100 %",
          abs(sum(g["ratio"] for g in age["groups"]) - 1.0) < 1e-9)
    target = scoring.DEFAULT_CONFIG["target_age_30_39"]["value"]
    check("absoluter Zielwert bezieht sich auf Personen ab 20",
          abs(group(stats, "age", "30_39")["target_count"] - target * 2) < 1e-9)
    check_equal("Kinder sind keine fehlende Angabe", age["unknown_count"], 0)
    check_equal("Kinder zählen bei den übrigen Merkmalen mit", category(stats, "gender")["total"], 4)
    check_equal("Kinder mit Geburtsdatum nicht in der Prüfliste (Alter)",
                [e for e in scoring.resident_people_missing_data(db) if missing_of(e, "age")], [])

    ratios = scoring.calculate_resident_stats(db)
    check_equal("IST-Verteilung des Scorings ebenso", ratios["ratio_age_30_39"], 1.0)
    check("kein Anteil 'unter 20' im Scoring", "ratio_age_under_20" not in ratios)


def test_household_sizes():
    print("\n== Haushaltsgröße ==")
    db = make_session()
    add_household(db, "Single", [{"birth_date": birth_date_for_age(40), "gender": "w"}])
    add_household(db, "Paar", [
        {"birth_date": birth_date_for_age(40), "gender": "w"},
        {"birth_date": birth_date_for_age(41), "gender": "m"},
    ])
    add_household(db, "Paar 2", [
        {"birth_date": birth_date_for_age(50), "gender": "w"},
        {"birth_date": birth_date_for_age(51), "gender": "m"},
    ])

    stats = scoring.calculate_resident_statistics(db)
    sizes = category(stats, "household_size")
    check("Bezugsgröße sind Haushalte", sizes["basis"] == "household" and sizes["total"] == 3)
    check("Haushaltsgröße kennt kein 'ohne Angabe'", sizes["unknown_count"] == 0)
    check("ein Ein-Personen-Haushalt", group(stats, "household_size", "1")["count"] == 1)
    check("zwei Zwei-Personen-Haushalte", group(stats, "household_size", "2")["count"] == 2)
    check("Anteil der Zwei-Personen-Haushalte",
          abs(group(stats, "household_size", "2")["ratio"] - 2 / 3) < 1e-9)


def test_matches_scoring_stats():
    print("\n== Gleiche Basis wie das Scoring ==")
    db = make_session()
    add_household(db, "A", [
        {"birth_date": birth_date_for_age(35), "gender": "w", "occupation_type": "4", "education_level": "6"},
        {"birth_date": birth_date_for_age(70), "gender": "m", "occupation_type": "5", "education_level": "3"},
        {"birth_date": birth_date_for_age(8), "gender": None, "occupation_type": "0", "education_level": None},
    ])

    stats = scoring.calculate_resident_statistics(db)
    ratios = scoring.calculate_resident_stats(db)
    mismatches = [
        g["key"] for c in stats["categories"] if c["basis"] == "person"
        for g in c["groups"]
        if abs(g["ratio"] - ratios.get(f"ratio_{c['key']}_{g['key']}", 0.0)) > 1e-12
    ]
    check("Anteile stimmen mit der IST-Verteilung des Scorings überein",
          not mismatches, f"abweichend: {mismatches}")


def test_scoring_ignores_missing():
    print("\n== Scoring: fehlende Angaben verzerren die Durchmischung nicht ==")
    db = make_session()
    # Einzige bekannte Angabe: weiblich. Drei Personen ohne Geschlecht.
    add_household(db, "Bewohner", [
        {"birth_date": birth_date_for_age(40), "gender": "w"},
        {"birth_date": birth_date_for_age(41), "gender": None},
        {"birth_date": birth_date_for_age(42), "gender": None},
        {"birth_date": birth_date_for_age(43), "gender": ""},
    ])
    woman = add_household(db, "Bewerberin", [{"birth_date": birth_date_for_age(40), "gender": "w"}],
                          is_resident=False)
    man = add_household(db, "Bewerber", [{"birth_date": birth_date_for_age(40), "gender": "m"}],
                        is_resident=False)

    ratios = scoring.calculate_resident_stats(db)
    config = scoring.get_config_dict(db)
    check_equal("IST weiblich = 100 % der Personen mit Angabe", ratios["ratio_gender_f"], 1.0)
    check_equal("Bewerberin: weiblich ist nicht unterrepräsentiert",
                scoring.calculate_diversity_subscores(woman, ratios, config)["diversity_gender"], 0.0)
    check("Bewerber: männlich ist unterrepräsentiert",
          scoring.calculate_diversity_subscores(man, ratios, config)["diversity_gender"] > 0.0)


def test_missing_list():
    print("\n== Prüfliste: Personen ohne Angabe ==")
    db = make_session()
    hh = add_household(db, "Bewohner", [
        {"first_name": "Komplett", "birth_date": birth_date_for_age(40), "gender": "w",
         "occupation_type": "4", "education_level": "6"},
        {"first_name": "Roh", "birth_date": None, "gender": "Frau",
         "occupation_type": "0", "education_level": None, "member_number": "042"},
        {"first_name": "Bogen", "birth_date": birth_date_for_age(30), "gender": "m",
         "occupation_type": None, "education_level": "7",
         "individual_import_timestamp": datetime(2026, 2, 1, 10, 0)},
        {"first_name": "Archiv", "gender": None, "archived": True},
    ])
    add_household(db, "Bewerber", [{"first_name": "Extern", "gender": None}], is_resident=False)

    entries = scoring.resident_people_missing_data(db)
    names = sorted(e["first_name"] for e in entries)
    check_equal("nur Bewohner mit fehlenden Angaben", names, ["Bogen", "Roh"])

    roh = entry_for(entries, "Roh")
    check_equal("Haushalt mitgeliefert", (roh["household_id"], roh["household_name"]), (hh.id, "Bewohner"))
    check_equal("Mitgliedsnummer mitgeliefert", roh["member_number"], "042")
    check_equal("Alter ohne Geburtsdatum leer", roh["age"], None)
    check_equal("Geburtsdatum: leer", missing_of(roh, "age")["reason"], scoring.MISSING_EMPTY)
    gender = missing_of(roh, "gender")
    check_equal("Geschlecht 'Frau': nicht erkannt",
                (gender["reason"], gender["raw_value"]), (scoring.MISSING_UNRECOGNIZED, "Frau"))
    check("nicht erkannter Wert ist Verdacht auf Importfehler", gender["suspected_import_error"])
    occupation = missing_of(roh, "occupation")
    check_equal("Berufskategorie 0: bewusst keine Zuordnung",
                (occupation["reason"], occupation["raw_value"]), (scoring.MISSING_CATEGORY_0, "0"))
    check("Kategorie 0 ist kein Verdacht", not occupation["suspected_import_error"])
    check("Bildung leer ohne Individualbogen ist kein Verdacht",
          not missing_of(roh, "education")["suspected_import_error"])

    bogen = entry_for(entries, "Bogen")
    check_equal("nur das fehlende Merkmal gelistet", [m["dimension"] for m in bogen["missing"]], ["occupation"])
    check("leer trotz Individualbogen ist Verdacht", missing_of(bogen, "occupation")["suspected_import_error"])

    check("Antwort passt zum API-Schema",
          all(schemas.PersonMissingData(**e) for e in entries))

    stats = scoring.calculate_resident_statistics(db)
    check_equal("Kopfzahl passt zur Prüfliste", stats["incomplete_person_count"], len(entries))
    for cat in stats["categories"]:
        if cat["basis"] == "person":
            listed = sum(1 for e in entries if missing_of(e, cat["key"]))
            check_equal(f"{cat['label']}: 'ohne Angabe' = Einträge der Prüfliste",
                        cat["unknown_count"], listed)


def test_example_data():
    print("\n== Beispieldaten ==")
    db = make_session()
    example_data.seed_example_data(db)

    stats = scoring.calculate_resident_statistics(db)
    check_equal("5 Bewohner-Haushalte", stats["household_count"], 5)
    check_equal("9 Bewohner-Personen", stats["person_count"], 9)
    check_equal("Haupttätigkeit: 8 mit Angabe", category(stats, "occupation")["total"], 8)
    check_equal("Haupttätigkeit: 1 ohne Angabe", category(stats, "occupation")["unknown_count"], 1)
    check_equal("Geschlecht vollständig", category(stats, "gender")["unknown_count"], 0)
    check_equal("Altersgruppen: Ewa (unter 20) ausgenommen", category(stats, "age")["total"], 8)
    check_equal("Altersgruppen: 1 Person unter 20", excluded(stats, "age", "under_20")["count"], 1)
    check_equal("Pädagogik: 2 von 8", group(stats, "occupation", "2")["ratio"], 2 / 8)

    entries = scoring.resident_people_missing_data(db)
    check_equal("nur Ewa Danek (Kind) ohne Angaben",
                [(e["first_name"], e["last_name"]) for e in entries], [("Ewa", "Danek")])
    ewa = entries[0]
    check_equal("Wohnung des Haushalts", ewa["apartment_unit"], "W.213")
    check("Kind unter 20", ewa["age"] is not None and ewa["age"] < 20)
    check_equal("Beruf und Bildung: Kategorie 0",
                sorted((m["dimension"], m["reason"]) for m in ewa["missing"]),
                [("education", scoring.MISSING_CATEGORY_0), ("occupation", scoring.MISSING_CATEGORY_0)])
    check("Kinder der Bewerberin Nolte nicht gelistet",
          not any(e["last_name"] == "Nolte" for e in entries))


def individual_bogen_xlsx(rows: list[dict]) -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return buffer.getvalue()


def test_import_error_is_found():
    print("\n== Beispiel: Importfehler im Individualbogen wird sichtbar ==")
    db = make_session()
    example_data.seed_example_data(db)

    # Thorsten Liebold (Mitgliedsnummer 2) füllt den Individualbogen aus. Die
    # Berufsbezeichnung weicht von der Zuordnungstabelle ab ("Handwerker" statt
    # "Handwerk"), das Geschlecht ebenfalls ("Mann") -- der Import übernimmt
    # beides roh und überschreibt damit die bisher gültigen Werte.
    contents = individual_bogen_xlsx([{
        "Zeitstempel": "2026-02-01 10:00:00",
        "Absenden?": "Ja",
        "Datenschutz": "Ich akzeptiere die Datenschutzhinweise",
        "Nachname, Vorname": "Liebold, Thorsten",
        "Mitgliedsnummer": "2",
        "Geburtsdatum": "1972-09-08",
        "Geschlecht": "Mann",
        "Berufe": "Handwerker",
        "Bildungsabschluss": "Hauptschulabschluss",
        "Lebenslage": "nein",
        "Soziodemografisches / Soziale Vielfalt": "nein",
    }])
    analysis = import_service.analyze_individual_bogen(contents, db)
    check_equal("ein Datensatz im Bogen", len(analysis.individuals), 1)
    row = analysis.individuals[0]
    thorsten = db.query(models.Person).filter(models.Person.first_name == "Thorsten").one()
    check_equal("Thorsten über die Mitgliedsnummer gefunden",
                row.match_result.matched_household_id, thorsten.id)

    import_service.commit_individual_bogen(schemas.IndividualCommitRequest(
        session_id=analysis.session_id,
        decisions=[schemas.IndividualDecision(
            temp_id=row.temp_id, action="update", target_person_id=thorsten.id)],
    ), db)
    db.refresh(thorsten)
    check_equal("Bildungsabschluss korrekt übersetzt", thorsten.education_level, "2")

    stats = scoring.calculate_resident_statistics(db)
    check_equal("Geschlecht: 1 ohne Angabe", category(stats, "gender")["unknown_count"], 1)
    check_equal("Haupttätigkeit: Ewa und Thorsten ohne Angabe",
                category(stats, "occupation")["unknown_count"], 2)
    check_equal("Handwerk zählt Thorsten nicht mehr", group(stats, "occupation", "4")["count"], 0)

    entry = entry_for(scoring.resident_people_missing_data(db), "Thorsten")
    check("Thorsten steht in der Prüfliste", entry is not None)
    if entry:
        occupation = missing_of(entry, "occupation")
        check_equal("Rohwert des Berufs sichtbar",
                    (occupation["reason"], occupation["raw_value"]),
                    (scoring.MISSING_UNRECOGNIZED, "Handwerker"))
        check_equal("Rohwert des Geschlechts sichtbar", missing_of(entry, "gender")["raw_value"], "mann")
        check("als Verdacht auf Importfehler markiert",
              all(m["suspected_import_error"] for m in entry["missing"]))
        check("Individualbogen-Zeitstempel mitgeliefert", entry["individual_import_timestamp"] is not None)

    # Korrektur im Frontend (PUT /people/{id}) behebt den Eintrag.
    thorsten.occupation_type = "4"
    thorsten.gender = "m"
    db.commit()
    check("nach Korrektur nicht mehr in der Prüfliste",
          entry_for(scoring.resident_people_missing_data(db), "Thorsten") is None)


def test_empty_database():
    print("\n== Ohne Bewohner ==")
    db = make_session()
    add_household(db, "Bewerber", [{"birth_date": birth_date_for_age(30)}], is_resident=False)

    stats = scoring.calculate_resident_statistics(db)
    check("keine Haushalte", stats["household_count"] == 0)
    check("keine Personen", stats["person_count"] == 0)
    check("Anteile bleiben 0", all(g["ratio"] == 0.0 for g in category(stats, "age")["groups"]))
    check("Haushaltsgröße ohne Zeilen", category(stats, "household_size")["groups"] == [])
    check("Prüfliste leer", scoring.resident_people_missing_data(db) == [])


if __name__ == "__main__":
    print("=" * 50)
    print("Tests: Ist-Statistik der aktuellen Bewohner")
    print("=" * 50)

    test_counts_only_residents()
    test_archived_person_excluded()
    test_missing_values_are_ignored()
    test_ratios_ignore_missing()
    test_groups_sum_up()
    test_targets_attached()
    test_under_20_excluded()
    test_household_sizes()
    test_matches_scoring_stats()
    test_scoring_ignores_missing()
    test_missing_list()
    test_example_data()
    test_import_error_is_found()
    test_empty_database()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

# -*- coding: utf-8 -*-
"""Tests für die Ist-Statistik der aktuellen Bewohner.

Aufruf aus dem Projekt-Root:  python tests/test_statistics.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, scoring

failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


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
        db.add(models.Person(household_id=hh.id, first_name="P", last_name=name, **kwargs))
    db.flush()
    return hh


def category(stats: dict, key: str) -> dict:
    return next(c for c in stats["categories"] if c["key"] == key)


def group(stats: dict, cat_key: str, group_key: str) -> dict:
    return next(g for g in category(stats, cat_key)["groups"] if g["key"] == group_key)


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


def test_missing_values_are_unknown():
    print("\n== Fehlende Angaben ==")
    db = make_session()
    add_household(db, "Bewohner", [
        {"birth_date": None, "gender": None, "occupation_type": "0", "education_level": ""},
        {"birth_date": birth_date_for_age(45), "gender": "divers", "occupation_type": "3", "education_level": "8"},
    ])

    stats = scoring.calculate_resident_statistics(db)
    check("fehlendes Geburtsdatum ist keine Altersgruppe",
          group(stats, "age", "unknown")["count"] == 1)
    check("fehlendes Geburtsdatum landet nicht bei 'über 89'",
          group(stats, "age", "over_89")["count"] == 0)
    check("fehlendes Geschlecht ausgewiesen", group(stats, "gender", "unknown")["count"] == 1)
    check("Berufskategorie 0 gilt als keine Angabe",
          group(stats, "occupation", "unknown")["count"] == 1)
    check("leerer Bildungsabschluss gilt als keine Angabe",
          group(stats, "education", "unknown")["count"] == 1)
    check("divers erkannt", group(stats, "gender", "d")["count"] == 1)


def test_groups_sum_up():
    print("\n== Summen ==")
    db = make_session()
    add_household(db, "A", [
        {"birth_date": birth_date_for_age(25), "gender": "w", "occupation_type": "1", "education_level": "4"},
        {"birth_date": birth_date_for_age(15), "gender": "m"},
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
    check("unter 20 wird ausgewiesen", group(stats, "age", "under_20")["count"] == 1)
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
    check("unter 20 ohne Zielwert", group(stats, "age", "under_20")["target_ratio"] is None)
    check("keine Angabe ohne Zielwert", group(stats, "age", "unknown")["target_ratio"] is None)
    check("Haushaltsgröße ohne Zielwert",
          all(g["target_ratio"] is None for g in category(stats, "household_size")["groups"]))


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


def test_empty_database():
    print("\n== Ohne Bewohner ==")
    db = make_session()
    add_household(db, "Bewerber", [{"birth_date": birth_date_for_age(30)}], is_resident=False)

    stats = scoring.calculate_resident_statistics(db)
    check("keine Haushalte", stats["household_count"] == 0)
    check("keine Personen", stats["person_count"] == 0)
    check("Anteile bleiben 0", all(g["ratio"] == 0.0 for g in category(stats, "age")["groups"]))
    check("Haushaltsgröße ohne Zeilen", category(stats, "household_size")["groups"] == [])


if __name__ == "__main__":
    print("=" * 50)
    print("Tests: Ist-Statistik der aktuellen Bewohner")
    print("=" * 50)

    test_counts_only_residents()
    test_archived_person_excluded()
    test_missing_values_are_unknown()
    test_groups_sum_up()
    test_targets_attached()
    test_household_sizes()
    test_matches_scoring_stats()
    test_empty_database()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

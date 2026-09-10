# -*- coding: utf-8 -*-
"""Tests für die Eignung Haushalt <-> Wohnung und die daraus gebaute Rangliste.

Aufruf aus dem Projekt-Root:  python tests/test_ranking.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, services

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
    return sessionmaker(bind=engine)()


def add_household(db, name, members, wbs=None, score=0.0, archived=False,
                  archived_members=0):
    hh = models.Household(name=name, wbs_status=wbs, total_score=score, archived=archived)
    db.add(hh)
    db.flush()
    for i in range(members + archived_members):
        db.add(models.Person(
            household_id=hh.id,
            first_name=f"P{i}",
            last_name=name,
            archived=i >= members,
        ))
    db.flush()
    return hh


def add_apartment(db, unit, size_rooms, funding, min_occupants):
    apt = models.Apartment(
        unit_number=unit,
        size_rooms=size_rooms,
        funding_type=funding,
        min_occupants=min_occupants,
    )
    db.add(apt)
    db.flush()
    return apt


def group_of(groups, size_rooms, funding):
    for g in groups:
        if g["size_rooms"] == size_rooms and g["funding_type"] == funding:
            return g
    return None


def names(group):
    return [hh.name for hh, _ in group["households"]]


# ---------------------------------------------------------------------------

def test_wbs_level():
    print("\n== WBS-Normalisierung ==")
    check("WBS A -> A", services.wbs_level("WBS A") == "A")
    check("WBS B -> B", services.wbs_level("WBS B") == "B")
    check("Importwert Einkommensgruppe A -> A",
          services.wbs_level("WBS Einkommensgruppe A") == "A")
    check("Importwert Einkommensgruppe B -> B",
          services.wbs_level("WBS Einkommensgruppe B") == "B")
    check("kein WBS -> None", services.wbs_level("kein WBS") is None)
    check("freifinanziert -> None", services.wbs_level("freifinanziert") is None)
    check("None -> None", services.wbs_level(None) is None)
    check("leerer String -> None", services.wbs_level("  ") is None)


def test_funding_matches():
    print("\n== Foerderbedingung ==")
    check("WBS A darf WBS A", services.funding_matches("WBS A", "WBS A"))
    check("WBS A darf WBS B", services.funding_matches("WBS A", "WBS B"))
    check("WBS A darf freifinanziert", services.funding_matches("WBS A", "freifinanziert"))
    check("WBS B darf WBS B", services.funding_matches("WBS B", "WBS B"))
    check("WBS B darf freifinanziert", services.funding_matches("WBS B", "freifinanziert"))
    check("WBS B darf NICHT WBS A", not services.funding_matches("WBS B", "WBS A"))
    check("ohne WBS darf freifinanziert",
          services.funding_matches(None, "freifinanziert"))
    check("ohne WBS darf NICHT WBS A", not services.funding_matches(None, "WBS A"))
    check("ohne WBS darf NICHT WBS B", not services.funding_matches(None, "WBS B"))
    check("kein WBS darf NICHT WBS B", not services.funding_matches("kein WBS", "WBS B"))


def test_is_eligible():
    print("\n== Eignung ==")
    check("Mindestbewohnerzahl erfuellt",
          services.is_eligible(2, "WBS A", 3, 2, "WBS A"))
    check("Mindestbewohnerzahl verfehlt",
          not services.is_eligible(1, "WBS A", 3, 2, "WBS A"))
    check("Zimmerzahl = Mitgliederzahl ist erlaubt",
          services.is_eligible(3, "WBS A", 3, 2, "WBS A"))
    check("weniger Zimmer als Mitglieder ist ausgeschlossen",
          not services.is_eligible(4, "WBS A", 3, 2, "WBS A"))
    check("Wohnung ohne Zimmerangabe kennt keine Zimmerschranke",
          services.is_eligible(6, "WBS A", None, 1, "WBS A"))
    check("Wohnung ohne Zimmerangabe prueft trotzdem Mindestbewohner",
          not services.is_eligible(1, "WBS A", None, 3, "WBS A"))
    check("min_occupants None wird wie 0 behandelt",
          services.is_eligible(1, None, 2, None, "freifinanziert"))


def test_ranking_groups():
    print("\n== Rangliste ==")
    db = make_session()
    add_apartment(db, "A.1", 1, "freifinanziert", 1)
    add_apartment(db, "A.2", 3, "WBS A", 2)
    add_apartment(db, "A.3", 3, "freifinanziert", 2)
    add_apartment(db, "A.4", 5, "WBS B", 4)
    add_apartment(db, "C.1", None, "WBS A", 3)
    add_apartment(db, "C.2", None, "WBS A", 1)   # gleiche Kategorie, kleinere Schranke

    add_household(db, "Einzel", 1, wbs="WBS A", score=10.0)
    add_household(db, "Paar", 2, wbs="WBS Einkommensgruppe A", score=30.0)
    add_household(db, "PaarB", 2, wbs="WBS B", score=20.0)
    add_household(db, "Frei", 2, wbs="kein WBS", score=40.0)
    add_household(db, "Gross", 4, wbs="WBS A", score=50.0)
    db.commit()

    groups = services.build_ranking(db)

    check("alle Wohnungskategorien als Gruppe", len(groups) == 5, str(len(groups)))
    check("Gruppe ohne Zimmerangabe steht am Ende",
          groups[-1]["size_rooms"] is None)

    g1 = group_of(groups, 1, "freifinanziert")
    check("1 Zimmer/freifinanziert: nur Einpersonenhaushalte",
          names(g1) == ["Einzel"], str(names(g1)))

    g3a = group_of(groups, 3, "WBS A")
    check("3 Zimmer/WBS A: nur WBS-A-Haushalte, 4er-Haushalt passt nicht in 3 Zimmer",
          names(g3a) == ["Paar"], str(names(g3a)))

    g3f = group_of(groups, 3, "freifinanziert")
    check("3 Zimmer/freifinanziert: auch WBS-B- und Ohne-WBS-Haushalte, nach Score sortiert",
          names(g3f) == ["Frei", "Paar", "PaarB"], str(names(g3f)))

    g5b = group_of(groups, 5, "WBS B")
    check("5 Zimmer/WBS B: WBS A und B ab 4 Personen",
          names(g5b) == ["Gross"], str(names(g5b)))

    gnone = group_of(groups, None, "WBS A")
    check("ohne Zimmerangabe: kleinste Mindestbewohnerzahl der Kategorie zaehlt",
          names(gnone) == ["Gross", "Paar", "Einzel"], str(names(gnone)))

    check("Mitgliederzahl wird mitgeliefert",
          [m for _, m in gnone["households"]] == [4, 2, 1])
    db.close()


def test_ranking_excludes_archived():
    print("\n== Archivierte ==")
    db = make_session()
    add_apartment(db, "A.1", 3, "freifinanziert", 1)
    add_household(db, "Aktiv", 2, score=10.0)
    add_household(db, "Archiviert", 2, score=99.0, archived=True)
    # 4 Personen, davon 2 archiviert -> zaehlt als 2er-Haushalt
    add_household(db, "MitArchivPerson", 2, score=5.0, archived_members=2)
    db.commit()

    groups = services.build_ranking(db)
    g = group_of(groups, 3, "freifinanziert")
    check("archivierte Haushalte fehlen in der Rangliste",
          names(g) == ["Aktiv", "MitArchivPerson"], str(names(g)))
    check("archivierte Personen zaehlen nicht als Mitglieder",
          dict(zip(names(g), [m for _, m in g["households"]]))["MitArchivPerson"] == 2)
    db.close()


def test_no_duplicate_rows():
    print("\n== Keine Dubletten ==")
    db = make_session()
    # zwei Wohnungen derselben Kategorie: der Haushalt darf nur einmal erscheinen
    add_apartment(db, "A.1", 3, "freifinanziert", 2)
    add_apartment(db, "A.2", 3, "freifinanziert", 2)
    add_household(db, "Paar", 2, score=10.0)
    db.commit()

    g = group_of(services.build_ranking(db), 3, "freifinanziert")
    ids = [hh.id for hh, _ in g["households"]]
    check("Haushalt erscheint genau einmal je Kategorie",
          len(ids) == len(set(ids)) == 1, str(ids))
    db.close()


def test_ranking_with_seed_data():
    print("\n== Beispieldaten ==")
    db = make_session()
    services.seed_example_data(db)
    groups = services.build_ranking(db)
    check("Kategorien aus den Wohnungsstammdaten", len(groups) > 0)
    total = {hh.id for g in groups for hh, _ in g["households"]}
    check("alle 11 Beispielhaushalte kommen irgendwo vor", len(total) == 11, str(len(total)))

    violations = []
    for g in groups:
        rooms, funding = g["size_rooms"], g["funding_type"]
        for hh, members in g["households"]:
            if rooms is not None and rooms < members:
                violations.append(f"{hh.name}: {members} Personen in {rooms} Zimmern")
            if not services.funding_matches(hh.wbs_status, funding):
                violations.append(f"{hh.name} ({hh.wbs_status}) in {funding}")
    check("keine Verletzung von Zimmer- oder Foerderbedingung",
          not violations, str(violations[:3]))
    db.close()


if __name__ == "__main__":
    test_wbs_level()
    test_funding_matches()
    test_is_eligible()
    test_ranking_groups()
    test_ranking_excludes_archived()
    test_no_duplicate_rows()
    test_ranking_with_seed_data()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

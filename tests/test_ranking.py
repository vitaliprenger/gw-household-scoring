# -*- coding: utf-8 -*-
"""Tests für die Eignung Haushalt <-> Wohnung und die daraus gebaute Rangliste.

Aufruf aus dem Projekt-Root:  python tests/test_ranking.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, scoring, services
import example_data

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
                  archived_members=0, is_resident=False):
    hh = models.Household(name=name, wbs_status=wbs, total_score=score, archived=archived,
                          is_resident=is_resident)
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


def add_apartment(db, unit, size_rooms, funding, min_occupants, category=None):
    apt = models.Apartment(
        unit_number=unit,
        size_rooms=size_rooms,
        funding_type=funding,
        min_occupants=min_occupants,
        apartment_category=category,
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
    return [e.household.name for e in group["households"]]


def entry(group, name):
    for e in group["households"]:
        if e.household.name == name:
            return e
    return None


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
          [e.members for e in gnone["households"]] == [4, 2, 1])
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
          entry(g, "MitArchivPerson").members == 2)
    db.close()


def test_ranking_excludes_residents():
    print("\n== Bestehende Bewohner ==")
    db = make_session()
    add_apartment(db, "A.1", 3, "freifinanziert", 1)
    add_household(db, "Bewerber", 2, score=10.0)
    add_household(db, "Bewohner", 2, score=99.0, is_resident=True)
    db.commit()

    groups = services.build_ranking(db)
    g = group_of(groups, 3, "freifinanziert")
    check("bestehende Bewohner fehlen in der Rangliste",
          names(g) == ["Bewerber"], str(names(g)))
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
    ids = [e.household.id for e in g["households"]]
    check("Haushalt erscheint genau einmal je Kategorie",
          len(ids) == len(set(ids)) == 1, str(ids))
    db.close()


def test_occupancy_subscore():
    print("\n== Wohnraumausnutzung (Erfuellungsgrad) ==")
    sub = scoring.calculate_occupancy_subscore
    check("3 Mitglieder fuellen 3 Zimmer aus", sub(3, 3) == 1.0)
    check("3 Mitglieder fuellen 4 Zimmer NICHT aus -> 0 Punkte", sub(3, 4) == 0.0)
    check("3 Mitglieder fuellen 5 Zimmer NICHT aus -> 0 Punkte", sub(3, 5) == 0.0)
    check("mehr Mitglieder als Zimmer gilt als ausgefuellt", sub(4, 3) == 1.0)
    check("1 Mitglied fuellt 1 Zimmer aus", sub(1, 1) == 1.0)
    check("Wohnung ohne Zimmerangabe: Mindestbelegung genuegt", sub(1, None) == 1.0)


def test_occupancy_weight():
    print("\n== Gewichtung der Wohnraumausnutzung ==")
    check("Erfuellung x Gewicht",
          scoring.calculate_occupancy_score(3, 3, {"weight_occupancy": 4.0}) == 4.0)
    check("keine Erfuellung -> 0 Punkte unabhaengig vom Gewicht",
          scoring.calculate_occupancy_score(3, 4, {"weight_occupancy": 4.0}) == 0.0)
    check("ohne Config greift der Default",
          scoring.calculate_occupancy_score(3, 3, {})
          == scoring.DEFAULT_CONFIG["weight_occupancy"]["value"])


def test_score_per_apartment_size():
    print("\n== Score je Wohnungsgroesse ==")
    db = make_session()
    db.add(models.ScoringConfig(key="weight_occupancy", value=2.0))
    add_apartment(db, "A.3", 3, "freifinanziert", 1)
    add_apartment(db, "A.4", 4, "freifinanziert", 1)
    add_household(db, "Drei", 3, score=10.0)
    db.commit()

    groups = services.build_ranking(db)
    g3 = entry(group_of(groups, 3, "freifinanziert"), "Drei")
    g4 = entry(group_of(groups, 4, "freifinanziert"), "Drei")

    check("Haushalt kommt in beiden Kategorien vor", g3 is not None and g4 is not None)
    check("3 Mitglieder / 3 Zimmer: volle Ausnutzungspunkte",
          g3.occupancy_score == 2.0, str(g3.occupancy_score))
    check("3 Mitglieder / 4 Zimmer: 0 Punkte Wohnraumausnutzung",
          g4.occupancy_score == 0.0, str(g4.occupancy_score))
    check("Grundpunktzahl bleibt in beiden Kategorien gleich",
          g3.base_score == g4.base_score == 10.0)
    check("Gesamtscore fuer 3 Zimmer hoeher als fuer 4 Zimmer",
          g3.total_score == 12.0 and g4.total_score == 10.0,
          f"{g3.total_score} / {g4.total_score}")
    db.close()


def test_occupancy_changes_order():
    print("\n== Ausnutzung beeinflusst die Reihenfolge ==")
    db = make_session()
    db.add(models.ScoringConfig(key="weight_occupancy", value=2.0))
    add_apartment(db, "A.4", 4, "freifinanziert", 1)
    add_household(db, "Drei", 3, score=10.0)   # fuellt 4 Zimmer nicht aus -> 10.0
    add_household(db, "Vier", 4, score=9.0)    # fuellt 4 Zimmer aus       -> 11.0
    db.commit()

    g = group_of(services.build_ranking(db), 4, "freifinanziert")
    check("ausfuellender Haushalt steht trotz kleinerer Grundpunktzahl vorn",
          names(g) == ["Vier", "Drei"], str(names(g)))
    check("Gesamtscores korrekt aufgeschlagen",
          [e.total_score for e in g["households"]] == [11.0, 10.0],
          str([e.total_score for e in g["households"]]))
    db.close()


def test_non_scored_categories():
    print("\n== Nicht per Scoring vergebene Wohnungsarten ==")
    check("Clusterwohnung wird nicht per Scoring vergeben",
          not services.is_scored_category("Clusterwohnung"))
    check("Joker wird nicht per Scoring vergeben",
          not services.is_scored_category("Joker"))
    check("Standard Wohnungstypen wird per Scoring vergeben",
          services.is_scored_category("Standard Wohnungstypen"))
    check("Ausbauwohnung wird per Scoring vergeben",
          services.is_scored_category("Ausbauwohnung"))
    check("Atelierwohnung wird per Scoring vergeben",
          services.is_scored_category("Atelierwohnung"))
    check("ohne Wohnungsart wird per Scoring vergeben",
          services.is_scored_category(None))

    db = make_session()
    add_apartment(db, "S.1", 3, "freifinanziert", 2, "Standard Wohnungstypen")
    add_apartment(db, "CL.1", 2, "WBS A", 2, "Clusterwohnung")
    add_apartment(db, "J.1", 1, "freifinanziert", 1, "Joker")
    add_household(db, "Paar", 2, wbs="WBS A", score=10.0)
    db.commit()

    categories = services.apartment_categories(db)
    check("nur die Standardkategorie bleibt uebrig",
          set(categories) == {(3, "freifinanziert")}, str(sorted(map(str, categories))))

    groups = services.build_ranking(db)
    check("Rangliste kennt nur die Standardkategorie", len(groups) == 1, str(len(groups)))
    check("keine Clusterwohnungs-Kategorie",
          group_of(groups, 2, "WBS A") is None)
    check("keine Joker-Kategorie",
          group_of(groups, 1, "freifinanziert") is None)
    check("geeigneter Haushalt steht weiterhin in der Standardkategorie",
          names(group_of(groups, 3, "freifinanziert")) == ["Paar"])
    db.close()


def test_seed_data_has_no_cluster_or_joker_categories():
    print("\n== Stammdaten ohne Cluster/Joker ==")
    db = make_session()
    services.seed_apartments(db)
    db.commit()

    excluded = {
        (a.size_rooms, a.funding_type)
        for a in db.query(models.Apartment)
        .filter(models.Apartment.apartment_category.in_(["Clusterwohnung", "Joker"]))
        .all()
    }
    check("Stammdaten enthalten Cluster-/Joker-Wohnungen", bool(excluded))

    scored = {
        (a.size_rooms, a.funding_type)
        for a in db.query(models.Apartment).all()
        if services.is_scored_category(a.apartment_category)
    }
    categories = set(services.apartment_categories(db))
    check("nur Kategorien der per Scoring vergebenen Wohnungen",
          categories == scored, str(sorted(map(str, categories - scored))))
    check("reine Cluster-/Joker-Kategorien fehlen",
          not (categories & (excluded - scored)),
          str(sorted(map(str, categories & (excluded - scored)))))
    db.close()


def test_ranking_with_seed_data():
    print("\n== Beispieldaten ==")
    db = make_session()
    example_data.seed_example_data(db)
    groups = services.build_ranking(db)
    check("Kategorien aus den Wohnungsstammdaten", len(groups) > 0)
    total = {e.household.id for g in groups for e in g["households"]}
    applicants = {
        hh.id for hh in db.query(models.Household).filter(
            models.Household.is_resident == False,
            models.Household.archived == False,
        ).all()
    }
    check("alle 6 Bewerber-Haushalte kommen irgendwo vor",
          total == applicants, str(sorted(applicants - total)))
    check("kein Bewohner-Haushalt in der Rangliste",
          all(not e.household.is_resident for g in groups for e in g["households"]))

    violations = []
    for g in groups:
        rooms, funding = g["size_rooms"], g["funding_type"]
        for e in g["households"]:
            hh, members = e.household, e.members
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
    test_ranking_excludes_residents()
    test_no_duplicate_rows()
    test_occupancy_subscore()
    test_occupancy_weight()
    test_score_per_apartment_size()
    test_occupancy_changes_order()
    test_non_scored_categories()
    test_seed_data_has_no_cluster_or_joker_categories()
    test_ranking_with_seed_data()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

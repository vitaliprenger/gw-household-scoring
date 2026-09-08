# -*- coding: utf-8 -*-
"""Tests für die Wohnungsstammdaten und die Zuordnung Wohnung -> Haushalt.

Aufruf aus dem Projekt-Root:  python tests/test_apartments.py

Nutzt eine eigene In-Memory-SQLite-Datenbank; die Anwendungsdatenbank
(housing.db) wird nicht angefasst.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, services, apartment_seed_data

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


def by_unit(db, unit) -> models.Apartment:
    return db.query(models.Apartment).filter(models.Apartment.unit_number == unit).first()


# ---------------------------------------------------------------------------

def test_seed_data():
    print("\n== Stammdaten ==")
    rows = apartment_seed_data.APARTMENTS
    fields = apartment_seed_data.FIELDS
    check("136 Wohnungen hinterlegt", len(rows) == 136, f"({len(rows)})")
    check("alle Zeilen vollständig", all(len(r) == len(fields) for r in rows))

    units = [dict(zip(fields, r))["unit_number"] for r in rows]
    check("Wohnungsnummern eindeutig", len(set(units)) == len(units))

    records = [dict(zip(fields, r)) for r in rows]
    check("alle mit Förderungsart", all(r["funding_type"] for r in records))
    check("alle mit Wohnungsart", all(r["apartment_category"] for r in records))
    check("keine 'Sonstige'-Wohnungsart", not [
        r["unit_number"] for r in records if r["apartment_category"] == "Sonstige"
    ])

    fundings = {r["funding_type"] for r in records}
    check("nur bekannte Förderungsarten",
          fundings <= {"freifinanziert", "WBS A", "WBS B"}, str(fundings))

    standard = [r for r in records if r["apartment_category"] == "Standard Wohnungstypen"]
    check("Standardwohnungen haben Zimmerzahl", all(r["size_rooms"] for r in standard))
    check("Sondertypen ohne Zimmerzahl", all(
        r["size_rooms"] is None for r in records
        if r["apartment_category"] != "Standard Wohnungstypen"
    ))

    p103 = next(r for r in records if r["unit_number"] == "P.103")
    check("P.103: 2,5 Zimmer", p103["size_rooms"] == 2.5)
    check("P.103: freifinanziert (WBS N)", p103["funding_type"] == "freifinanziert")
    check("P.103: WBS-Rohwert erhalten", p103["wbs_raw"] == "N")
    check("P.103: 56,56 qm mietwirksam", p103["area_rent"] == 56.56)

    wpg = next(r for r in records if r["unit_number"] == "W.008.1")
    check("W.008.1: WPG-A wird WBS A", wpg["funding_type"] == "WBS A")
    check("W.008.1: Rohwert WPG-A erhalten", wpg["wbs_raw"] == "WPG-A")
    check("W.008.1: Wohngemeinschaft", wpg["apartment_category"] == "Wohngemeinschaft")

    joker = next(r for r in records if r["unit_number"] == "W.107")
    check("W.107: Joker -> freifinanziert", joker["funding_type"] == "freifinanziert")
    check("W.107: Wohnungsart Joker", joker["apartment_category"] == "Joker")


def test_seed_is_idempotent():
    print("\n== Seed ==")
    db = make_session()
    created = services.seed_apartments(db)
    check("136 Wohnungen angelegt", created == 136, f"({created})")
    check("136 in der Datenbank", db.query(models.Apartment).count() == 136)

    apt = by_unit(db, "P.108.1")
    check("P.108.1 Etage", apt.floor == "1.OG")
    check("P.108.1 Clusterwohnung", apt.apartment_category == "Clusterwohnung")
    check("P.108.1 mind. 2 Bewohner", apt.min_occupants == 2)
    check("P.108.1 ohne Haushalt", apt.household_id is None)

    # Zweiter Aufruf legt nichts an und überschreibt nichts
    apt.area_rent = 99.0
    db.commit()
    again = services.seed_apartments(db)
    check("zweiter Seed legt nichts an", again == 0, f"({again})")
    check("Bearbeitung bleibt erhalten", by_unit(db, "P.108.1").area_rent == 99.0)
    check("weiterhin 136 Wohnungen", db.query(models.Apartment).count() == 136)
    db.close()


def test_household_assignment():
    print("\n== Zuordnung Wohnung -> Haushalt ==")
    db = make_session()
    services.seed_apartments(db)

    hh = models.Household(name="Matt")
    db.add(hh)
    db.commit()

    apt = by_unit(db, "W.002")
    check("Zuordnung gesetzt", services.assign_household(db, apt, hh.id) is True)
    db.commit()

    check("Wohnung zeigt auf Haushalt", apt.household_id == hh.id)
    check("Haushalt kennt Wohnung", hh.apartment.unit_number == "W.002")
    check("Haushalt ist Bewohner", hh.is_resident is True)
    check("Wohnungsnummer am Haushalt gesetzt", hh.apartment_unit == "W.002")
    check("erneute Zuordnung ist No-Op", services.assign_household(db, apt, hh.id) is False)
    db.close()


def test_one_apartment_per_household():
    print("\n== Ein Haushalt wohnt in genau einer Wohnung ==")
    db = make_session()
    services.seed_apartments(db)
    hh = models.Household(name="Umzug")
    db.add(hh)
    db.commit()

    old = by_unit(db, "P.101")
    new = by_unit(db, "P.103")
    services.assign_household(db, old, hh.id)
    db.commit()
    check("Erstzuordnung P.101", old.household_id == hh.id)

    services.assign_household(db, new, hh.id)
    db.commit()
    check("neue Wohnung zugeordnet", new.household_id == hh.id)
    check("alte Zuordnung gelöst", old.household_id is None)

    check("Zuordnung lösbar", services.assign_household(db, new, None) is True)
    db.commit()
    check("Wohnung ohne Haushalt", new.household_id is None)
    check("Wohnung bleibt bestehen", by_unit(db, "P.103") is not None)
    check("Lösen ohne Zuordnung ist No-Op", services.assign_household(db, new, None) is False)

    try:
        services.assign_household(db, new, 9999)
        check("unbekannter Haushalt meldet Fehler", False, "(keine Exception)")
    except ValueError:
        check("unbekannter Haushalt meldet Fehler", True)
    db.close()


def test_example_data_links_residents():
    print("\n== Beispieldaten ==")
    db = make_session()
    services.seed_apartments(db)
    services.seed_example_data(db)

    residents = db.query(models.Household).filter(models.Household.is_resident == True).all()  # noqa: E712
    check("5 Bewohner-Haushalte", len(residents) == 5, f"({len(residents)})")
    check("jeder Bewohner hat eine Wohnung", all(h.apartment is not None for h in residents),
          str([h.name for h in residents if h.apartment is None]))
    check("Wohnungsnummer stimmt überein",
          all(h.apartment.unit_number == h.apartment_unit for h in residents))

    applicants = db.query(models.Household).filter(models.Household.is_resident == False).all()  # noqa: E712
    check("Bewerber ohne Wohnung", all(h.apartment is None for h in applicants))
    check("Bewerbungen angelegt", db.query(models.Application).count() == 10,
          f"({db.query(models.Application).count()})")
    check("Bewerbungen zeigen auf echte Wohnungen", all(
        a.apartment is not None for a in db.query(models.Application).all()
    ))
    check("keine Wohnung doppelt belegt", len({
        a.household_id for a in db.query(models.Apartment).filter(
            models.Apartment.household_id.isnot(None)).all()
    }) == 5)
    db.close()


if __name__ == "__main__":
    test_seed_data()
    test_seed_is_idempotent()
    test_household_assignment()
    test_one_apartment_per_household()
    test_example_data_links_residents()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

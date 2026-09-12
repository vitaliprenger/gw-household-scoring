# -*- coding: utf-8 -*-
"""Tests für Bewerbungen: Wunsch-Parser, Statusregeln und Auswahlkategorien.

Aufruf aus dem Projekt-Root:  python tests/test_applications.py

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

from backend import models, services, wishes

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


def w(size=None, funding=None, category=None):
    return {"size_rooms": size, "funding_type": funding, "apartment_category": category}


# ---------------------------------------------------------------------------

def test_parse_wish():
    print("\n== Wunsch-Parser ==")
    cases = [
        ("2,5 A", [w(2, "WBS A")]),
        ("1,5 B", [w(1, "WBS B")]),
        ("3,5 frei", [w(3, "freifinanziert")]),
        ("1,5 WBS B", [w(1, "WBS B")]),
        ("5,5 A", [w(5, "WBS A")]),
        # Ohne Zimmerzahl bleibt die Größe offen ("egal")
        ("B", [w(None, "WBS B")]),
        ("Cluster", [w(None, None, "Clusterwohnung")]),
        ("Gartencluster", [w(None, None, "Clusterwohnung")]),
        ("Cluster B", [w(None, "WBS B", "Clusterwohnung")]),
        ("Joker", [w(None, None, "Joker")]),
        # Der Haushaltsbogen schreibt die Größe anders
        ("4 Zimmer", [w(4)]),
        # Mehrere Wünsche in einer Zelle
        ("5,5 A\n4,5 A", [w(5, "WBS A"), w(4, "WBS A")]),
        ("3,5 A/B", [w(3, "WBS A"), w(3, "WBS B")]),
        # Ausbau und Atelier zählen als Standardwohnung -- auch abgekürzt,
        # wie die gepflegte Liste sie schreibt
        ("1,5 B Ausbau / Atelier", [w(1, "WBS B")]),
        ("1,5 A\n1,5 B\nAusb / Atelier\nCluster",
         [w(1, "WBS A"), w(1, "WBS B"), w(None, None, "Clusterwohnung")]),
        ("1,5 att", [w(1)]),
        # "klein" ist eine Bauvariante derselben Kategorie
        ("3,5 kl WBS B", [w(3, "WBS B")]),
        ("3,5k A", [w(3, "WBS A")]),
        # Wohnungsnummern sind Hinweise, kein Wunsch
        ("2,5 A - W.006", [w(2, "WBS A")]),
        ("", []),
        (None, []),
    ]
    for raw, expected in cases:
        parsed, unparsed = wishes.parse_wish(raw)
        check_equal(f"{raw!r}", parsed, expected)
        check(f"{raw!r}: nichts offen", not unparsed, str(unparsed))

    parsed, unparsed = wishes.parse_wish("2,5 A, ter")
    check_equal("erkannter Teil bleibt erhalten", parsed, [w(2, "WBS A")])
    check_equal("unauflösbarer Teil wird gemeldet", unparsed, ["ter"])

    # Eine Wohnungsnummer als ganzer Wunsch ist ein Wunsch, den das Modell nicht
    # kennt -- er darf nicht stillschweigend verschwinden.
    parsed, unparsed = wishes.parse_wish("W.213")
    check_equal("Wohnungsnummer als Wunsch: kein Wunsch", parsed, [])
    check_equal("Wohnungsnummer als Wunsch: gemeldet", unparsed, ["W.213"])


def test_wish_label():
    print("\n== Anzeige der Wünsche ==")
    # Das halbe Zimmer entfällt im Modell, die Anzeige nutzt die Schreibweise der Liste.
    check_equal("2 Zimmer -> 2,5 A", wishes.wish_label(w(2, "WBS A")), "2,5 A")
    check_equal("freifinanziert kurz", wishes.wish_label(w(3, "freifinanziert")), "3,5 frei")
    check_equal("Cluster ohne Größe", wishes.wish_label(w(None, None, "Clusterwohnung")), "Cluster")
    check_equal("Joker", wishes.wish_label(w(None, None, "Joker")), "Joker")
    check_equal("ohne jede Angabe", wishes.wish_label(w()), "beliebig")


def test_wish_matches():
    print("\n== Abgleich Wunsch <-> Kategorie ==")
    check("genaue Kategorie passt",
          wishes.wish_matches(w(2, "WBS A"), 2, "WBS A", "Standard Wohnungstypen"))
    check("andere Zimmerzahl passt nicht",
          not wishes.wish_matches(w(2, "WBS A"), 3, "WBS A", "Standard Wohnungstypen"))
    check("andere Förderungsart passt nicht",
          not wishes.wish_matches(w(2, "WBS A"), 2, "WBS B", "Standard Wohnungstypen"))
    check("offene Zimmerzahl heißt egal",
          wishes.wish_matches(w(None, "WBS B"), 4, "WBS B", None))
    check("offene Förderungsart heißt egal",
          wishes.wish_matches(w(2), 2, "freifinanziert", None))
    check("Ausbauwohnung zählt als Standard",
          wishes.wish_matches(w(2, "WBS A"), 2, "WBS A", "Ausbauwohnung"))
    check("Cluster muss ausdrücklich gewünscht sein",
          not wishes.wish_matches(w(2, "WBS A"), 2, "WBS A", "Clusterwohnung"))
    check("Cluster-Wunsch trifft Cluster",
          wishes.wish_matches(w(None, None, "Clusterwohnung"), 2, "WBS A", "Clusterwohnung"))
    check("Cluster-Wunsch trifft keine Standardwohnung",
          not wishes.wish_matches(w(None, None, "Clusterwohnung"), 2, "WBS A", None))


def test_normalize_wishes():
    print("\n== Kanonische Form ==")
    check_equal("Dubletten entfernt",
                wishes.normalize_wishes([w(2, "WBS A"), w(2, "WBS A")]), [w(2, "WBS A")])
    check_equal("Standard wird nicht gespeichert",
                wishes.normalize_wishes([w(2, "WBS A", "Standard Wohnungstypen")]),
                [w(2, "WBS A")])
    check_equal("leere Werte werden zu None",
                wishes.normalize_wishes([{"size_rooms": 2, "funding_type": "", "apartment_category": ""}]),
                [w(2)])
    check_equal("None bleibt leer", wishes.normalize_wishes(None), [])


def test_from_household_fields():
    print("\n== Übernahme aus den alten Haushaltsfeldern ==")
    check_equal("Größe und Standard-Wohnungsart",
                wishes.from_household_fields("3,5", '["Standard Wohnungstypen"]'),
                [w(3)])
    check_equal("Clusterwohnung bleibt erhalten",
                wishes.from_household_fields("2,5", ["Clusterwohnung"]),
                [w(2, None, "Clusterwohnung")])
    check_equal("Wohnungsart ohne Größe",
                wishes.from_household_fields(None, ["Clusterwohnung"]),
                [w(None, None, "Clusterwohnung")])
    check_equal("ohne Angaben kein Wunsch", wishes.from_household_fields(None, None), [])


def test_one_open_application_per_kind():
    print("\n== Offene Bewerbungen ==")
    db = make_session()
    hh = models.Household(name="Test")
    db.add(hh)
    db.flush()
    db.add(models.Application(household_id=hh.id, kind="wartepool", status="offen"))
    db.add(models.Application(household_id=hh.id, kind="wechselwunsch", status="offen"))
    db.add(models.Application(household_id=hh.id, kind="wartepool", status="zurueckgezogen"))
    db.commit()

    check_equal("zwei offene Bewerbungen", len(services.open_applications(db, hh.id)), 2)
    check_equal("je Art genau eine offene",
                len(services.open_applications(db, hh.id, kind="wartepool")), 1)
    check_equal("zurückgezogene zählt nicht",
                len(services.open_applications(db, hh.id, kind="zurueckgezogen")), 0)
    db.close()


def test_close_on_move_in():
    print("\n== Einzug schließt Bewerbungen ==")
    db = make_session()
    hh = models.Household(name="Test")
    apt = models.Apartment(unit_number="W.001", size_rooms=2, funding_type="freifinanziert")
    db.add_all([hh, apt])
    db.flush()
    pool = models.Application(household_id=hh.id, kind="wartepool", status="offen")
    done = models.Application(household_id=hh.id, kind="wechselwunsch",
                              status="zurueckgezogen")
    db.add_all([pool, done])
    db.commit()

    services.assign_household(db, apt, hh.id)
    db.commit()

    check_equal("offene Bewerbung erfüllt", pool.status, "erfuellt")
    check_equal("Wohnung vermerkt", pool.fulfilled_apartment_id, apt.id)
    check("Zeitpunkt gesetzt", pool.fulfilled_at is not None)
    check_equal("zurückgezogene bleibt unberührt", done.status, "zurueckgezogen")
    check("zurückgezogene bekommt keine Wohnung", done.fulfilled_apartment_id is None)
    db.close()


def test_category_options():
    print("\n== Auswahlliste der Wunschkategorien ==")
    db = make_session()
    db.add_all([
        models.Apartment(unit_number="A.1", size_rooms=2, funding_type="WBS A",
                         apartment_category="Standard Wohnungstypen"),
        models.Apartment(unit_number="A.2", size_rooms=2, funding_type="WBS A",
                         apartment_category="Ausbauwohnung"),
        models.Apartment(unit_number="A.3", size_rooms=3, funding_type="freifinanziert",
                         apartment_category="Atelierwohnung"),
        models.Apartment(unit_number="C.1", size_rooms=2, funding_type="WBS A",
                         apartment_category="Clusterwohnung"),
        models.Apartment(unit_number="C.2", size_rooms=1, funding_type="WBS B",
                         apartment_category="Clusterwohnung"),
        models.Apartment(unit_number="J.1", size_rooms=None, funding_type="freifinanziert",
                         apartment_category="Joker"),
    ])
    db.commit()

    options = services.apartment_category_options(db)
    labels = [o["label"] for o in options]
    check("Ausbau- und Atelierwohnung laufen als Standard",
          labels[:2] == ["2,5 A", "3,5 frei"], str(labels))
    check_equal("Standardkategorie zählt beide Wohnungen",
                options[0]["apartment_count"], 2)
    check("Clusterwohnungen erscheinen mit Wohnungsart",
          "Cluster" in labels and "1,5 Cluster B" in labels, str(labels))
    check("Sammel-Wunsch 'Cluster' ohne Zimmerzahl vorhanden",
          any(o["apartment_category"] == "Clusterwohnung" and o["size_rooms"] is None
              for o in options))
    check("Joker nur einmal (nur eine Ausprägung)",
          sum(1 for o in options if o["apartment_category"] == "Joker") == 1, str(labels))
    db.close()


if __name__ == "__main__":
    test_parse_wish()
    test_wish_label()
    test_wish_matches()
    test_normalize_wishes()
    test_from_household_fields()
    test_one_open_application_per_kind()
    test_close_on_move_in()
    test_category_options()

    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} Test(s) fehlgeschlagen:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle Tests bestanden.")

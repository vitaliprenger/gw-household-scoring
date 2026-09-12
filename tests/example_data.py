# -*- coding: utf-8 -*-
"""Beispieldaten für die Tests.

Diese Daten wurden früher beim Start der Anwendung in eine leere Datenbank
geschrieben. Die Anwendung startet jetzt mit einer leeren Datenbank; die
Beispieldaten leben nur noch hier und werden ausschließlich von den Tests
benutzt.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from backend import models
from backend.services import seed_apartments, assign_household
from backend.wishes import parse_wish


def _d(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d)


def seed_example_data(db: Session):
    if db.query(models.Household).first() is not None:
        return

    # Beispieldaten aus realen Import-Daten (imported_data/)

    # -- Bewohner (Ist-Belegung) ------------------------------------------
    residents = [
        {
            "name": "Manuela Liebold",
            "engagement_score": 0.8,
            "is_resident": True,
            "apartment_unit": "W.209",
            "people": [
                ("Manuela", "Liebold", _d(1975, 4, 12), "f", "2", "6", None, None, "1", _d(2017, 1, 1)),
                ("Thorsten", "Liebold", _d(1972, 9, 8), "m", "4", "3", None, None, "2", _d(2017, 1, 1)),
            ],
        },
        {
            "name": "Gudrun Gehrke",
            "engagement_score": 0.6,
            "is_resident": True,
            "apartment_unit": "W.210",
            "people": [
                ("Gudrun", "Gehrke", _d(1962, 3, 22), "f", "1", "7", None, None, "14", _d(2017, 6, 1)),
                ("Mathias", "Uhl", _d(1960, 11, 15), "m", "9", "8", None, None, "13", _d(2017, 6, 1)),
            ],
        },
        {
            "name": "Elke Stücke",
            "engagement_score": 0.9,
            "is_resident": True,
            "apartment_unit": "R.103",
            "people": [
                ("Elke", "Stücke", _d(1958, 1, 25), "f", "5", "4", None, None, "30", _d(2015, 1, 1)),
            ],
        },
        {
            "name": "Sebastian Danek",
            "engagement_score": 0.5,
            "is_resident": True,
            "apartment_unit": "W.213",
            "people": [
                ("Sebastian", "Danek", _d(1988, 7, 3), "m", "9", "7", None, None, "65", _d(2018, 1, 1)),
                ("Tanja", "Danek", _d(1990, 2, 14), "f", "2", "6", None, None, "66", _d(2018, 1, 1)),
                ("Ewa", "Danek", _d(2019, 3, 28), "f", "0", "0", None, None, None, None),
            ],
        },
        {
            "name": "Christa Köller",
            "engagement_score": 0.3,
            "is_resident": True,
            "apartment_unit": "W.104",
            "people": [
                ("Christa", "Köller", _d(1950, 8, 30), "f", "6", "4", None, None, "34", _d(2016, 6, 1)),
            ],
        },
    ]

    # -- Bewerber ----------------------------------------------------------
    applicants = [
        {
            "name": "Simon Kruse",
            "engagement_score": 0.2,
            "is_resident": False,
            "wbs_status": "WBS A",
            "wish": "1,5 A",
            "people": [
                ("Simon", "Kruse", _d(1988, 11, 29), "m", "1", "7", None,
                 "Behinderung (GdB 40 mit Gleichstellung)", "637", _d(2024, 5, 1)),
            ],
        },
        {
            "name": "Anja Venjakob",
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "wish": "3,5 frei",
            "people": [
                ("Anja", "Venjakob", _d(1977, 6, 23), "f", "2", "7", None, None, "628", _d(2023, 1, 1)),
                ("Jörg", "Höbing", _d(1974, 6, 17), "m", "2", "7", None, None, "627", _d(2023, 1, 1)),
            ],
        },
        {
            "name": "Reinhilde Tenk",
            "engagement_score": 0.7,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "people": [
                ("Reinhilde", "Tenk", _d(1954, 11, 10), "f", "5", "6", None, "Osteoporose", "26", _d(2017, 6, 1)),
            ],
        },
        {
            "name": "Thomas Tenk",
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "people": [
                ("Thomas", "Tenk", _d(1958, 8, 17), "m", "4", "4", None, None, "27", _d(2017, 6, 1)),
            ],
        },
        {
            "name": "Kerstin Nolte",
            "engagement_score": 0.4,
            "is_resident": False,
            "wbs_status": "WBS A",
            "financial_status": "kann Anteile nicht übernehmen",
            "people": [
                ("Kerstin", "Nolte", _d(1986, 5, 20), "f", "2", "6", None, None, "135", _d(2019, 6, 1)),
                ("Emmi", "Nolte", _d(2018, 1, 8), "f", "0", "0", None, None, None, None),
                ("Clara", "Nolte", _d(2018, 1, 8), "f", "0", "0", None, None, None, None),
            ],
        },
        {
            "name": "Sandra Rocha",
            "engagement_score": 0.6,
            "is_resident": False,
            "wbs_status": "WBS A",
            "wish": "3,5 A",
            "pets_count": 1,
            "pets_info": "Hund",
            "people": [
                ("Sandra A.", "Rocha", _d(1980, 12, 15), "f", "2", "6",
                 "lateinamerikanisch", None, "12", _d(2017, 1, 1)),
                ("Silas K. M.", "Rocha Hegmanns", _d(2004, 9, 22), "m", "0", "4",
                 None, None, None, None),
            ],
        },
    ]

    # Haushalte + Personen anlegen
    all_households: list[models.Household] = []
    for hh_data in residents + applicants:
        hh = models.Household(
            name=hh_data["name"],
            engagement_score=hh_data["engagement_score"],
            is_resident=hh_data["is_resident"],
            wbs_status=hh_data.get("wbs_status"),
            financial_status=hh_data.get("financial_status"),
            pets_count=hh_data.get("pets_count", 0),
            pets_info=hh_data.get("pets_info"),
            apartment_unit=hh_data.get("apartment_unit"),
        )
        db.add(hh)
        db.flush()
        for first, last, birth, gender, occ, edu, culture, special, member_nr, member_since in hh_data["people"]:
            db.add(models.Person(
                household_id=hh.id,
                first_name=first,
                last_name=last,
                birth_date=birth,
                gender=gender,
                occupation_type=occ,
                education_level=edu,
                cultural_background=culture,
                special_needs=special,
                member_number=member_nr,
                member_since=member_since,
            ))
        all_households.append(hh)

    # Wohnungsstammdaten sicherstellen und Bewohner ihren Wohnungen zuordnen
    seed_apartments(db)
    for hh in all_households:
        if not hh.apartment_unit:
            continue
        apt = (
            db.query(models.Apartment)
            .filter(models.Apartment.unit_number == hh.apartment_unit)
            .first()
        )
        if apt is not None:
            assign_household(db, apt, hh.id)

    # -- Bewerbungen -------------------------------------------------------
    # Ohne offene Bewerbung steht ein Haushalt in keiner Rangliste. Jeder
    # Bewerber erhält deshalb eine Wartepool-Bewerbung; der Wunsch wird aus der
    # Schreibweise der gepflegten Liste geparst ("3,5 A").
    by_name = {hh.name: hh for hh in all_households}
    for hh_data in applicants:
        wish_list, _ = parse_wish(hh_data.get("wish"))
        db.add(models.Application(
            household_id=by_name[hh_data["name"]].id,
            kind="wartepool",
            status="offen",
            requested_at=hh_data.get("requested_at", _d(2024, 1, 15)),
            wishes=wish_list,
            created_at=_d(2024, 1, 15),
        ))

    # Zwei Bewohner-Haushalte wollen wechseln, einer möchte ein Joker-Zimmer.
    # Hier entscheidet nicht das Scoring, sondern das Datum des Wunsches.
    resident_applications = [
        ("Elke Stücke",      "wechselwunsch", "2,5 A",  _d(2023, 5, 4),  "Wohnung zu groß"),
        ("Christa Köller",   "wechselwunsch", "2,5 A",  _d(2024, 9, 17), None),
        ("Sebastian Danek",  "joker",         "Joker",  _d(2024, 3, 1),  None),
    ]
    for name, kind, wish, requested, note in resident_applications:
        wish_list, _ = parse_wish(wish)
        db.add(models.Application(
            household_id=by_name[name].id,
            kind=kind,
            status="offen",
            requested_at=requested,
            wishes=wish_list,
            note=note,
            created_at=requested,
        ))

    db.commit()

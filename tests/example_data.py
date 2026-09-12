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

    # Frei erfundene Beispieldaten; sie gehören zu keiner realen Person

    # -- Bewohner (Ist-Belegung) ------------------------------------------
    residents = [
        {
            "name": "Birgit Ahrendt",
            "engagement_score": 0.8,
            "is_resident": True,
            "apartment_unit": "W.110",
            "people": [
                ("Birgit", "Ahrendt", _d(1975, 7, 19), "f", "2", "6", None, None, "3", _d(2017, 3, 1)),
                ("Holger", "Ahrendt", _d(1972, 2, 26), "m", "4", "3", None, None, "4", _d(2017, 3, 1)),
            ],
        },
        {
            "name": "Renate Falkner",
            "engagement_score": 0.6,
            "is_resident": True,
            "apartment_unit": "W.111",
            "people": [
                ("Renate", "Falkner", _d(1962, 8, 5), "f", "1", "7", None, None, "19", _d(2017, 9, 1)),
                ("Dieter", "Brandhorst", _d(1960, 4, 27), "m", "9", "8", None, None, "18", _d(2017, 9, 1)),
            ],
        },
        {
            "name": "Ingrid Sommerfeld",
            "engagement_score": 0.9,
            "is_resident": True,
            "apartment_unit": "R.116",
            "people": [
                ("Ingrid", "Sommerfeld", _d(1958, 6, 9), "f", "5", "4", None, None, "37", _d(2015, 4, 1)),
            ],
        },
        {
            "name": "Lukas Wiegand",
            "engagement_score": 0.5,
            "is_resident": True,
            "apartment_unit": "W.113",
            "people": [
                ("Lukas", "Wiegand", _d(1988, 3, 21), "m", "9", "7", None, None, "81", _d(2018, 5, 1)),
                ("Miriam", "Wiegand", _d(1990, 9, 2), "f", "2", "6", None, None, "82", _d(2018, 5, 1)),
                ("Lotta", "Wiegand", _d(2019, 6, 11), "f", "0", "0", None, None, None, None),
            ],
        },
        {
            "name": "Hannelore Petzold",
            "engagement_score": 0.3,
            "is_resident": True,
            "apartment_unit": "W.203",
            "people": [
                ("Hannelore", "Petzold", _d(1950, 5, 14), "f", "6", "4", None, None, "45", _d(2016, 10, 1)),
            ],
        },
    ]

    # -- Bewerber ----------------------------------------------------------
    applicants = [
        {
            "name": "Florian Reuter",
            "engagement_score": 0.2,
            "is_resident": False,
            "wbs_status": "WBS A",
            "wish": "1,5 A",
            "people": [
                ("Florian", "Reuter", _d(1988, 4, 6), "m", "1", "7", None,
                 "Gehbehinderung", "954", _d(2024, 8, 1)),
            ],
        },
        {
            "name": "Katrin Lindemann",
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "wish": "3,5 frei",
            "people": [
                ("Katrin", "Lindemann", _d(1977, 10, 3), "f", "2", "7", None, None, "941", _d(2023, 4, 1)),
                ("Stefan", "Oswald", _d(1974, 1, 28), "m", "2", "7", None, None, "940", _d(2023, 4, 1)),
            ],
        },
        {
            "name": "Marianne Voss",
            "engagement_score": 0.7,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "people": [
                ("Marianne", "Voss", _d(1954, 3, 16), "f", "5", "6", None, "chronische Erkrankung", "51", _d(2017, 9, 1)),
            ],
        },
        {
            "name": "Günter Voss",
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "people": [
                ("Günter", "Voss", _d(1958, 12, 4), "m", "4", "4", None, None, "52", _d(2017, 9, 1)),
            ],
        },
        {
            "name": "Julia Hartwig",
            "engagement_score": 0.4,
            "is_resident": False,
            "wbs_status": "WBS A",
            "financial_status": "kann Anteile nicht übernehmen",
            "people": [
                ("Julia", "Hartwig", _d(1986, 9, 12), "f", "2", "6", None, None, "168", _d(2019, 11, 1)),
                ("Mia", "Hartwig", _d(2018, 2, 19), "f", "0", "0", None, None, None, None),
                ("Lena", "Hartwig", _d(2018, 2, 19), "f", "0", "0", None, None, None, None),
            ],
        },
        {
            "name": "Carla Ferreira",
            "engagement_score": 0.6,
            "is_resident": False,
            "wbs_status": "WBS A",
            "wish": "3,5 A",
            "pets_count": 1,
            "pets_info": "Katze",
            "people": [
                ("Carla M.", "Ferreira", _d(1980, 7, 24), "f", "2", "6",
                 "südeuropäisch", None, "23", _d(2017, 3, 1)),
                ("Noah J. T.", "Ferreira Brandt", _d(2004, 5, 30), "m", "0", "4",
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
        ("Ingrid Sommerfeld",      "wechselwunsch", "2,5 A",  _d(2023, 4, 12),  "möchte sich verkleinern"),
        ("Hannelore Petzold",   "wechselwunsch", "2,5 A",  _d(2024, 10, 2), None),
        ("Lukas Wiegand",  "joker",         "Joker",  _d(2024, 2, 19),  None),
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

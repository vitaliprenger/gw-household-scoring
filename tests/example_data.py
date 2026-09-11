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
            "desired_apartment_size": "1,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            # "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Marianne", "Voss", _d(1954, 3, 16), "f", "5", "6", None, "chronische Erkrankung", "51", _d(2017, 9, 1)),
            ],
        },
        {
            "name": "Günter Voss",
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            # "desired_apartment_size": "2,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            desired_apartment_size=hh_data.get("desired_apartment_size"),
            desired_apartment_type=hh_data.get("desired_apartment_type"),
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

    # Beispiel-Bewerbungen auf echte Wohnungen (siehe seed_apartments)
    applicant_hhs = [h for h in all_households if not h.is_resident]
    example_applications = [
        (0, ["P.104", "P.204"]),          # Reuter (1 Pers.)   → 1,5 Zimmer
        (1, ["P.106", "P.206"]),          # Lindemann/Oswald   → 3,5 Zimmer
        (2, ["P.106", "P.206"]),          # M. Voss           → 3,5 Zimmer
        (3, ["P.211", "W.212"]),          # Hartwig (3 Pers.)   → 4,5 / 5,5 Zimmer
        (4, ["P.208", "P.106"]),          # Ferreira (2 Pers.)   → 3,5 Zimmer
    ]
    apartments_by_unit = {
        apt.unit_number: apt
        for apt in db.query(models.Apartment).all()
    }
    for hh_idx, units in example_applications:
        for unit in units:
            apt = apartments_by_unit.get(unit)
            if apt is None:
                continue
            db.add(models.Application(
                household_id=applicant_hhs[hh_idx].id,
                apartment_id=apt.id,
            ))

    db.commit()

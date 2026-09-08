import pandas as pd
from sqlalchemy.orm import Session
from . import models
from datetime import datetime, date
import io

def process_excel_upload(file_contents: bytes, db: Session):
    # Read Excel file
    # Assuming a flat structure where each row is a person, grouped by "Household Name"
    df = pd.read_excel(io.BytesIO(file_contents))
    
    # Expected columns:
    # Household Name, Member Since, Engagement Score, 
    # First Name, Last Name, Birth Date, Gender, Occupation, Education, Cultural Background, Special Needs
    
    # Group by Household Name to create households first
    grouped = df.groupby("Household Name")
    
    created_count = 0
    
    for household_name, group in grouped:
        # Take household data from the first row of the group
        first_row = group.iloc[0]
        
        # Parse dates and scores
        member_since = pd.to_datetime(first_row.get("Member Since"), errors='coerce')
        if pd.isna(member_since):
            member_since = None

        engagement_score = float(first_row.get("Engagement Score", 0.0))

        db_household = models.Household(
            name=str(household_name),
            engagement_score=engagement_score
        )
        db.add(db_household)
        db.flush()

        for index, row in group.iterrows():
            birth_date = pd.to_datetime(row.get("Birth Date"), errors='coerce')
            row_member_since = pd.to_datetime(row.get("Member Since"), errors='coerce')
            if pd.isna(row_member_since):
                row_member_since = member_since

            db_person = models.Person(
                household_id=db_household.id,
                first_name=str(row.get("First Name", "")),
                last_name=str(row.get("Last Name", "")),
                birth_date=birth_date,
                gender=str(row.get("Gender", "")),
                occupation_type=str(row.get("Occupation", "")),
                education_level=str(row.get("Education", "")),
                cultural_background=str(row.get("Cultural Background", "")),
                special_needs=str(row.get("Special Needs", "")).strip() or None,
                member_since=row_member_since,
            )
            db.add(db_person)
        
        created_count += 1
        
    db.commit()
    return {"message": f"Erfolgreich {created_count} Haushalte und {len(df)} Personen importiert."}


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
            "people": [
                ("Birgit", "Ahrendt", _d(1975, 7, 19), "f", "2", "6", None, None, "3", _d(2017, 3, 1)),
                ("Holger", "Ahrendt", _d(1972, 2, 26), "m", "4", "3", None, None, "4", _d(2017, 3, 1)),
            ],
        },
        {
            "name": "Renate Falkner",
            "engagement_score": 0.6,
            "is_resident": True,
            "people": [
                ("Renate", "Falkner", _d(1962, 8, 5), "f", "1", "7", None, None, "19", _d(2017, 9, 1)),
                ("Dieter", "Brandhorst", _d(1960, 4, 27), "m", "9", "8", None, None, "18", _d(2017, 9, 1)),
            ],
        },
        {
            "name": "Ingrid Sommerfeld",
            "engagement_score": 0.9,
            "is_resident": True,
            "people": [
                ("Ingrid", "Sommerfeld", _d(1958, 6, 9), "f", "5", "4", None, None, "37", _d(2015, 4, 1)),
            ],
        },
        {
            "name": "Lukas Wiegand",
            "engagement_score": 0.5,
            "is_resident": True,
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
            "wbs_status": "WBS Einkommensgruppe A",
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
            "desired_apartment_size": "3,5",
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
            "desired_apartment_size": "2,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Günter", "Voss", _d(1958, 12, 4), "m", "4", "4", None, None, "52", _d(2017, 9, 1)),
            ],
        },
        {
            "name": "Julia Hartwig",
            "engagement_score": 0.4,
            "is_resident": False,
            "wbs_status": "WBS Einkommensgruppe A",
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
            "wbs_status": "WBS Einkommensgruppe A",
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

    # -- Wohnungen ---------------------------------------------------------
    apartments_data = [
        ("W-101", 1.5, "freifinanziert"),
        ("W-102", 1.5, "WBS A"),
        ("W-201", 2.5, "freifinanziert"),
        ("W-202", 2.5, "WBS A"),
        ("W-203", 2.5, "WBS B"),
        ("W-301", 3.5, "freifinanziert"),
        ("W-302", 3.5, "WBS A"),
        ("W-401", 4.5, "WBS B"),
        ("W-501", 5.5, "freifinanziert"),
        ("W-502", 5.5, "WBS A"),
        ("W-503", 5.5, "WBS B"),
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

    # Wohnungen anlegen
    db_apartments: list[models.Apartment] = []
    for unit, size, funding in apartments_data:
        apt = models.Apartment(unit_number=unit, size_rooms=size, funding_type=funding)
        db.add(apt)
        db_apartments.append(apt)
    db.flush()

    # Bewerbungen: Bewerber auf passende Wohnungen
    applicant_hhs = [h for h in all_households if not h.is_resident]
    assignment = [
        (0, [0, 1]),    # Reuter (1 Pers.) → 1.5er
        (1, [5, 6]),    # Lindemann/Oswald (2 Pers.) → 3.5er
        (2, [5, 6]),    # Voss (2 Pers.) → 3.5er
        (3, [7, 8]),    # Hartwig (3 Pers.) → 4.5 + 5.5
        (4, [5, 6]),    # Ferreira (2 Pers.) → 3.5er
    ]
    for hh_idx, apt_indices in assignment:
        for apt_idx in apt_indices:
            db.add(models.Application(
                household_id=applicant_hhs[hh_idx].id,
                apartment_id=db_apartments[apt_idx].id,
            ))

    db.commit()

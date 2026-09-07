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
        
        # Check if household exists or create new
        # For simplicity in this iteration, we create new ones. 
        # In production, we might want to update existing ones.
        db_household = models.Household(
            name=str(household_name),
            member_since=member_since,
            engagement_score=engagement_score
        )
        db.add(db_household)
        db.flush() # Flush to get the ID
        
        # Create people for this household
        for index, row in group.iterrows():
            birth_date = pd.to_datetime(row.get("Birth Date"), errors='coerce')
            
            db_person = models.Person(
                household_id=db_household.id,
                first_name=str(row.get("First Name", "")),
                last_name=str(row.get("Last Name", "")),
                birth_date=birth_date,
                gender=str(row.get("Gender", "")),
                occupation_type=str(row.get("Occupation", "")),
                education_level=str(row.get("Education", "")),
                cultural_background=str(row.get("Cultural Background", "")),
                special_needs=str(row.get("Special Needs", "")).strip() or None
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

    # -- Bewohner (Ist-Belegung) ------------------------------------------
    residents = [
        {
            "name": "Familie Müller",
            "member_since": _d(2018, 3, 1),
            "engagement_score": 0.7,
            "is_resident": True,
            "people": [
                ("Thomas", "Müller", _d(1982, 5, 14), "m", "angestellt", "3", None, None),
                ("Sabine", "Müller", _d(1985, 9, 22), "f", "angestellt", "7", None, None),
                ("Lena", "Müller", _d(2015, 1, 10), "f", "Schüler", "0", None, None),
            ],
        },
        {
            "name": "WG Schmidt & Co",
            "member_since": _d(2020, 7, 15),
            "engagement_score": 0.4,
            "is_resident": True,
            "people": [
                ("Jan", "Schmidt", _d(1995, 11, 3), "m", "Student", "7", None, None),
                ("Ayumi", "Tanaka", _d(1997, 4, 18), "f", "Student", "7", "japanisch", None),
            ],
        },
        {
            "name": "Herr Becker",
            "member_since": _d(2015, 1, 1),
            "engagement_score": 0.9,
            "is_resident": True,
            "people": [
                ("Helmut", "Becker", _d(1958, 8, 30), "m", "Rentner", "3", None, None),
            ],
        },
        {
            "name": "Familie Özdemir",
            "member_since": _d(2019, 6, 1),
            "engagement_score": 0.6,
            "is_resident": True,
            "people": [
                ("Kemal", "Özdemir", _d(1978, 2, 12), "m", "selbstständig", "7", "türkisch", None),
                ("Fatma", "Özdemir", _d(1980, 12, 5), "f", "angestellt", "3", "türkisch", None),
                ("Elif", "Özdemir", _d(2010, 7, 20), "f", "Schüler", "0", "türkisch", None),
                ("Emre", "Özdemir", _d(2013, 3, 8), "m", "Schüler", "0", "türkisch", None),
            ],
        },
        {
            "name": "Frau Lehmann",
            "member_since": _d(2016, 11, 1),
            "engagement_score": 0.3,
            "is_resident": True,
            "people": [
                ("Ingrid", "Lehmann", _d(1955, 6, 17), "f", "Rentner", "7", None, "Pflegebedürftig (Pflegegrad 2)"),
            ],
        },
    ]

    # -- Bewerber ----------------------------------------------------------
    applicants = [
        {
            "name": "Familie Weber",
            "member_since": _d(2021, 4, 1),
            "engagement_score": 0.5,
            "is_resident": False,
            "people": [
                ("Markus", "Weber", _d(1990, 3, 25), "m", "angestellt", "7", None, None),
                ("Lisa", "Weber", _d(1992, 7, 11), "f", "selbstständig", "7", None, None),
                ("Noah", "Weber", _d(2020, 10, 2), "m", "0", "0", None, None),
            ],
        },
        {
            "name": "Herr Nguyen",
            "member_since": _d(2023, 1, 15),
            "engagement_score": 0.8,
            "is_resident": False,
            "people": [
                ("Minh", "Nguyen", _d(1988, 12, 1), "m", "angestellt", "7", "vietnamesisch", None),
            ],
        },
        {
            "name": "Frau Fischer",
            "member_since": _d(2022, 9, 1),
            "engagement_score": 0.2,
            "is_resident": False,
            "people": [
                ("Clara", "Fischer", _d(2000, 5, 30), "f", "Student", "3", None, None),
            ],
        },
        {
            "name": "Familie Al-Rashid",
            "member_since": _d(2020, 2, 1),
            "engagement_score": 0.6,
            "is_resident": False,
            "people": [
                ("Omar", "Al-Rashid", _d(1975, 8, 14), "m", "angestellt", "7", "syrisch", "Geflüchteter, schwierige finanzielle Situation"),
                ("Amira", "Al-Rashid", _d(1979, 1, 22), "f", "angestellt", "3", "syrisch", None),
                ("Layla", "Al-Rashid", _d(2008, 4, 5), "f", "Schüler", "0", "syrisch", None),
                ("Sami", "Al-Rashid", _d(2012, 11, 18), "m", "Schüler", "0", "syrisch", None),
            ],
        },
        {
            "name": "Herr & Frau Klein",
            "member_since": _d(2017, 5, 1),
            "engagement_score": 0.9,
            "is_resident": False,
            "people": [
                ("Werner", "Klein", _d(1960, 3, 7), "m", "Rentner", "3", None, None),
                ("Gisela", "Klein", _d(1962, 10, 19), "f", "Rentner", "0", None, "Schwerbehindert (GdB 60)"),
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
            member_since=hh_data["member_since"],
            engagement_score=hh_data["engagement_score"],
            is_resident=hh_data["is_resident"],
        )
        db.add(hh)
        db.flush()
        for first, last, birth, gender, occ, edu, culture, special in hh_data["people"]:
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
            ))
        all_households.append(hh)

    # Wohnungen anlegen
    db_apartments: list[models.Apartment] = []
    for unit, size, funding in apartments_data:
        apt = models.Apartment(unit_number=unit, size_rooms=size, funding_type=funding)
        db.add(apt)
        db_apartments.append(apt)
    db.flush()

    # Bewerbungen: jeder Bewerber bewirbt sich auf 2 passende Wohnungen
    applicant_hhs = [h for h in all_households if not h.is_resident]
    assignment = [
        (0, [5, 6]),    # Weber (3 Pers.) → 3.5er
        (1, [0, 1]),    # Nguyen (1 Pers.) → 1.5er
        (2, [0, 2]),    # Fischer (1 Pers.) → 1.5 + 2.5
        (3, [7, 8]),    # Al-Rashid (4 Pers.) → 4.5 + 5.5
        (4, [2, 3]),    # Klein (2 Pers.) → 2.5er
    ]
    for hh_idx, apt_indices in assignment:
        for apt_idx in apt_indices:
            db.add(models.Application(
                household_id=applicant_hhs[hh_idx].id,
                apartment_id=db_apartments[apt_idx].id,
            ))

    db.commit()

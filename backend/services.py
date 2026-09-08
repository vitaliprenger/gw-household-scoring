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

    # Beispieldaten aus realen Import-Daten (imported_data/)

    # -- Bewohner (Ist-Belegung) ------------------------------------------
    residents = [
        {
            "name": "Manuela Liebold",
            "member_since": _d(2017, 1, 1),
            "engagement_score": 0.8,
            "is_resident": True,
            "people": [
                ("Manuela", "Liebold", _d(1975, 4, 12), "f", "2", "6", None, None, "1"),
                ("Thorsten", "Liebold", _d(1972, 9, 8), "m", "4", "3", None, None, "2"),
            ],
        },
        {
            "name": "Gudrun Gehrke",
            "member_since": _d(2017, 6, 1),
            "engagement_score": 0.6,
            "is_resident": True,
            "people": [
                ("Gudrun", "Gehrke", _d(1962, 3, 22), "f", "1", "7", None, None, "14"),
                ("Mathias", "Uhl", _d(1960, 11, 15), "m", "9", "8", None, None, "13"),
            ],
        },
        {
            "name": "Elke Stücke",
            "member_since": _d(2015, 1, 1),
            "engagement_score": 0.9,
            "is_resident": True,
            "people": [
                ("Elke", "Stücke", _d(1958, 1, 25), "f", "5", "4", None, None, "30"),
            ],
        },
        {
            "name": "Sebastian Danek",
            "member_since": _d(2018, 1, 1),
            "engagement_score": 0.5,
            "is_resident": True,
            "people": [
                ("Sebastian", "Danek", _d(1988, 7, 3), "m", "9", "7", None, None, "65"),
                ("Tanja", "Danek", _d(1990, 2, 14), "f", "2", "6", None, None, "66"),
                ("Ewa", "Danek", _d(2019, 3, 28), "f", "0", "0", None, None, None),
            ],
        },
        {
            "name": "Christa Köller",
            "member_since": _d(2016, 6, 1),
            "engagement_score": 0.3,
            "is_resident": True,
            "people": [
                ("Christa", "Köller", _d(1950, 8, 30), "f", "6", "4", None, None, "34"),
            ],
        },
    ]

    # -- Bewerber ----------------------------------------------------------
    applicants = [
        {
            "name": "Simon Kruse",
            "member_since": _d(2024, 5, 1),
            "engagement_score": 0.2,
            "is_resident": False,
            "wbs_status": "WBS Einkommensgruppe A",
            "desired_apartment_size": "1,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Simon", "Kruse", _d(1988, 11, 29), "m", "1", "7", None,
                 "Behinderung (GdB 40 mit Gleichstellung)", "637"),
            ],
        },
        {
            "name": "Anja Venjakob",
            "member_since": _d(2023, 1, 1),
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Anja", "Venjakob", _d(1977, 6, 23), "f", "2", "7", None, None, "628"),
                ("Jörg", "Höbing", _d(1974, 6, 17), "m", "2", "7", None, None, "627"),
            ],
        },
        {
            "name": "Reinhilde Tenk",
            "member_since": _d(2017, 6, 1),
            "engagement_score": 0.7,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Reinhilde", "Tenk", _d(1954, 11, 10), "f", "5", "6", None, "Osteoporose", "26"),
                ("Thomas", "Tenk", _d(1958, 8, 17), "m", "4", "4", None, None, "27"),
            ],
        },
        {
            "name": "Kerstin Nolte",
            "member_since": _d(2019, 6, 1),
            "engagement_score": 0.4,
            "is_resident": False,
            "wbs_status": "WBS Einkommensgruppe A",
            "financial_status": "kann Anteile nicht übernehmen",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Kerstin", "Nolte", _d(1986, 5, 20), "f", "2", "6", None, None, "135"),
                ("Emmi", "Nolte", _d(2018, 1, 8), "f", "0", "0", None, None, None),
                ("Clara", "Nolte", _d(2018, 1, 8), "f", "0", "0", None, None, None),
            ],
        },
        {
            "name": "Sandra Rocha",
            "member_since": _d(2017, 1, 1),
            "engagement_score": 0.6,
            "is_resident": False,
            "wbs_status": "WBS Einkommensgruppe A",
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "pets_count": 1,
            "pets_info": "Hund",
            "people": [
                ("Sandra A.", "Rocha", _d(1980, 12, 15), "f", "2", "6",
                 "lateinamerikanisch", None, "12"),
                ("Silas K. M.", "Rocha Hegmanns", _d(2004, 9, 22), "m", "0", "4",
                 None, None, None),
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
            wbs_status=hh_data.get("wbs_status"),
            desired_apartment_size=hh_data.get("desired_apartment_size"),
            desired_apartment_type=hh_data.get("desired_apartment_type"),
            financial_status=hh_data.get("financial_status"),
            pets_count=hh_data.get("pets_count", 0),
            pets_info=hh_data.get("pets_info"),
        )
        db.add(hh)
        db.flush()
        for first, last, birth, gender, occ, edu, culture, special, member_nr in hh_data["people"]:
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
        (0, [0, 1]),    # Kruse (1 Pers.) → 1.5er
        (1, [5, 6]),    # Venjakob/Höbing (2 Pers.) → 3.5er
        (2, [5, 6]),    # Tenk (2 Pers.) → 3.5er
        (3, [7, 8]),    # Nolte (3 Pers.) → 4.5 + 5.5
        (4, [5, 6]),    # Rocha (2 Pers.) → 3.5er
    ]
    for hh_idx, apt_indices in assignment:
        for apt_idx in apt_indices:
            db.add(models.Application(
                household_id=applicant_hhs[hh_idx].id,
                apartment_id=db_apartments[apt_idx].id,
            ))

    db.commit()

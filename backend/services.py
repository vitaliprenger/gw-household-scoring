import pandas as pd
from sqlalchemy.orm import Session
from . import models, apartment_seed_data
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


def seed_apartments(db: Session) -> int:
    """Legt die Wohnungsstammdaten an (siehe ``apartment_seed_data``).

    Idempotent: Wohnungen, deren ``unit_number`` bereits existiert, bleiben
    unverändert — im Frontend vorgenommene Änderungen werden nicht überschrieben.
    """
    existing = {row[0] for row in db.query(models.Apartment.unit_number).all()}
    created = 0
    for row in apartment_seed_data.APARTMENTS:
        data = dict(zip(apartment_seed_data.FIELDS, row))
        if data["unit_number"] in existing:
            continue
        db.add(models.Apartment(**data))
        created += 1
    if created:
        db.commit()
    return created


def assign_household(db: Session, apartment: models.Apartment, household_id: int | None) -> bool:
    """Ordnet der Wohnung den Haushalt zu, der darin wohnt (oder löst die Zuordnung).

    Ein Haushalt wohnt in genau einer Wohnung: eine bestehende Zuordnung des
    Haushalts zu einer anderen Wohnung wird dabei gelöst. Der Haushalt gilt
    danach als Bewohner (``is_resident``).
    """
    if household_id is None:
        if apartment.household_id is None:
            return False
        apartment.household_id = None
        return True

    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise ValueError(f"Haushalt {household_id} nicht gefunden")

    if apartment.household_id == household_id:
        return False

    for other in db.query(models.Apartment).filter(
        models.Apartment.household_id == household_id,
        models.Apartment.id != apartment.id,
    ).all():
        other.household_id = None

    apartment.household_id = household_id
    household.is_resident = True
    if not household.apartment_unit:
        household.apartment_unit = apartment.unit_number
    household.updated_at = datetime.utcnow()
    return True


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
            "wbs_status": "WBS Einkommensgruppe A",
            "desired_apartment_size": "1,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Reinhilde", "Tenk", _d(1954, 11, 10), "f", "5", "6", None, "Osteoporose", "26", _d(2017, 6, 1)),
            ],
        },
        {
            "name": "Thomas Tenk",
            "engagement_score": 0.5,
            "is_resident": False,
            "wbs_status": "kein WBS",
            "desired_apartment_size": "2,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
            "people": [
                ("Thomas", "Tenk", _d(1958, 8, 17), "m", "4", "4", None, None, "27", _d(2017, 6, 1)),
            ],
        },
        {
            "name": "Kerstin Nolte",
            "engagement_score": 0.4,
            "is_resident": False,
            "wbs_status": "WBS Einkommensgruppe A",
            "financial_status": "kann Anteile nicht übernehmen",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
            "wbs_status": "WBS Einkommensgruppe A",
            "desired_apartment_size": "3,5",
            "desired_apartment_type": ["Standard Wohnungstypen"],
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
        (0, ["P.104", "P.204"]),          # Kruse (1 Pers.)   → 1,5 Zimmer
        (1, ["P.106", "P.206"]),          # Venjakob/Höbing   → 3,5 Zimmer
        (2, ["P.106", "P.206"]),          # R. Tenk           → 3,5 Zimmer
        (3, ["P.211", "W.212"]),          # Nolte (3 Pers.)   → 4,5 / 5,5 Zimmer
        (4, ["P.208", "P.106"]),          # Rocha (2 Pers.)   → 3,5 Zimmer
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

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from typing import List

from datetime import datetime
from . import models, schemas, database, services, scoring, auth, import_service, vcf_import_service

models.Base.metadata.create_all(bind=database.engine)

with database.engine.connect() as conn:
    hh_columns = {c["name"] for c in inspect(database.engine).get_columns("households")}
    hh_migrations = {
        "is_resident": "ALTER TABLE households ADD COLUMN is_resident BOOLEAN DEFAULT 0",
        "wbs_status": "ALTER TABLE households ADD COLUMN wbs_status TEXT",
        "pets_count": "ALTER TABLE households ADD COLUMN pets_count INTEGER DEFAULT 0",
        "pets_info": "ALTER TABLE households ADD COLUMN pets_info TEXT",
        "desired_apartment_size": "ALTER TABLE households ADD COLUMN desired_apartment_size TEXT",
        "desired_apartment_type": "ALTER TABLE households ADD COLUMN desired_apartment_type TEXT",
        "wheelchair_accessible": "ALTER TABLE households ADD COLUMN wheelchair_accessible BOOLEAN DEFAULT 0",
        "financial_status": "ALTER TABLE households ADD COLUMN financial_status TEXT",
        "import_source": "ALTER TABLE households ADD COLUMN import_source TEXT",
        "import_timestamp": "ALTER TABLE households ADD COLUMN import_timestamp DATETIME",
        "household_member_count": "ALTER TABLE households ADD COLUMN household_member_count INTEGER",
        "cultural_diversity_score": "ALTER TABLE households ADD COLUMN cultural_diversity_score REAL DEFAULT 0.0",
        "special_needs_score": "ALTER TABLE households ADD COLUMN special_needs_score REAL DEFAULT 0.0",
        "archived": "ALTER TABLE households ADD COLUMN archived BOOLEAN DEFAULT 0",
        "updated_at": "ALTER TABLE households ADD COLUMN updated_at DATETIME",
        "apartment_unit": "ALTER TABLE households ADD COLUMN apartment_unit TEXT",
        "vcf_import_timestamp": "ALTER TABLE households ADD COLUMN vcf_import_timestamp DATETIME",
    }
    for col, sql in hh_migrations.items():
        if col not in hh_columns:
            conn.execute(text(sql))

    person_columns = {c["name"] for c in inspect(database.engine).get_columns("people")}
    person_migrations = {
        "member_number": "ALTER TABLE people ADD COLUMN member_number TEXT",
        "individual_import_timestamp": "ALTER TABLE people ADD COLUMN individual_import_timestamp DATETIME",
        "archived": "ALTER TABLE people ADD COLUMN archived BOOLEAN DEFAULT 0",
        "updated_at": "ALTER TABLE people ADD COLUMN updated_at DATETIME",
        "member_since": "ALTER TABLE people ADD COLUMN member_since DATETIME",
        "vcf_import_timestamp": "ALTER TABLE people ADD COLUMN vcf_import_timestamp DATETIME",
    }
    for col, sql in person_migrations.items():
        if col not in person_columns:
            conn.execute(text(sql))

    apartment_columns = {c["name"] for c in inspect(database.engine).get_columns("apartments")}
    apartment_migrations = {
        "area_shares": "ALTER TABLE apartments ADD COLUMN area_shares REAL",
        "area_rent": "ALTER TABLE apartments ADD COLUMN area_rent REAL",
        "area_utilities": "ALTER TABLE apartments ADD COLUMN area_utilities REAL",
        "apartment_category": "ALTER TABLE apartments ADD COLUMN apartment_category TEXT",
        "is_small": "ALTER TABLE apartments ADD COLUMN is_small BOOLEAN DEFAULT 0",
        "min_occupants": "ALTER TABLE apartments ADD COLUMN min_occupants INTEGER",
        "household_id": "ALTER TABLE apartments ADD COLUMN household_id INTEGER REFERENCES households(id)",
    }
    for col, sql in apartment_migrations.items():
        if col not in apartment_columns:
            conn.execute(text(sql))

    # Mini WGs sind Standardwohnungen mit 3 Zimmern, die klein ausfallen.
    # Muss laufen, solange die alte Typ-Spalte sie noch identifizieren kann.
    if "apartment_type" in apartment_columns:
        conn.execute(text(
            "UPDATE apartments SET apartment_category = 'Standard Wohnungstypen',"
            " size_rooms = 3, is_small = 1 WHERE apartment_type = 'Mini WG'"
        ))

    # C-Riegel, Gartencluster und Wohngemeinschaften sind Clusterwohnungen
    conn.execute(text(
        "UPDATE apartments SET apartment_category = 'Clusterwohnung'"
        " WHERE apartment_category IN ('C-Riegel', 'Gartencluster', 'Wohngemeinschaft')"
    ))

    # Halbe Zimmer entfallen: 3.5 -> 3
    conn.execute(text(
        "UPDATE apartments SET size_rooms = CAST(size_rooms AS INTEGER) WHERE size_rooms IS NOT NULL"
    ))

    # Etage und Rohwert "Typ" werden nicht mehr geführt
    for col in ("floor", "apartment_type"):
        if col in apartment_columns:
            conn.execute(text(f"ALTER TABLE apartments DROP COLUMN {col}"))

    # Migrate member_since from households to people
    if "member_since" in hh_columns:
        conn.execute(text(
            "UPDATE people SET member_since = ("
            "  SELECT households.member_since FROM households"
            "  WHERE households.id = people.household_id"
            ") WHERE people.member_since IS NULL"
        ))

    # Migrate special_needs from BOOLEAN to TEXT
    result = conn.execute(text("SELECT typeof(special_needs) FROM people WHERE special_needs IS NOT NULL LIMIT 1"))
    row = result.fetchone()
    if row and row[0] == "integer":
        conn.execute(text("UPDATE people SET special_needs = NULL WHERE special_needs = 0"))
        conn.execute(text("UPDATE people SET special_needs = 'Ja' WHERE special_needs = 1"))

    # Migrate desired_apartment_type from plain string to JSON array
    rows = conn.execute(text(
        "SELECT id, desired_apartment_type FROM households "
        "WHERE desired_apartment_type IS NOT NULL AND desired_apartment_type != ''"
    )).fetchall()
    import json as _json
    for r in rows:
        val = r[1]
        try:
            parsed = _json.loads(val)
            if isinstance(parsed, list):
                continue
        except (ValueError, TypeError):
            pass
        arr = _json.dumps([val])
        conn.execute(text("UPDATE households SET desired_apartment_type = :v WHERE id = :id"), {"v": arr, "id": r[0]})

    # "Gartencluster" ist keine eigene Wohnungsart mehr, sondern eine Clusterwohnung
    rows = conn.execute(text(
        "SELECT id, desired_apartment_type FROM households "
        "WHERE desired_apartment_type LIKE '%Gartencluster%'"
    )).fetchall()
    for r in rows:
        try:
            types = _json.loads(r[1])
        except (ValueError, TypeError):
            continue
        if not isinstance(types, list):
            continue
        replaced = ["Clusterwohnung" if t == "Gartencluster" else t for t in types]
        deduped = list(dict.fromkeys(replaced))
        conn.execute(
            text("UPDATE households SET desired_apartment_type = :v WHERE id = :id"),
            {"v": _json.dumps(deduped), "id": r[0]},
        )

    conn.commit()

app = FastAPI(title="Wohnungsvergabe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    db = database.SessionLocal()
    scoring.initialize_config(db)
    services.seed_apartments(db)
    db.close()

@app.post("/token")
def login(form_data: dict):
    password = form_data.get("password", "")
    token = auth.verify_password(password)
    return {"access_token": token, "token_type": "bearer"}

# --- Households ---
@app.post("/households/", response_model=schemas.Household)
def create_household(
    household: schemas.HouseholdCreate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    db_household = models.Household(
        name=household.name,
        engagement_score=household.engagement_score,
        is_resident=household.is_resident,
    )
    db.add(db_household)
    db.commit()
    db.refresh(db_household)

    for person in household.people:
        db_person = models.Person(**person.dict(), household_id=db_household.id)
        db.add(db_person)

    db.commit()
    db.refresh(db_household)
    return db_household

@app.get("/households/", response_model=List[schemas.Household])
def read_households(
    skip: int = 0,
    limit: int = 1000,
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    query = db.query(models.Household)
    if not include_archived:
        query = query.filter(models.Household.archived == False)
    households = query.offset(skip).limit(limit).all()
    return households

@app.get("/households/{household_id}", response_model=schemas.Household)
def read_household(
    household_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    hh = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not hh:
        raise HTTPException(status_code=404, detail="Haushalt nicht gefunden")
    return hh

@app.delete("/households/{household_id}")
def delete_household(
    household_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Löscht einen Haushalt samt Personen, Bewerbungen und löst die Wohnungszuordnung."""
    hh = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not hh:
        raise HTTPException(status_code=404, detail="Haushalt nicht gefunden")
    db.query(models.Application).filter(models.Application.household_id == household_id).delete()
    db.query(models.Person).filter(models.Person.household_id == household_id).delete()
    apt = db.query(models.Apartment).filter(models.Apartment.household_id == household_id).first()
    if apt:
        apt.household_id = None
    db.delete(hh)
    db.commit()
    return {"deleted": household_id}

@app.put("/households/{household_id}", response_model=schemas.Household)
def update_household(
    household_id: int,
    data: schemas.HouseholdUpdate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    hh = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not hh:
        raise HTTPException(status_code=404, detail="Haushalt nicht gefunden")
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload:
        name = (payload["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Haushaltsname darf nicht leer sein")
        payload["name"] = name
    for field, value in payload.items():
        setattr(hh, field, value)
    hh.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(hh)
    return hh

# --- People ---
@app.post("/people/", response_model=schemas.Person)
def create_person(
    person: schemas.PersonCreate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    db_person = models.Person(**person.model_dump())
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return db_person

@app.delete("/people/unassigned")
def delete_unassigned_persons(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Löscht alle Personen ohne Haushaltszuordnung auf einmal."""
    query = db.query(models.Person).filter(models.Person.household_id.is_(None))
    if not include_archived:
        query = query.filter(models.Person.archived == False)
    persons = query.all()
    for person in persons:
        db.delete(person)
    db.commit()
    return {"deleted": len(persons)}

@app.delete("/people/{person_id}")
def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Löscht eine Person. Blockiert, solange sie einem Haushalt zugeordnet ist."""
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    if person.household_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Person ist einem Haushalt zugeordnet und kann nicht gelöscht werden. "
                   "Bitte zuerst aus dem Haushalt entfernen.",
        )
    db.delete(person)
    db.commit()
    return {"deleted": person_id}

@app.put("/people/{person_id}", response_model=schemas.Person)
def update_person(
    person_id: int,
    data: schemas.PersonUpdate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    person.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(person)
    return person

@app.post("/people/{person_id}/assign/{household_id}", response_model=schemas.Person)
def assign_person(
    person_id: int,
    household_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    hh = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not hh:
        raise HTTPException(status_code=404, detail="Haushalt nicht gefunden")
    person.household_id = household_id
    person.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(person)
    return person

@app.delete("/people/{person_id}/assign", response_model=schemas.Person)
def unassign_person(
    person_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Entfernt eine Person aus ihrem Haushalt (Person bleibt bestehen)."""
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    person.household_id = None
    person.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(person)
    return person

@app.get("/people/", response_model=List[schemas.PersonWithHousehold])
def read_all_persons(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    query = db.query(models.Person)
    if not include_archived:
        query = query.filter(models.Person.archived == False)
    persons = query.all()
    result = []
    for p in persons:
        data = schemas.PersonWithHousehold.model_validate(p)
        if p.household:
            data.household_name = p.household.name
        result.append(data)
    return result

@app.patch("/households/{household_id}/archive")
def toggle_archive_household(
    household_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    hh = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not hh:
        raise HTTPException(status_code=404, detail="Haushalt nicht gefunden")
    hh.archived = not hh.archived
    for person in hh.people:
        person.archived = hh.archived
    db.commit()
    return {"archived": hh.archived}

@app.patch("/people/{person_id}/archive")
def toggle_archive_person(
    person_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    person.archived = not person.archived
    db.commit()
    return {"archived": person.archived}

@app.get("/people/unassigned", response_model=List[schemas.Person])
def read_unassigned_persons(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    query = db.query(models.Person).filter(models.Person.household_id.is_(None))
    if not include_archived:
        query = query.filter(models.Person.archived == False)
    return query.all()

# --- Apartments ---
@app.post("/apartments/", response_model=schemas.Apartment)
def create_apartment(
    apartment: schemas.ApartmentCreate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    db_apartment = models.Apartment(**apartment.dict())
    db.add(db_apartment)
    db.commit()
    db.refresh(db_apartment)
    return db_apartment

@app.get("/apartments/", response_model=List[schemas.Apartment])
def read_apartments(
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    apartments = (
        db.query(models.Apartment)
        .order_by(models.Apartment.unit_number)
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for apt in apartments:
        data = schemas.Apartment.model_validate(apt)
        if apt.household:
            data.household_name = apt.household.name
        result.append(data)
    return result

@app.put("/apartments/{apartment_id}", response_model=schemas.Apartment)
def update_apartment(
    apartment_id: int,
    data: schemas.ApartmentUpdate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    apt = db.query(models.Apartment).filter(models.Apartment.id == apartment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Wohnung nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(apt, field, value)
    db.commit()
    db.refresh(apt)
    return apt

@app.post("/apartments/{apartment_id}/assign/{household_id}", response_model=schemas.Apartment)
def assign_apartment(
    apartment_id: int,
    household_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Ordnet der Wohnung den Haushalt zu, der darin wohnt."""
    apt = db.query(models.Apartment).filter(models.Apartment.id == apartment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Wohnung nicht gefunden")
    try:
        services.assign_household(db, apt, household_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    db.commit()
    db.refresh(apt)
    result = schemas.Apartment.model_validate(apt)
    if apt.household:
        result.household_name = apt.household.name
    return result

@app.delete("/apartments/{apartment_id}/assign", response_model=schemas.Apartment)
def unassign_apartment(
    apartment_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Löst die Zuordnung Wohnung -> Haushalt (Wohnung bleibt bestehen)."""
    apt = db.query(models.Apartment).filter(models.Apartment.id == apartment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Wohnung nicht gefunden")
    services.assign_household(db, apt, None)
    db.commit()
    db.refresh(apt)
    return apt

@app.delete("/apartments/{apartment_id}")
def delete_apartment(
    apartment_id: int,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Löscht eine Wohnung samt der Bewerbungen auf diese Wohnung.

    Blockiert, solange ein Haushalt der Wohnung zugeordnet ist.
    """
    apt = db.query(models.Apartment).filter(models.Apartment.id == apartment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Wohnung nicht gefunden")
    if apt.household_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Wohnung ist einem Haushalt zugeordnet und kann nicht gelöscht werden. "
                   "Bitte zuerst die Zuordnung lösen.",
        )
    db.query(models.Application).filter(models.Application.apartment_id == apartment_id).delete()
    db.delete(apt)
    db.commit()
    return {"deleted": apartment_id}

# --- Applications ---
@app.post("/applications/", response_model=schemas.Application)
def create_application(
    application: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    db_application = models.Application(
        household_id=application.household_id,
        apartment_id=application.apartment_id,
    )
    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    return db_application

@app.get("/applications/", response_model=List[schemas.Application])
def read_applications(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    return db.query(models.Application).all()

# --- Import ---
@app.post("/upload/households/")
async def upload_households(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Ungültiges Dateiformat. Bitte eine Excel-Datei hochladen.")

    contents = await file.read()
    try:
        result = services.process_excel_upload(contents, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Scoring ---
@app.post("/scoring/calculate")
def calculate_scores(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    return scoring.run_scoring(db)

# --- Ranking ---
@app.get("/ranking/", response_model=List[schemas.RankingGroup])
def get_ranking(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Rangliste je Wohnungskategorie; Eignung und Punkte berechnet ``services.build_ranking``.

    Der Score ist je Kategorie verschieden: die Wohnraumausnutzung hängt an der
    Zimmerzahl und steckt in ``occupancy_score``.
    """
    return [
        schemas.RankingGroup(
            size_rooms=group["size_rooms"],
            funding_type=group["funding_type"],
            households=[
                schemas.RankedHousehold(
                    rank=rank,
                    id=entry.household.id,
                    name=entry.household.name,
                    member_count=entry.members,
                    engagement_score=entry.household.engagement_score,
                    base_score=entry.base_score,
                    occupancy_score=entry.occupancy_score,
                    total_score=entry.total_score,
                )
                for rank, entry in enumerate(group["households"], 1)
            ],
        )
        for group in services.build_ranking(db)
    ]

# --- Ist-Statistik ---
@app.get("/statistics/residents", response_model=schemas.ResidentStatistics)
def get_resident_statistics(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Ist-Statistik der aktuellen Bewohner: je Merkmal absolute Zahlen und Anteile.

    Bezugsmenge sind dieselben Personen, die auch die IST-Verteilung der
    Durchmischung bilden (nicht archivierte Personen in nicht archivierten
    Haushalten mit ``is_resident=True``).
    """
    return scoring.calculate_resident_statistics(db)

@app.get("/statistics/residents/missing", response_model=List[schemas.PersonMissingData])
def get_resident_missing_data(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    """Bewohner-Personen ohne Angabe zu mindestens einem Merkmal -- zur Kontrolle der Importe.

    Das sind genau die Datensaetze, die die Ist-Statistik beim jeweiligen
    Merkmal ignoriert; je Merkmal mit Grund und gespeichertem Rohwert.
    """
    return scoring.resident_people_missing_data(db)

@app.get("/scoring/config", response_model=List[schemas.ScoringConfig])
def get_scoring_config(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    return db.query(models.ScoringConfig).all()

# --- Import (Fragebogen) ---
@app.post("/import/household-bogen/analyze", response_model=schemas.HHAnalysisResponse)
async def analyze_hh_bogen(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Bitte eine .xlsx-Datei hochladen.")
    contents = await file.read()
    try:
        return import_service.analyze_household_bogen(contents, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/household-bogen/commit", response_model=schemas.HHCommitResponse)
def commit_hh_bogen(
    request: schemas.HHCommitRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    try:
        return import_service.commit_household_bogen(request, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/individual-bogen/analyze", response_model=schemas.IndividualAnalysisResponse)
async def analyze_individual_bogen(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Bitte eine .xlsx-Datei hochladen.")
    contents = await file.read()
    try:
        return import_service.analyze_individual_bogen(contents, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/individual-bogen/commit", response_model=schemas.IndividualCommitResponse)
def commit_individual_bogen(
    request: schemas.IndividualCommitRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    try:
        return import_service.commit_individual_bogen(request, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/vcf/analyze", response_model=schemas.VcfAnalysisResponse)
async def analyze_vcf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    if not file.filename.lower().endswith(('.vcf', '.vcard')):
        raise HTTPException(status_code=400, detail="Bitte eine .vcf-Datei hochladen.")
    contents = await file.read()
    try:
        return vcf_import_service.analyze_vcf(contents, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/vcf/commit", response_model=schemas.VcfCommitResponse)
def commit_vcf(
    request: schemas.VcfCommitRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    try:
        return vcf_import_service.commit_vcf(request, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/import/session/{session_id}")
def get_import_session(
    session_id: str,
    _=Depends(auth.require_auth),
):
    session = import_service.import_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    return {"session_id": session.id, "type": session.session_type, "created_at": session.created_at.isoformat()}

@app.delete("/import/session/{session_id}")
def delete_import_session(
    session_id: str,
    _=Depends(auth.require_auth),
):
    if session_id in import_service.import_sessions:
        del import_service.import_sessions[session_id]
        return {"message": "Session gelöscht"}
    raise HTTPException(status_code=404, detail="Session nicht gefunden")

@app.put("/scoring/config")
def update_scoring_config(
    configs: List[schemas.ScoringConfigBase],
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    for conf in configs:
        db_conf = db.query(models.ScoringConfig).filter(models.ScoringConfig.key == conf.key).first()
        if db_conf:
            db_conf.value = conf.value
            db_conf.description = conf.description
    db.commit()
    return {"message": "Konfiguration aktualisiert"}

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from typing import List

from . import models, schemas, database, services, scoring, auth, import_service

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
    }
    for col, sql in hh_migrations.items():
        if col not in hh_columns:
            conn.execute(text(sql))

    person_columns = {c["name"] for c in inspect(database.engine).get_columns("people")}
    if "member_number" not in person_columns:
        conn.execute(text("ALTER TABLE people ADD COLUMN member_number TEXT"))

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
    services.seed_example_data(db)
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
        member_since=household.member_since,
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
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    households = db.query(models.Household).offset(skip).limit(limit).all()
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
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hh, field, value)
    db.commit()
    db.refresh(hh)
    return hh

# --- People ---
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
    db.commit()
    db.refresh(person)
    return person

@app.get("/people/", response_model=List[schemas.PersonWithHousehold])
def read_all_persons(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    persons = db.query(models.Person).all()
    result = []
    for p in persons:
        data = schemas.PersonWithHousehold.model_validate(p)
        if p.household:
            data.household_name = p.household.name
        result.append(data)
    return result

@app.get("/people/unassigned", response_model=List[schemas.Person])
def read_unassigned_persons(
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    return db.query(models.Person).filter(models.Person.household_id.is_(None)).all()

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
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    apartments = db.query(models.Apartment).offset(skip).limit(limit).all()
    return apartments

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
    categories = (
        db.query(models.Apartment.size_rooms, models.Apartment.funding_type)
        .distinct()
        .order_by(models.Apartment.size_rooms, models.Apartment.funding_type)
        .all()
    )

    result = []
    for size_rooms, funding_type in categories:
        households = (
            db.query(models.Household)
            .join(models.Application)
            .join(models.Apartment)
            .filter(
                models.Apartment.size_rooms == size_rooms,
                models.Apartment.funding_type == funding_type,
            )
            .order_by(models.Household.total_score.desc())
            .all()
        )

        ranked = [
            schemas.RankedHousehold(
                rank=i,
                id=h.id,
                name=h.name,
                member_count=len(h.people),
                engagement_score=h.engagement_score,
                total_score=h.total_score,
                people=h.people,
            )
            for i, h in enumerate(households, 1)
        ]

        result.append(schemas.RankingGroup(
            size_rooms=size_rooms,
            funding_type=funding_type,
            households=ranked,
        ))

    return result

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

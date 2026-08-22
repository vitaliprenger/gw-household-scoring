from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from typing import List

from . import models, schemas, database, services, scoring, auth

models.Base.metadata.create_all(bind=database.engine)

with database.engine.connect() as conn:
    columns = [c["name"] for c in inspect(database.engine).get_columns("households")]
    if "is_resident" not in columns:
        conn.execute(text("ALTER TABLE households ADD COLUMN is_resident BOOLEAN DEFAULT 0"))
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
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(auth.require_auth),
):
    households = db.query(models.Household).offset(skip).limit(limit).all()
    return households

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

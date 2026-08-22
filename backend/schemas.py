from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Person Schemas ---
class PersonBase(BaseModel):
    first_name: str
    last_name: str
    birth_date: datetime
    gender: str
    occupation_type: str
    education_level: str
    cultural_background: Optional[str] = None
    special_needs: bool = False

class PersonCreate(PersonBase):
    pass

class Person(PersonBase):
    id: int
    household_id: int

    class Config:
        from_attributes = True

# --- Household Schemas ---
class HouseholdBase(BaseModel):
    name: str
    member_since: Optional[datetime] = None
    engagement_score: float = 0.0
    is_resident: bool = False

class HouseholdCreate(HouseholdBase):
    people: List[PersonCreate] = []

class Household(HouseholdBase):
    id: int
    application_date: datetime
    total_score: float
    people: List[Person] = []

    class Config:
        from_attributes = True

# --- Apartment Schemas ---
class ApartmentBase(BaseModel):
    unit_number: str
    size_rooms: float
    funding_type: str

class ApartmentCreate(ApartmentBase):
    pass

class Apartment(ApartmentBase):
    id: int

    class Config:
        from_attributes = True

# --- Scoring Config Schemas ---
class ScoringConfigBase(BaseModel):
    key: str
    value: float
    description: Optional[str] = None

class ScoringConfig(ScoringConfigBase):
    class Config:
        from_attributes = True

# --- Application Schemas ---
class ApplicationBase(BaseModel):
    household_id: int
    apartment_id: int

class ApplicationCreate(ApplicationBase):
    pass

class Application(ApplicationBase):
    id: int
    status: str

    class Config:
        from_attributes = True

# --- Ranking Schemas ---
class RankedHousehold(BaseModel):
    rank: int
    id: int
    name: str
    member_count: int
    engagement_score: float
    total_score: float
    people: List[Person] = []

    class Config:
        from_attributes = True

class RankingGroup(BaseModel):
    size_rooms: float
    funding_type: str
    households: List[RankedHousehold] = []

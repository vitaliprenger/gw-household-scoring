from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Person Schemas ---
class PersonBase(BaseModel):
    first_name: str
    last_name: str
    birth_date: Optional[datetime] = None
    gender: Optional[str] = None
    occupation_type: Optional[str] = None
    education_level: Optional[str] = None
    cultural_background: Optional[str] = None
    special_needs: Optional[str] = None
    member_number: Optional[str] = None
    member_since: Optional[datetime] = None

class PersonCreate(PersonBase):
    pass

class PersonUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[datetime] = None
    gender: Optional[str] = None
    occupation_type: Optional[str] = None
    education_level: Optional[str] = None
    cultural_background: Optional[str] = None
    special_needs: Optional[str] = None
    member_number: Optional[str] = None
    member_since: Optional[datetime] = None
    household_id: Optional[int] = None
    archived: Optional[bool] = None

class Person(PersonBase):
    id: int
    household_id: Optional[int] = None
    individual_import_timestamp: Optional[datetime] = None
    vcf_import_timestamp: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False

    class Config:
        from_attributes = True

class PersonWithHousehold(Person):
    household_name: Optional[str] = None

# --- Household Schemas ---
class HouseholdBase(BaseModel):
    name: str
    engagement_score: float = 0.0
    cultural_diversity_score: float = 0.0
    special_needs_score: float = 0.0
    is_resident: bool = False
    wbs_status: Optional[str] = None
    pets_count: int = 0
    pets_info: Optional[str] = None
    desired_apartment_size: Optional[str] = None
    desired_apartment_type: Optional[List[str]] = None
    wheelchair_accessible: bool = False
    financial_status: Optional[str] = None
    import_source: Optional[str] = None
    import_timestamp: Optional[datetime] = None
    household_member_count: Optional[int] = None
    apartment_unit: Optional[str] = None
    vcf_import_timestamp: Optional[datetime] = None

class HouseholdCreate(HouseholdBase):
    people: List[PersonCreate] = []

class HouseholdUpdate(BaseModel):
    name: Optional[str] = None
    engagement_score: Optional[float] = None
    cultural_diversity_score: Optional[float] = None
    special_needs_score: Optional[float] = None
    wbs_status: Optional[str] = None
    pets_count: Optional[int] = None
    pets_info: Optional[str] = None
    desired_apartment_size: Optional[str] = None
    desired_apartment_type: Optional[List[str]] = None
    wheelchair_accessible: Optional[bool] = None
    financial_status: Optional[str] = None
    household_member_count: Optional[int] = None
    apartment_unit: Optional[str] = None
    archived: Optional[bool] = None

class Household(HouseholdBase):
    id: int
    application_date: datetime
    total_score: float
    updated_at: Optional[datetime] = None
    archived: bool = False
    people: List[Person] = []
    assigned_apartment_unit: Optional[str] = None

    class Config:
        from_attributes = True

# --- Apartment Schemas ---
class ApartmentBase(BaseModel):
    unit_number: str
    size_rooms: Optional[int] = None
    funding_type: str
    apartment_category: Optional[str] = None
    is_small: bool = False
    area_shares: Optional[float] = None
    area_rent: Optional[float] = None
    area_utilities: Optional[float] = None
    min_occupants: Optional[int] = None
    household_id: Optional[int] = None

class ApartmentCreate(ApartmentBase):
    pass

class ApartmentUpdate(BaseModel):
    unit_number: Optional[str] = None
    size_rooms: Optional[int] = None
    funding_type: Optional[str] = None
    apartment_category: Optional[str] = None
    is_small: Optional[bool] = None
    area_shares: Optional[float] = None
    area_rent: Optional[float] = None
    area_utilities: Optional[float] = None
    min_occupants: Optional[int] = None
    household_id: Optional[int] = None

class Apartment(ApartmentBase):
    id: int
    household_name: Optional[str] = None

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
    size_rooms: Optional[int] = None
    funding_type: str
    households: List[RankedHousehold] = []

# --- Import Schemas ---
class ImportPersonPreview(BaseModel):
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    member_number: Optional[str] = None
    birth_date: Optional[str] = None

class FuzzyCandidate(BaseModel):
    household_id: int
    name: str
    score: float
    member_numbers: List[str] = []

class MatchResult(BaseModel):
    type: str
    matched_household_id: Optional[int] = None
    matched_household_name: Optional[str] = None
    confidence: float = 0.0
    fuzzy_candidates: List[FuzzyCandidate] = []

class DataChange(BaseModel):
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None

class ExistingDataChanges(BaseModel):
    fields_to_overwrite: List[DataChange] = []
    data_removals: List[DataChange] = []

class HouseholdImportPreview(BaseModel):
    temp_id: str
    timestamp: str
    wbs_status: Optional[str] = None
    financial_status: Optional[str] = None
    declared_member_count: int = 0
    wheelchair_accessible: bool = False
    desired_apartment_type: Optional[List[str]] = None
    desired_apartment_size: Optional[str] = None
    pets_count: int = 0
    pets_info: Optional[str] = None
    persons: List[ImportPersonPreview] = []
    match_result: MatchResult
    member_count_mismatch: bool = False
    already_imported: bool = False
    existing_data_changes: Optional[ExistingDataChanges] = None

class PrivacyWarning(BaseModel):
    row: int
    name: str

class HHAnalysisResponse(BaseModel):
    session_id: str
    total_rows: int
    skipped_not_submitted: int
    skipped_duplicates: int = 0
    privacy_warnings: List[PrivacyWarning] = []
    households: List[HouseholdImportPreview] = []

class HouseholdDecision(BaseModel):
    temp_id: str
    action: str
    target_household_id: Optional[int] = None
    confirm_data_removals: bool = False

class HHCommitRequest(BaseModel):
    session_id: str
    decisions: List[HouseholdDecision]

class HHCommitResponse(BaseModel):
    imported: int
    updated: int
    skipped: int
    created_household_ids: List[int] = []

class IndividualImportPreview(BaseModel):
    temp_id: str
    name: str
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    member_number: Optional[str] = None
    timestamp: str
    gender: Optional[str] = None
    occupation: Optional[str] = None
    education: Optional[str] = None
    life_situation: Optional[str] = None
    social_diversity: Optional[str] = None
    match_result: MatchResult
    already_imported: bool = False
    is_older: bool = False
    existing_data_changes: Optional[ExistingDataChanges] = None

class IndividualAnalysisResponse(BaseModel):
    session_id: str
    total_rows: int
    skipped_not_submitted: int
    skipped_duplicates: int = 0
    privacy_warnings: List[PrivacyWarning] = []
    hh_import_warning: bool = False
    individuals: List[IndividualImportPreview] = []

class IndividualDecision(BaseModel):
    temp_id: str
    action: str
    target_person_id: Optional[int] = None
    target_household_id: Optional[int] = None
    confirm_data_removals: bool = False

class IndividualCommitRequest(BaseModel):
    session_id: str
    decisions: List[IndividualDecision]

class IndividualCommitResponse(BaseModel):
    updated: int
    created: int
    skipped: int

# --- VCF-Import Schemas ---
class VcfPersonPreview(BaseModel):
    temp_id: str
    name: str
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    member_number: Optional[str] = None
    member_since: Optional[str] = None
    apartment_unit: Optional[str] = None
    role: str
    source: str
    mentioned_by: Optional[str] = None

class VcfHouseholdPreview(BaseModel):
    temp_id: str
    name: str
    apartment_unit: Optional[str] = None
    address: Optional[str] = None
    is_resident: bool = False
    timestamp: Optional[str] = None
    persons: List[VcfPersonPreview] = []
    match_result: MatchResult
    already_imported: bool = False
    warnings: List[str] = []
    existing_data_changes: Optional[ExistingDataChanges] = None

class VcfAnalysisResponse(BaseModel):
    session_id: str
    total_cards: int
    skipped_no_name: int = 0
    total_persons: int = 0
    resident_households: int = 0
    households: List[VcfHouseholdPreview] = []

class VcfDecision(BaseModel):
    temp_id: str
    action: str
    target_household_id: Optional[int] = None
    excluded_person_temp_ids: List[str] = []

class VcfCommitRequest(BaseModel):
    session_id: str
    decisions: List[VcfDecision]

class VcfCommitResponse(BaseModel):
    households_created: int
    households_updated: int
    households_skipped: int
    persons_created: int
    persons_updated: int
    persons_assigned: int
    created_household_ids: List[int] = []


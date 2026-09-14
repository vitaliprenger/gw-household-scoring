from pydantic import BaseModel, field_validator, model_validator
from typing import Dict, List, Optional
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
class ApplicationWish(BaseModel):
    """Eine gewünschte Wohnungskategorie.

    Entspricht dem Schlüssel, den ``services.apartment_categories`` liefert:
    Zimmerzahl x Förderungsart, dazu optional die Wohnungsart. ``None`` heißt
    in jedem Feld "egal" -- so lässt sich auch ein Wunsch wie "WBS B, Größe egal"
    abbilden, ohne Freitext zu benötigen.
    """
    size_rooms: Optional[int] = None           # 2 für "2,5"; None = Größe egal
    funding_type: Optional[str] = None         # "WBS A" | "WBS B" | "freifinanziert"; None = egal
    apartment_category: Optional[str] = None   # "Clusterwohnung" | "Joker" | None = Standard

class ApplicationBase(BaseModel):
    household_id: int
    kind: str = "wartepool"
    requested_at: Optional[datetime] = None
    wishes: List[ApplicationWish] = []

    @field_validator("wishes", mode="before")
    @classmethod
    def _wishes_never_none(cls, value):
        """Die JSON-Spalte ist leer, solange kein Wunsch gepflegt ist."""
        return value or []

    status: str = "offen"
    status_note: Optional[str] = None
    special_case: bool = False
    special_case_note: Optional[str] = None
    note: Optional[str] = None
    fulfilled_apartment_id: Optional[int] = None
    fulfilled_at: Optional[datetime] = None

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationUpdate(BaseModel):
    kind: Optional[str] = None
    requested_at: Optional[datetime] = None
    wishes: Optional[List[ApplicationWish]] = None
    status: Optional[str] = None
    status_note: Optional[str] = None
    special_case: Optional[bool] = None
    special_case_note: Optional[str] = None
    note: Optional[str] = None
    fulfilled_apartment_id: Optional[int] = None
    archived: Optional[bool] = None

class Application(ApplicationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False

    class Config:
        from_attributes = True

class ApplicationWithHousehold(Application):
    """Bewerbung samt der Angaben, die die Übersicht ohne Nachladen braucht."""
    household_name: Optional[str] = None
    member_count: int = 0
    is_resident: bool = False
    wbs_status: Optional[str] = None
    current_apartment_unit: Optional[str] = None    # "Aktuelle Wohnung" (aus der Zuordnung)
    fulfilled_apartment_unit: Optional[str] = None  # "neue Wohnung"

class ApartmentCategory(BaseModel):
    """Wählbare Wunschkategorie, abgeleitet aus den Wohnungsstammdaten."""
    size_rooms: Optional[int] = None
    funding_type: Optional[str] = None
    apartment_category: Optional[str] = None
    label: str                                      # Anzeige in der Schreibweise der Liste, z. B. "2,5 A"
    apartment_count: int = 0                        # wie viele Wohnungen dahinterstehen

# --- Ranking Schemas ---
class RankedHousehold(BaseModel):
    rank: int
    id: int
    name: str
    member_count: int
    engagement_score: float
    base_score: float       # haushaltseigene Kriterien, unabhängig von der Wohnung
    occupancy_score: float  # Wohnraumausnutzung für die Zimmerzahl dieser Kategorie
    total_score: float      # base_score + occupancy_score
    #: Der Haushalt steht nur hier, weil er diese Kategorie ausdrücklich wünscht --
    #: die Eignungsprüfung würde ihn ausschließen (evtl. unvollständige Angaben).
    by_wish_only: bool = False
    special_case: bool = False
    special_case_note: Optional[str] = None
    requested_at: Optional[datetime] = None
    #: Die gespeicherte Grundpunktzahl weicht von der aktuellen Berechnung ab
    #: (Daten geändert oder Stichtag verschoben, ohne neu zu berechnen).
    is_stale: bool = False
    size_rooms: Optional[int] = None
    funding_type: Optional[str] = None

    class Config:
        from_attributes = True

class PriorityEntry(BaseModel):
    """Ein Wechselwunsch in einer Kategorie -- Vorrang nach Datum, ohne Scoring."""
    rank: int
    id: int
    name: str
    member_count: int
    requested_at: Optional[datetime] = None
    current_apartment_unit: Optional[str] = None
    special_case: bool = False
    special_case_note: Optional[str] = None

class RankingGroup(BaseModel):
    size_rooms: Optional[int] = None
    funding_type: str
    #: Wechselwünsche, die dieser Kategorie gelten -- stehen vor der Rangliste
    priority: List[PriorityEntry] = []
    households: List[RankedHousehold] = []

class JokerWaitEntry(BaseModel):
    """Bewerbung auf ein Joker-Zimmer -- reine Warteliste nach Datum."""
    rank: int
    application_id: int
    household_id: int
    household_name: str
    requested_at: Optional[datetime] = None
    current_apartment_unit: Optional[str] = None
    special_case: bool = False
    special_case_note: Optional[str] = None

# --- Ist-Statistik Schemas ---
class StatisticsGroup(BaseModel):
    """Eine Merkmalsauspraegung der Ist-Statistik, absolut und relativ."""
    key: str
    label: str
    count: int                              # absolute Zahl
    ratio: float                            # Anteil an der Bezugsgroesse (0..1)
    target_ratio: Optional[float] = None    # Zielwert als Anteil, falls konfiguriert
    target_count: Optional[float] = None    # Zielwert absolut (target_ratio x total)

class StatisticsExcludedGroup(BaseModel):
    """Auspraegung ausserhalb der Bezugsgroesse, nur nachrichtlich (z. B. "unter 20")."""
    key: str
    label: str
    count: int

class StatisticsCategory(BaseModel):
    key: str
    label: str
    basis: str                              # "person" oder "household"
    total: int                              # Bezugsgroesse der Anteile: nur Datensaetze mit Angabe
    unknown_count: int = 0                  # ohne Angabe -- ignoriert, weder Gruppe noch Bezugsgroesse
    excluded_groups: List[StatisticsExcludedGroup] = []  # Angabe, aber ausserhalb der Bezugsgroesse
    groups: List[StatisticsGroup] = []

class ResidentStatistics(BaseModel):
    household_count: int
    person_count: int
    incomplete_person_count: int = 0        # Personen mit mindestens einer fehlenden Angabe
    categories: List[StatisticsCategory] = []

class MissingValue(BaseModel):
    """Ein Merkmal, bei dem eine Person als "keine Angabe" gilt."""
    dimension: str                          # "age", "gender", "occupation", "education"
    reason: str                             # "empty", "category_0", "unrecognized"
    raw_value: Optional[str] = None         # gespeicherter Wert, sofern vorhanden
    suspected_import_error: bool = False    # nicht erkannter Wert oder leer trotz Individualbogen

class PersonMissingData(BaseModel):
    """Bewohner-Person mit fehlenden Angaben -- Eintrag der Pruefliste."""
    person_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    member_number: Optional[str] = None
    household_id: int
    household_name: Optional[str] = None
    apartment_unit: Optional[str] = None
    age: Optional[int] = None
    individual_import_timestamp: Optional[datetime] = None
    missing: List[MissingValue] = []

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

#: Treffer-Arten, die **eindeutig** sind und deshalb automatisch zugeordnet
#: werden dürfen:
#:
#: * ``exact_member_nr`` — eindeutige Mitgliedsnummer,
#: * ``exact_name_dob`` — exakt übereinstimmender Personenname (mit oder ohne
#:   bestätigendes Geburtsdatum),
#: * ``exact_household_name`` — Haushaltsname, der genau übereinstimmt und im
#:   Bestand nur einmal vorkommt,
#: * ``apartment_unit`` — der Namenstreffer wohnt zusätzlich in der Wohnung, die
#:   die Zeile nennt (die Wohnung **bestätigt** den Treffer).
#:
#: Bewusst über die **Art** entschieden und nicht über ``confidence``: Ein
#: unscharfer Namensvergleich erreicht leicht einen Wert von 0.9 und mehr; eine
#: reine Zahlenschwelle würde ihn deshalb zu einem sicheren Treffer machen.
#:
#: Nicht darin: ``apartment_occupant`` — in der genannten Wohnung wohnt jemand,
#: dessen Name nicht zur Zeile passt. Das ist ein Hinweis, keine Zuordnung: Bei
#: einer erfüllten Bewerbung ist der Bewerber ausgezogen und die Wohnung
#: längst neu belegt.
CERTAIN_MATCH_TYPES = frozenset({
    "exact_member_nr", "exact_name_dob", "exact_household_name", "apartment_unit",
})


class MatchResult(BaseModel):
    """Vorschlag, welchem bestehenden Datensatz eine Importzeile entspricht.

    ``is_certain`` ist die einzige Grundlage dafür, ob ein Import-Assistent eine
    Zuordnung **vorauswählen** darf: nur ein eindeutiger Treffer (siehe
    :data:`CERTAIN_MATCH_TYPES`). Ein **ähnlicher** Name bleibt dagegen ein
    Vorschlag, über den ein Mensch entscheidet. Das Feld wird zentral berechnet,
    damit keine der vier Treffer-Quellen es vergessen kann.
    """
    type: str
    matched_household_id: Optional[int] = None
    matched_household_name: Optional[str] = None
    confidence: float = 0.0
    is_certain: bool = False
    fuzzy_candidates: List[FuzzyCandidate] = []

    @model_validator(mode="after")
    def _derive_is_certain(self):
        object.__setattr__(
            self, "is_certain",
            self.matched_household_id is not None and self.type in CERTAIN_MATCH_TYPES,
        )
        return self

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
    #: Wohnungswunsch aus dem Fragebogen -- wird in die Wartepool-Bewerbung geschrieben
    wishes: List[ApplicationWish] = []
    unparsed_wishes: List[str] = []
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
    missing_base_data_warning: bool = False
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
    updated: int
    skipped: int
    skipped_no_match: int = 0

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
    missing_base_data_warning: bool = False
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
    skipped: int
    skipped_no_match: int = 0

# --- Bewerbungslisten-Import Schemas ---
class ApplicationPersonCandidate(BaseModel):
    """Vorhandene Person ohne Haushalt, die zum Namen der Zeile passt."""
    person_id: int
    name: str
    member_number: Optional[str] = None
    score: float = 0.0

class ApplicationImportPreview(BaseModel):
    temp_id: str
    row: int
    raw_household: str                              # Spalte "Haushalt"
    kind: str                                       # wartepool | wechselwunsch | joker
    raw_kind: Optional[str] = None
    requested_at: Optional[str] = None              # "Mail / Info von"
    wishes: List[ApplicationWish] = []
    #: Teile der Wunsch-Zelle, die der Parser nicht auflösen konnte
    unparsed_wishes: List[str] = []
    status: str = "offen"
    raw_status: Optional[str] = None
    note: Optional[str] = None
    #: Nur zum Abgleich im Assistenten -- wird nicht gespeichert
    raw_current_type: Optional[str] = None
    raw_current_unit: Optional[str] = None
    raw_new_unit: Optional[str] = None
    match_result: MatchResult
    #: Der Haushalt wohnt laut Tool in einer anderen Wohnung als die Liste nennt
    apartment_mismatch: bool = False
    #: Wohnungsnummer der Liste existiert nicht in den Stammdaten
    unknown_apartment: bool = False
    #: Es gibt bereits eine offene Bewerbung dieser Art -- "Aktualisieren" möglich
    existing_application_id: Optional[int] = None
    #: Vorschlag für "Haushalt neu anlegen": passende Personen ohne Haushalt
    person_candidates: List[ApplicationPersonCandidate] = []
    suggested_household_name: str = ""

class ApplicationAnalysisResponse(BaseModel):
    session_id: str
    total_rows: int
    skipped_empty: int = 0
    households: List[ApplicationImportPreview] = []

class ApplicationDecision(BaseModel):
    temp_id: str
    #: "update" | "create" (bestehender Haushalt) | "create_household" | "skip"
    action: str
    target_household_id: Optional[int] = None
    #: Nur bei "create_household": Name und die zuzuordnenden Personen ohne Haushalt
    household_name: Optional[str] = None
    person_ids: List[int] = []

class ApplicationCommitRequest(BaseModel):
    session_id: str
    decisions: List[ApplicationDecision]

class ApplicationCommitResponse(BaseModel):
    applications_created: int = 0
    applications_updated: int = 0
    households_created: int = 0
    persons_assigned: int = 0
    skipped: int = 0
    skipped_no_match: int = 0
    created_household_ids: List[int] = []

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
    persons_without_household: int = 0
    created_household_ids: List[int] = []


# --- Punkteaufschlüsselung (Transparenz des Scorings) ---
class ScoreTerm(BaseModel):
    """Eine Gruppe eines Zielwert-Kriteriums: (Ziel − Ist) × Personen × Faktor."""
    group: str
    label: str
    persons: List[str] = []
    count: int
    target: float
    resident_count: Optional[int] = None   # Bewohner-Personen der Gruppe
    resident_basis: Optional[int] = None   # Bewohner-Personen mit Angabe (Bezugsgröße)
    current: float                         # Ist-Anteil = resident_count / resident_basis
    gap: float                             # target − current
    applies: bool                          # nur bei Ist < Ziel gibt es Punkte
    relative_gap: float                    # Beitrag je Person: (Ziel − Ist) / Ziel, 0–1
    value: float                           # relative_gap × count

class IgnoredPerson(BaseModel):
    name: str
    reason: str

class MembershipPerson(BaseModel):
    """Beitrag einer Person zur Mitgliedsdauer: min(Jahre; Maximum) / Maximum."""
    person_name: str
    member_since: datetime
    years: float
    capped_years: float                    # min(years, max_years)
    value: float                           # capped_years / max_years, 0–1

class MembershipInputs(BaseModel):
    reference_date: datetime
    max_years: float
    persons: List[MembershipPerson] = []

class ScoreCriterion(BaseModel):
    key: str
    category: str
    label: str
    kind: str                      # target | membership | manual
    manual: bool
    field: Optional[str] = None    # Haushaltsfeld der manuellen Bewertung
    weight: float
    value: Optional[float] = None  # Erfüllungsgrad (manuell)
    subscore: float
    points: float                  # subscore × weight
    terms: List[ScoreTerm] = []
    ignored_persons: List[IgnoredPerson] = []
    membership: Optional[MembershipInputs] = None

class OccupancyExplanation(BaseModel):
    size_rooms: Optional[int] = None
    members: int
    fulfilled: float
    weight: float
    points: float

class HouseholdBreakdown(BaseModel):
    household_id: int
    name: str
    member_count: int
    calculated_at: datetime        # Stichtag, zu dem die Aufschlüsselung rechnet
    score_calculated_at: Optional[datetime] = None  # Stichtag der gespeicherten Punktzahl (None = nie berechnet)
    base_score: float              # zum Stichtag berechnet
    stored_score: float            # Household.total_score (Stand der letzten Berechnung)
    is_stale: bool
    criteria: List[ScoreCriterion]
    occupancy: Optional[OccupancyExplanation] = None
    total_score: float             # base_score + Wohnraumausnutzung (falls Zimmerzahl gewählt)

class BreakdownTarget(BaseModel):
    household_id: int
    #: Zimmerzahl der Kategorie; ohne Angabe keine Wohnraumausnutzung.
    size_rooms: Optional[int] = None
    #: True, wenn eine Kategorie gewählt ist -- auch "ohne Zimmerangabe" (size_rooms = None).
    with_occupancy: bool = False

class ManualOverride(BaseModel):
    """Simulierte manuelle Bewertung (0–1) für den Vergleich; fehlende Felder bleiben unverändert."""
    engagement_score: Optional[float] = None
    cultural_diversity_score: Optional[float] = None
    special_needs_score: Optional[float] = None

class BreakdownRequest(BaseModel):
    targets: List[BreakdownTarget]

class BreakdownExportRequest(BreakdownRequest):
    #: household_id → simulierte Werte
    overrides: Dict[int, ManualOverride] = {}

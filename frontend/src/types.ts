export interface Person {
    id: number;
    household_id?: number;
    first_name: string;
    last_name: string;
    birth_date?: string;
    gender?: string;
    occupation_type?: string;
    education_level?: string;
    cultural_background?: string;
    special_needs?: string;
    member_number?: string;
    member_since?: string;
    individual_import_timestamp?: string;
    vcf_import_timestamp?: string;
    updated_at?: string;
    archived: boolean;
}

export interface PersonWithHousehold extends Person {
    household_name?: string;
}

export interface Household {
    id: number;
    name: string;
    engagement_score: number;
    cultural_diversity_score: number;
    special_needs_score: number;
    is_resident: boolean;
    total_score: number;
    people: Person[];
    wbs_status?: string;
    pets_count: number;
    pets_info?: string;
    wheelchair_accessible: boolean;
    financial_status?: string;
    import_source?: string;
    import_timestamp?: string;
    updated_at?: string;
    household_member_count?: number;
    apartment_unit?: string;
    vcf_import_timestamp?: string;
    archived: boolean;
    assigned_apartment_unit?: string;
}

export interface Apartment {
    id: number;
    unit_number: string;
    size_rooms?: number | null;
    apartment_category?: string;
    /** Wohnung fällt für ihre Zimmerzahl klein aus (z. B. ehemalige "Mini WG"). */
    is_small: boolean;
    area_shares?: number;
    area_rent?: number;
    area_utilities?: number;
    funding_type: string;
    min_occupants?: number;
    household_id?: number | null;
    household_name?: string | null;
}

export interface ScoringConfig {
    key: string;
    value: number;
    description?: string;
}

export interface RankedHousehold {
    rank: number;
    id: number;
    name: string;
    member_count: number;
    engagement_score: number;
    /** Haushaltseigene Kriterien, unabhängig von der Wohnung. */
    base_score: number;
    /** Wohnraumausnutzung für die Zimmerzahl dieser Kategorie (null = keine Größe gewählt). */
    occupancy_score: number | null;
    /** base_score + occupancy_score */
    total_score: number;
    /** Steht nur hier, weil der Haushalt die Kategorie ausdrücklich wünscht. */
    by_wish_only?: boolean;
    special_case?: boolean;
    special_case_note?: string;
    requested_at?: string;
    /** Gespeicherte Grundpunktzahl weicht von der aktuellen Berechnung ab. */
    is_stale?: boolean;
    /** Kategorie, aus der die Zeile stammt (für die Wohnraumausnutzung in der Aufschlüsselung). */
    size_rooms?: number | null;
    funding_type?: string | null;
}

// --- Punkteaufschlüsselung ---

/** Eine Gruppe eines Zielwert-Kriteriums: (Ziel − Ist) × Personen × Faktor. */
export interface ScoreTerm {
    group: string;
    label: string;
    persons: string[];
    count: number;
    target: number;
    resident_count?: number | null;
    resident_basis?: number | null;
    current: number;
    gap: number;
    /** Nur bei Ist < Ziel gibt es Punkte. */
    applies: boolean;
    /** Beitrag je Person: (Ziel − Ist) / Ziel, 0–1. */
    relative_gap: number;
    /** relative_gap × count */
    value: number;
}

/** Beitrag einer Person zur Mitgliedsdauer: min(Jahre; Maximum) / Maximum. */
export interface MembershipPerson {
    person_name: string;
    member_since: string;
    years: number;
    /** min(years, max_years) */
    capped_years: number;
    /** capped_years / max_years, 0–1 */
    value: number;
}

export interface MembershipInputs {
    reference_date: string;
    max_years: number;
    persons: MembershipPerson[];
}

export type ManualScoreField = 'engagement_score' | 'cultural_diversity_score' | 'special_needs_score';

export interface ScoreCriterion {
    key: string;
    category: string;
    label: string;
    kind: 'target' | 'membership' | 'manual';
    manual: boolean;
    field?: ManualScoreField | null;
    weight: number;
    value?: number | null;
    subscore: number;
    points: number;
    terms: ScoreTerm[];
    ignored_persons: { name: string; reason: string }[];
    membership?: MembershipInputs | null;
}

export interface OccupancyExplanation {
    size_rooms: number | null;
    members: number;
    fulfilled: number;
    weight: number;
    points: number;
}

export interface HouseholdBreakdown {
    household_id: number;
    name: string;
    member_count: number;
    /** Stichtag, zu dem die Aufschlüsselung rechnet (= letzte Berechnung, sonst heute). */
    calculated_at: string;
    /** Stichtag der gespeicherten Punktzahl; null = noch nie berechnet. */
    score_calculated_at?: string | null;
    base_score: number;
    stored_score: number;
    is_stale: boolean;
    criteria: ScoreCriterion[];
    occupancy?: OccupancyExplanation | null;
    total_score: number;
}

/** Haushalt samt Kategorie-Kontext: mit Kategorie kommt die Wohnraumausnutzung hinzu. */
export interface BreakdownTarget {
    household_id: number;
    size_rooms?: number | null;
    with_occupancy?: boolean;
}

export type ManualOverrides = Record<number, Partial<Record<ManualScoreField, number>>>;

/** Ein Wechselwunsch in einer Kategorie: Vorrang nach Datum, ohne Scoring. */
export interface PriorityEntry {
    rank: number;
    id: number;
    name: string;
    member_count: number;
    requested_at?: string;
    current_apartment_unit?: string;
    special_case?: boolean;
    special_case_note?: string;
}

export interface RankingGroup {
    size_rooms: number | null;
    funding_type: string;
    priority: PriorityEntry[];
    households: RankedHousehold[];
}

// --- Bewerbungen ---

export type ApplicationKind = 'wartepool' | 'wechselwunsch' | 'joker';
export type ApplicationStatus = 'offen' | 'erfuellt' | 'zurueckgezogen';

export const APPLICATION_KIND_LABELS: Record<ApplicationKind, string> = {
    wartepool: 'Wartepool',
    wechselwunsch: 'Wechselwunsch',
    joker: 'Joker',
};

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
    offen: 'offen',
    erfuellt: 'erfüllt',
    zurueckgezogen: 'zurückgezogen',
};

/**
 * Eine gewünschte Wohnungskategorie. `null` heißt in jedem Feld "egal".
 * Die Zimmerzahl ist die ganze Zahl des Modells: 2 steht für "2,5".
 */
export interface ApplicationWish {
    size_rooms?: number | null;
    funding_type?: string | null;
    apartment_category?: string | null;
}

export interface Application {
    id: number;
    household_id: number;
    kind: ApplicationKind;
    requested_at?: string | null;
    wishes: ApplicationWish[];
    status: ApplicationStatus;
    status_note?: string | null;
    special_case: boolean;
    special_case_note?: string | null;
    note?: string | null;
    fulfilled_apartment_id?: number | null;
    fulfilled_at?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
    archived: boolean;
    household_name?: string | null;
    member_count: number;
    is_resident: boolean;
    wbs_status?: string | null;
    current_apartment_unit?: string | null;
    fulfilled_apartment_unit?: string | null;
}

/** Wählbare Wunschkategorie, abgeleitet aus den Wohnungsstammdaten. */
export interface ApartmentCategory {
    size_rooms?: number | null;
    funding_type?: string | null;
    apartment_category?: string | null;
    label: string;
    apartment_count: number;
}

export interface JokerWaitEntry {
    rank: number;
    application_id: number;
    household_id: number;
    household_name: string;
    requested_at?: string;
    current_apartment_unit?: string;
    special_case?: boolean;
    special_case_note?: string;
}

// --- Import Types ---

/** Person des Datenbestands, die einer neu anzulegenden ähnlich ist. */
export interface SimilarPerson {
    name: string;
    household?: string;
    reason: 'member_number' | 'same_name' | 'birth_date';
}

/** Eine Mitgliedsnummer aus einem Import, die nicht gespeichert wurde. */
export interface MemberNumberConflict {
    person: string;
    member_number: string;
    /** Wer die Nummer schon trägt. */
    holder: string;
}

export interface ImportPersonPreview {
    name: string;
    /** Vor- und Nachname so, wie sie gespeichert würden. */
    first_name?: string;
    last_name?: string;
    member_number?: string;
    birth_date?: string;
    /** Was mit der Person geschieht, bezogen auf den vorgeschlagenen Haushalt. */
    status: 'in_household' | 'assign' | 'other_household' | 'new';
    /** Bei `other_household`: der Haushalt, in dem die Person bleibt. */
    other_household?: string;
    /** Bei `new`: ähnliche Personen im Datenbestand. */
    similar: SimilarPerson[];
    /** Wer die Mitgliedsnummer schon trägt; sie wird dann nicht gespeichert. */
    member_number_holder?: string;
}

export interface FuzzyCandidate {
    household_id: number;
    name: string;
    score: number;
    member_numbers: string[];
}

export interface MatchResult {
    type: string;
    matched_household_id?: number;
    matched_household_name?: string;
    confidence: number;
    /**
     * Eindeutiger Treffer (Mitgliedsnummer oder gleicher Name).
     * Nur dann darf ein Assistent die Zuordnung vorauswählen — siehe
     * `components/import/matching.ts`.
     */
    is_certain: boolean;
    fuzzy_candidates: FuzzyCandidate[];
}

export interface DataChange {
    field: string;
    old_value?: string;
    new_value?: string;
}

export interface ExistingDataChanges {
    fields_to_overwrite: DataChange[];
    data_removals: DataChange[];
}

export interface HouseholdImportPreview {
    temp_id: string;
    timestamp: string;
    wbs_status?: string;
    financial_status?: string;
    declared_member_count: number;
    wheelchair_accessible: boolean;
    /** Wohnungswunsch aus dem Fragebogen -- landet in der Wartepool-Bewerbung. */
    wishes: ApplicationWish[];
    unparsed_wishes: string[];
    pets_count: number;
    pets_info?: string;
    persons: ImportPersonPreview[];
    match_result: MatchResult;
    member_count_mismatch: boolean;
    already_imported: boolean;
    existing_data_changes?: ExistingDataChanges;
    /** Der vorgeschlagene Haushalt ist ein Bewohner-Haushalt: sein Wunsch wird nicht übernommen. */
    wish_not_applied: boolean;
    /** Name, den ein neu angelegter Haushalt bekäme. */
    suggested_household_name: string;
    /** Was mit jeder Person geschähe, wenn der Bogen einen neuen Haushalt anlegt. */
    persons_if_created: ImportPersonPreview[];
    /** Mindestens eine Person käme in den neuen Haushalt; sonst ist „Neu anlegen“ nicht zulässig. */
    create_allowed: boolean;
    /** Keine Person des Bogens nennt eine Mitgliedsnummer. */
    no_member_number: boolean;
}

export interface PrivacyWarning {
    row: number;
    name: string;
}

export interface HHAnalysisResponse {
    session_id: string;
    total_rows: number;
    skipped_not_submitted: number;
    skipped_duplicates: number;
    privacy_warnings: PrivacyWarning[];
    households: HouseholdImportPreview[];
}

export interface HouseholdDecision {
    temp_id: string;
    /** `create` legt einen neuen Haushalt an; nie vorausgewählt. */
    action: 'update' | 'skip' | 'create';
    target_household_id?: number;
    confirm_data_removals: boolean;
}

export interface HHCommitRequest {
    session_id: string;
    decisions: HouseholdDecision[];
}

export interface HHCommitResponse {
    updated: number;
    skipped: number;
    /** „Aktualisieren“ ohne zugeordneten Haushalt. */
    skipped_no_match: number;
    /** Namen der Bewohner-Haushalte, deren Wunsch nicht übernommen wurde. */
    wishes_not_applied: string[];
    households_created: number;
    applications_created: number;
    persons_created: number;
    /** Personen, die ohne Haushalt im Datenbestand standen und zugeordnet wurden. */
    persons_assigned: number;
    /** Personen, die in ihrem bisherigen Haushalt bleiben. */
    persons_not_taken_over: { person: string; household: string }[];
    member_numbers_not_stored: MemberNumberConflict[];
    /** Neu angelegte Personen, zu denen es ähnliche im Datenbestand gibt. */
    similar_persons: { person: string; similar: SimilarPerson[] }[];
}

export interface IndividualImportPreview {
    temp_id: string;
    name: string;
    first_name: string;
    last_name: string;
    birth_date?: string;
    member_number?: string;
    member_since?: string;
    /** Wert der Spalte „Mitglied seit“, der nicht als Datum angenommen wurde. */
    member_since_rejected?: string;
    /** Eine andere Person trägt die Mitgliedsnummer schon; sie wird nicht ergänzt. */
    member_number_holder?: string;
    timestamp: string;
    gender?: string;
    occupation?: string;
    education?: string;
    life_situation?: string;
    social_diversity?: string;
    match_result: MatchResult;
    already_imported: boolean;
    is_older: boolean;
    existing_data_changes?: ExistingDataChanges;
}

export interface IndividualAnalysisResponse {
    session_id: string;
    total_rows: number;
    skipped_not_submitted: number;
    skipped_duplicates: number;
    privacy_warnings: PrivacyWarning[];
    individuals: IndividualImportPreview[];
}

export interface IndividualDecision {
    temp_id: string;
    action: 'update' | 'skip';
    target_person_id?: number;
    confirm_data_removals: boolean;
}

export interface IndividualCommitRequest {
    session_id: string;
    decisions: IndividualDecision[];
}

export interface IndividualCommitResponse {
    updated: number;
    skipped: number;
    /** Ohne zugeordnete Person - der Import legt keine Personen an. */
    skipped_no_match: number;
    member_numbers_not_stored: MemberNumberConflict[];
}

// --- Mitgliederliste (vCard) ---

/** Leere Angaben, die die Mitgliederliste füllt. */
export interface MemberListFills {
    /** Personen, bei denen mindestens eine Angabe gefüllt wird. */
    persons: number;
    birth_date: number;
    member_since: number;
    member_number: number;
    gender: number;
}

/** „Mitglied seit“ der Mitgliederliste weicht vom gespeicherten Wert ab (nur Anzeige). */
export interface MemberSinceDeviation {
    person: string;
    household?: string;
    stored: string;
    member_list: string;
    days: number;
}

export interface VcfAnalysisResponse {
    session_id: string;
    total_cards: number;
    skipped_no_name: number;
    /** Karten ohne sicheren Treffer; sie bewirken nichts. */
    unmatched_cards: number;
    fills: MemberListFills;
    /** Größte Abweichung zuerst. */
    member_since_deviations: MemberSinceDeviation[];
    member_numbers_not_stored: MemberNumberConflict[];
}

export interface VcfCommitRequest {
    session_id: string;
}

export interface VcfCommitResponse {
    fills: MemberListFills;
    unmatched_cards: number;
}

// --- Ist-Statistik ---

export interface StatisticsGroup {
    key: string;
    label: string;
    /** Absolute Zahl. */
    count: number;
    /** Anteil an der Bezugsgröße der Kategorie (0..1). */
    ratio: number;
    /** Zielwert als Anteil, sofern konfiguriert. */
    target_ratio?: number | null;
    /** Zielwert absolut (target_ratio × total). */
    target_count?: number | null;
}

export interface StatisticsCategory {
    key: string;
    label: string;
    /** Bezugsgröße der Anteile: Personen oder Haushalte. */
    basis: 'person' | 'household';
    /** Bezugsgröße — nur Datensätze mit Angabe. */
    total: number;
    /** Datensätze ohne Angabe: ignoriert, weder Ausprägung noch Bezugsgröße. */
    unknown_count: number;
    /** Ausprägungen außerhalb der Bezugsgröße, nur nachrichtlich (z. B. „unter 20"). */
    excluded_groups: StatisticsExcludedGroup[];
    groups: StatisticsGroup[];
}

export interface StatisticsExcludedGroup {
    key: string;
    label: string;
    count: number;
}

export interface ResidentStatistics {
    household_count: number;
    person_count: number;
    /** Personen mit mindestens einer fehlenden Angabe. */
    incomplete_person_count: number;
    categories: StatisticsCategory[];
}

/** Personenbezogene Merkmale der Ist-Statistik. */
export type StatisticsDimension = 'age' | 'gender' | 'occupation' | 'education';

export interface MissingValue {
    dimension: StatisticsDimension;
    /** empty = Feld leer, category_0 = Kategorie 0 (bewusst keine Zuordnung), unrecognized = Wert nicht erkannt. */
    reason: 'empty' | 'category_0' | 'unrecognized';
    /** Gespeicherter Wert, sofern vorhanden. */
    raw_value?: string | null;
    /** Nicht erkannter Wert oder leer trotz Individualbogen-Import. */
    suspected_import_error: boolean;
}

/** Bewohner-Person mit fehlenden Angaben — Eintrag der Prüfliste. */
export interface PersonMissingData {
    person_id: number;
    first_name?: string | null;
    last_name?: string | null;
    member_number?: string | null;
    household_id: number;
    household_name?: string | null;
    apartment_unit?: string | null;
    age?: number | null;
    individual_import_timestamp?: string | null;
    missing: MissingValue[];
}

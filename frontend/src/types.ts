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
    desired_apartment_size?: string;
    desired_apartment_type?: string[];
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
}

export interface RankingGroup {
    size_rooms: number | null;
    funding_type: string;
    households: RankedHousehold[];
}

// --- Import Types ---

export interface ImportPersonPreview {
    name: string;
    first_name?: string;
    last_name?: string;
    member_number?: string;
    birth_date?: string;
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
    desired_apartment_type?: string[];
    desired_apartment_size?: string;
    pets_count: number;
    pets_info?: string;
    persons: ImportPersonPreview[];
    match_result: MatchResult;
    member_count_mismatch: boolean;
    already_imported: boolean;
    existing_data_changes?: ExistingDataChanges;
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
    /** Es existieren noch keine Haushalte - bitte zuerst die vCard importieren. */
    missing_base_data_warning: boolean;
    households: HouseholdImportPreview[];
}

export interface HouseholdDecision {
    temp_id: string;
    action: 'update' | 'skip';
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
    /** Ohne zugeordneten Haushalt - der Import legt keine Haushalte an. */
    skipped_no_match: number;
}

export interface IndividualImportPreview {
    temp_id: string;
    name: string;
    first_name: string;
    last_name: string;
    birth_date?: string;
    member_number?: string;
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
    /** Es existieren noch keine Personen - bitte zuerst die vCard importieren. */
    missing_base_data_warning: boolean;
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
}

// --- VCF-Import Types ---

export interface VcfPersonPreview {
    temp_id: string;
    name: string;
    first_name: string;
    last_name: string;
    birth_date?: string;
    gender?: string;
    member_number?: string;
    member_since?: string;
    apartment_unit?: string;
    role: 'member' | 'partner' | 'child';
    source: 'vcard' | 'note';
    mentioned_by?: string;
}

export interface VcfHouseholdPreview {
    temp_id: string;
    name: string;
    apartment_unit?: string;
    address?: string;
    is_resident: boolean;
    timestamp?: string;
    persons: VcfPersonPreview[];
    match_result: MatchResult;
    already_imported: boolean;
    warnings: string[];
    existing_data_changes?: ExistingDataChanges;
}

export interface VcfAnalysisResponse {
    session_id: string;
    total_cards: number;
    skipped_no_name: number;
    total_persons: number;
    resident_households: number;
    households: VcfHouseholdPreview[];
}

export interface VcfDecision {
    temp_id: string;
    action: 'create' | 'update' | 'skip';
    target_household_id?: number;
    excluded_person_temp_ids: string[];
}

export interface VcfCommitRequest {
    session_id: string;
    decisions: VcfDecision[];
}

export interface VcfCommitResponse {
    households_created: number;
    households_updated: number;
    households_skipped: number;
    persons_created: number;
    persons_updated: number;
    persons_assigned: number;
    /** Neu angelegte Personen ohne Haushalt (keine Wohnungszuordnung). */
    persons_without_household: number;
    created_household_ids: number[];
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

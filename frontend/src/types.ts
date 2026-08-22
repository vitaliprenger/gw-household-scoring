export interface Person {
    id: number;
    first_name: string;
    last_name: string;
    birth_date: string;
    gender: string;
    occupation_type: string;
    education_level: string;
    cultural_background?: string;
    special_needs: boolean;
}

export interface Household {
    id: number;
    name: string;
    member_since?: string;
    engagement_score: float;
    is_resident: boolean;
    total_score: float;
    people: Person[];
}

export interface ScoringConfig {
    key: string;
    value: float;
    description?: string;
}

export interface RankedHousehold {
    rank: number;
    id: number;
    name: string;
    member_count: number;
    engagement_score: number;
    total_score: number;
    people: Person[];
}

export interface RankingGroup {
    size_rooms: number;
    funding_type: string;
    households: RankedHousehold[];
}

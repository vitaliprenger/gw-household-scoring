import { ApartmentCategory, ApplicationWish } from '../../types';

/**
 * Anzeige der Wünsche in der Schreibweise der gepflegten Liste.
 *
 * Das halbe Zimmer entfällt im Modell (`3,5` wird als `size_rooms = 3`
 * gespeichert); angezeigt wird es weiterhin, damit die Kommission ihre
 * gewohnten Bezeichner sieht. Spiegelt `backend/wishes.py`.
 */

export const CATEGORY_CLUSTER = 'Clusterwohnung';
export const CATEGORY_JOKER = 'Joker';

export function sizeLabel(sizeRooms?: number | null): string {
    if (sizeRooms === null || sizeRooms === undefined || sizeRooms <= 0) {
        return 'ohne Zimmerangabe';
    }
    return `${sizeRooms},5`;
}

export function fundingShort(fundingType?: string | null): string {
    if (fundingType === 'WBS A') return 'A';
    if (fundingType === 'WBS B') return 'B';
    if (fundingType === 'freifinanziert') return 'frei';
    return '';
}

export function wishLabel(wish: ApplicationWish): string {
    const parts: string[] = [];
    if (wish.size_rooms !== null && wish.size_rooms !== undefined) {
        parts.push(sizeLabel(wish.size_rooms));
    }
    if (wish.apartment_category) {
        parts.push(wish.apartment_category === CATEGORY_CLUSTER ? 'Cluster' : wish.apartment_category);
    }
    const short = fundingShort(wish.funding_type);
    if (short) parts.push(short);
    return parts.length ? parts.join(' ') : 'beliebig';
}

/** Stabiler Schlüssel einer Wunschkategorie — dient als Wert der Auswahlliste. */
export function wishKey(wish: ApplicationWish): string {
    return [
        wish.size_rooms ?? '',
        wish.funding_type ?? '',
        wish.apartment_category ?? '',
    ].join('|');
}

export function categoryToWish(category: ApartmentCategory): ApplicationWish {
    return {
        size_rooms: category.size_rooms ?? null,
        funding_type: category.funding_type ?? null,
        apartment_category: category.apartment_category ?? null,
    };
}

/** Wunschkategorien aus Schlüsseln zurückbauen (Auswahlliste -> Speicherform). */
export function wishesFromKeys(keys: string[], categories: ApartmentCategory[]): ApplicationWish[] {
    const byKey = new Map(categories.map((c) => [wishKey(categoryToWish(c)), categoryToWish(c)]));
    return keys.map((k) => byKey.get(k)).filter((w): w is ApplicationWish => !!w);
}

/** Datum ohne Uhrzeit, wie die Liste es führt. */
export function formatDate(value?: string | null): string {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('de-DE');
}

/** Wert für ein `<input type="date">`. */
export function toDateInput(value?: string | null): string {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toISOString().slice(0, 10);
}

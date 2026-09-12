import { MatchResult } from '../../types';

/**
 * Regel für alle Import-Assistenten: **nur ein eindeutiger Treffer wird
 * automatisch zugeordnet.**
 *
 * Eindeutig sind die Mitgliedsnummer, ein exakt übereinstimmender Name (mit
 * oder ohne bestätigendes Geburtsdatum) und die Wohnungsnummer. Ein nur
 * *ähnlicher* Name bleibt ein Vorschlag: Er ist im Assistenten sichtbar und
 * auswählbar, wird aber nie vorausgewählt. Maßgeblich ist
 * `MatchResult.is_certain` aus dem Backend (`schemas.CERTAIN_MATCH_TYPES`),
 * damit Backend und Frontend dieselbe Grenze ziehen — und zwar über die
 * Treffer-Art statt über den Prozentwert, den auch ein unscharfer Vergleich
 * hoch treiben kann.
 */
export function isCertainMatch(match: MatchResult | undefined | null): boolean {
    return !!match?.is_certain;
}

/** Ein Vorschlag liegt vor, ist aber nicht sicher — hier muss ein Mensch entscheiden. */
export function isUncertainMatch(match: MatchResult | undefined | null): boolean {
    return !!match?.matched_household_id && !match.is_certain;
}

/**
 * Aktionswert für eine Zeile, über die noch nicht entschieden wurde.
 *
 * Nötig überall, wo die Alternative zur Zuordnung selbst Daten erzeugen würde
 * (vCard: neuer Haushalt, Bewerbungsliste: neuer Haushalt). Dort wäre weder
 * „zuordnen" noch „neu anlegen" eine unschuldige Vorbelegung — die Zeile
 * braucht eine ausdrückliche Entscheidung, und der Import bleibt bis dahin
 * gesperrt. Die Fragebogen-Importe legen nichts an; dort genügt
 * „Überspringen" als Vorbelegung.
 *
 * Die Commit-Endpunkte behandeln jede unbekannte Aktion wie „Überspringen",
 * damit dieser Wert auch versehentlich nichts bewirken kann.
 */
export const UNDECIDED = 'undecided';

export const UNDECIDED_LABEL = 'Bitte entscheiden';

/** Kurzer Hinweis, warum eine Zeile eine Entscheidung braucht. */
export function uncertainMatchHint(match: MatchResult): string {
    const name = match.matched_household_name ?? '?';
    if (match.type === 'apartment_occupant') {
        // Der Name der Zeile passt zu niemandem; gefunden wurde nur, wer heute
        // in der genannten Wohnung wohnt. Bei erfüllten Bewerbungen ist der
        // Bewerber längst ausgezogen — das ist ein Hinweis, keine Zuordnung.
        return `In der genannten Wohnung wohnt heute „${name}" — der Name der Zeile `
            + 'passt zu keinem Haushalt. Bei einer erfüllten Bewerbung ist der Bewerber '
            + 'längst ausgezogen. Bitte Zuordnung prüfen.';
    }
    const percent = Math.round((match.confidence ?? 0) * 100);
    return `„${name}" ist nur ein ähnlicher Treffer (${percent} %) — automatisch `
        + 'zugeordnet wird nur bei Mitgliedsnummer, exaktem Namen oder bestätigender '
        + 'Wohnungsnummer. Bitte Zuordnung prüfen.';
}

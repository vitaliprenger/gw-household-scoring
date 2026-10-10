import { MatchResult } from '../../types';

/**
 * Regel für alle Import-Assistenten: **nur ein eindeutiger Treffer wird
 * automatisch zugeordnet.**
 *
 * Eindeutig sind die Mitgliedsnummer und ein exakt übereinstimmender Name (mit
 * oder ohne bestätigendes Geburtsdatum). Ein nur
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
 * Nötig, wo die Vorbelegung einer unsicheren Zeile selbst Daten erzeugen
 * würde (vCard: neuer Haushalt). Dort wäre weder
 * „zuordnen" noch „neu anlegen" eine unschuldige Vorbelegung — die Zeile
 * braucht eine ausdrückliche Entscheidung, und der Import bleibt bis dahin
 * gesperrt. Die Fragebogen-Importe belegen unsichere Zeilen mit
 * „Überspringen" vor; „Neu anlegen" im Haushaltsbogen ist immer eine bewusste
 * Wahl je Zeile (ADR 0011), deshalb sperren sie nicht.
 *
 * Die Commit-Endpunkte behandeln jede unbekannte Aktion wie „Überspringen",
 * damit dieser Wert auch versehentlich nichts bewirken kann.
 */
export const UNDECIDED = 'undecided';

export const UNDECIDED_LABEL = 'Bitte entscheiden';

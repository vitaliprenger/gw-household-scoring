import { MembershipPerson, ScoreCriterion, ScoreTerm, OccupancyExplanation } from '../../types';

/** Zahl mit fester Nachkommazahl, deutsch formatiert. */
export const num = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined
    ? '—'
    : value.toLocaleString('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** Anteil als Dezimalzahl (0,1753) — so, wie er in die Formel eingeht. */
export const ratio = (value: number): string => num(value, 4);

export const points = (value: number): string => num(value, 2);

/** Faktoren und Gewichte ohne überflüssige Nachkommastellen (2 statt 2,00). */
export const plain = (value: number | null | undefined): string =>
  value === null || value === undefined
    ? '—'
    : value.toLocaleString('de-DE', { maximumFractionDigits: 4 });

/** Rechenweg eines Terms: (Ziel − Ist) / Ziel je Person × Personen = Wert. */
export const termFormula = (term: ScoreTerm): string => {
  const current = term.resident_basis
    ? `${ratio(term.current)} (${term.resident_count}/${term.resident_basis})`
    : ratio(term.current);
  if (!term.applies) {
    return `Ist ${current} ≥ Ziel ${ratio(term.target)} → 0`;
  }
  return `(${ratio(term.target)} − ${current}) / ${ratio(term.target)} = ${num(term.relative_gap, 3)}`
    + ` × ${term.count} Pers. = ${num(term.value, 3)}`;
};

/** Rechenweg eines Kriteriums bis zu den Punkten. */
export const criterionFormula = (c: ScoreCriterion): string => {
  switch (c.kind) {
    case 'target':
      return `Σ Gruppen ${num(c.subscore, 3)} × Gewicht ${plain(c.weight)} = ${points(c.points)}`;
    case 'membership': {
      const persons = c.membership?.persons ?? [];
      if (persons.length === 0) return 'kein Eintrittsdatum gepflegt → 0';
      return `Σ ${persons.length} Pers. ${num(c.subscore, 3)} × Gewicht ${plain(c.weight)} = ${points(c.points)}`;
    }
    default:
      return `Erfüllungsgrad ${plain(c.value)} × Gewicht ${plain(c.weight)} = ${points(c.points)}`;
  }
};

/** Rechenweg einer Person: min(Jahre; Maximum) / Maximum = Wert. */
export const membershipFormula = (p: MembershipPerson, maxYears: number): string =>
  `min(${num(p.years, 2)} J.; ${plain(maxYears)}) / ${plain(maxYears)} = ${num(p.value, 3)}`;

export const occupancyFormula = (o: OccupancyExplanation): string =>
  o.size_rooms === null || o.size_rooms === undefined
    ? `ohne Zimmerangabe → erfüllt 1 × Gewicht ${plain(o.weight)} = ${points(o.points)}`
    : `${o.members} Mitglieder ${o.members >= o.size_rooms ? '≥' : '<'} ${o.size_rooms} Zimmer → `
      + `${plain(o.fulfilled)} × Gewicht ${plain(o.weight)} = ${points(o.points)}`;

export const occupancyLabel = (sizeRooms: number | null | undefined): string =>
  sizeRooms === null || sizeRooms === undefined ? 'ohne Zimmerangabe' : `${sizeRooms} Zimmer`;

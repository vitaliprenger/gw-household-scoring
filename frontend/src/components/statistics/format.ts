import { StatisticsGroup } from '../../types';

/** Darstellungsform der Ist-Statistik: absolute Zahlen oder Anteile. */
export type Mode = 'absolute' | 'relative';

export const formatCount = (value: number): string => value.toLocaleString('de-DE');

export const formatDecimal = (value: number): string =>
  value.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const formatPercent = (value: number): string =>
  (value * 100).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' %';

/** Abweichung mit Vorzeichen — negativ heißt: unter dem Zielwert. */
const withSign = (value: number, format: (v: number) => string): string =>
  (value > 0 ? '+' : '') + format(value);

export const hasTarget = (g: StatisticsGroup): boolean =>
  g.target_ratio !== null && g.target_ratio !== undefined;

/** Ist-Wert einer Ausprägung als Anzahl oder Anteil. */
export const formatValue = (g: StatisticsGroup, mode: Mode): string =>
  mode === 'absolute' ? formatCount(g.count) : formatPercent(g.ratio);

export const formatTarget = (g: StatisticsGroup, mode: Mode): string => {
  if (g.target_ratio === null || g.target_ratio === undefined) return '—';
  return mode === 'absolute' ? formatDecimal(g.target_count ?? 0) : formatPercent(g.target_ratio);
};

export const formatDeviation = (g: StatisticsGroup, mode: Mode): string => {
  if (g.target_ratio === null || g.target_ratio === undefined) return '—';
  return mode === 'absolute'
    ? withSign(g.count - (g.target_count ?? 0), formatDecimal)
    : withSign(g.ratio - g.target_ratio, formatPercent);
};

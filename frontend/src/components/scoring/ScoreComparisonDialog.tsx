import { Fragment, useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Link,
  Slider, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
  BreakdownTarget, HouseholdBreakdown, ManualOverrides, ManualScoreField, ScoreCriterion,
} from '../../types';
import { calculateScores, exportScoreBreakdowns, getScoreBreakdowns, updateHousehold } from '../../api';
import ConfirmDialog from '../common/ConfirmDialog';
import { NO_ZEBRA_ROW_CLASS } from '../common/tableStyles';
import { num, plain, points } from './format';

export interface ComparisonEntry {
  target: BreakdownTarget;
  /** Beschriftung der Kategorie, aus der der Haushalt stammt. */
  categoryLabel?: string;
}

interface ScoreComparisonDialogProps {
  open: boolean;
  entries: ComparisonEntry[];
  onClose: () => void;
  /** Nach „Werte übernehmen“: Rangliste neu laden. */
  onApplied: () => void;
  onShowBreakdown: (entry: ComparisonEntry) => void;
}

type Values = Record<number, Partial<Record<ManualScoreField, number>>>;

const SIMULATED_BG = 'rgba(255, 193, 7, 0.18)';

/** Rang je Haushalt (1 = höchste Punktzahl) für eine Punkteliste. */
const ranksOf = (totals: { id: number; total: number }[]): Map<number, number> =>
  new Map([...totals].sort((a, b) => b.total - a.total).map((t, index) => [t.id, index + 1]));

/**
 * Vergleich von 2–5 Haushalten: Punkte je Kriterium nebeneinander. Die manuell
 * bewerteten Kriterien lassen sich durchspielen — Gesamtpunktzahl und Rang
 * innerhalb der Auswahl folgen sofort. Punkte eines manuellen Kriteriums sind
 * linear (Erfüllungsgrad × Gewicht), die Simulation ist deshalb exakt.
 */
export default function ScoreComparisonDialog({
  open, entries, onClose, onApplied, onShowBreakdown,
}: ScoreComparisonDialogProps) {
  const [breakdowns, setBreakdowns] = useState<HouseholdBreakdown[] | null>(null);
  const [values, setValues] = useState<Values>({});
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const targets = entries.map(e => e.target);

  const load = async () => {
    setError(null);
    setBreakdowns(null);
    try {
      const result = await getScoreBreakdowns(targets);
      setBreakdowns(result);
      setValues({});
    } catch {
      setError('Aufschlüsselung konnte nicht geladen werden.');
    }
  };

  useEffect(() => {
    if (open && entries.length > 0) load();
  }, [open, entries]);

  const manualValue = (b: HouseholdBreakdown, c: ScoreCriterion): number =>
    c.field && values[b.household_id]?.[c.field] !== undefined
      ? values[b.household_id][c.field]!
      : c.value ?? 0;

  const isChanged = (b: HouseholdBreakdown, c: ScoreCriterion): boolean =>
    c.manual && Math.abs(manualValue(b, c) - (c.value ?? 0)) > 1e-9;

  const simulatedPoints = (b: HouseholdBreakdown, c: ScoreCriterion): number =>
    c.manual ? manualValue(b, c) * c.weight : c.points;

  const simulatedTotal = (b: HouseholdBreakdown): number =>
    b.total_score + b.criteria.reduce((sum, c) => sum + simulatedPoints(b, c) - c.points, 0);

  const { originalRanks, simulatedRanks, leader } = useMemo(() => {
    const list = breakdowns ?? [];
    const simulated = list.map(b => ({ id: b.household_id, total: simulatedTotal(b) }));
    return {
      originalRanks: ranksOf(list.map(b => ({ id: b.household_id, total: b.total_score }))),
      simulatedRanks: ranksOf(simulated),
      leader: Math.max(...simulated.map(s => s.total), 0),
    };
  }, [breakdowns, values]);

  const setValue = (householdId: number, field: ManualScoreField, raw: number) => {
    const value = Math.min(1, Math.max(0, Number.isFinite(raw) ? raw : 0));
    setValues(prev => ({ ...prev, [householdId]: { ...prev[householdId], [field]: value } }));
  };

  /** Nur tatsächlich geänderte Werte — für Export und Übernahme. */
  const overrides: ManualOverrides = useMemo(() => {
    const result: ManualOverrides = {};
    for (const b of breakdowns ?? []) {
      for (const c of b.criteria) {
        if (c.field && isChanged(b, c)) {
          result[b.household_id] = { ...result[b.household_id], [c.field]: manualValue(b, c) };
        }
      }
    }
    return result;
  }, [breakdowns, values]);
  const hasChanges = Object.keys(overrides).length > 0;

  const handleExport = async () => {
    setBusy(true);
    try {
      await exportScoreBreakdowns(targets, overrides);
    } catch {
      setError('Export fehlgeschlagen.');
    } finally {
      setBusy(false);
    }
  };

  const handleApply = async () => {
    setBusy(true);
    try {
      for (const [id, fields] of Object.entries(overrides)) {
        await updateHousehold(Number(id), fields);
      }
      await calculateScores();
      setConfirmOpen(false);
      await load();
      onApplied();
    } catch {
      setError('Übernehmen fehlgeschlagen.');
    } finally {
      setBusy(false);
    }
  };

  const criteria = breakdowns?.[0]?.criteria ?? [];
  const categories = [...new Set(criteria.map(c => c.category))];
  const anyStale = breakdowns?.some(b => b.is_stale);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
      <DialogTitle>
        Punktevergleich
        <Typography variant="body2" color="textSecondary">
          Manuell bewertete Kriterien lassen sich durchspielen; nichts wird gespeichert, bis „Werte übernehmen“
          bestätigt ist. Gelb = simulierter Wert.
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {anyStale && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Bei mindestens einem Haushalt (⚠) haben sich die Daten seit der letzten Berechnung geändert. Der Vergleich
            zeigt die mit den heutigen Daten berechneten Werte; die Rangliste nutzt bis zur Neuberechnung die gespeicherten.
          </Alert>
        )}
        {!breakdowns && !error && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
        {breakdowns && (
          <TableContainer sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ minWidth: 220 }}>Kriterium</TableCell>
                  <TableCell align="right">Gewicht</TableCell>
                  {breakdowns.map((b, index) => (
                    <TableCell key={b.household_id} align="right" sx={{ minWidth: 190 }}>
                      <Link component="button" onClick={() => onShowBreakdown(entries[index])} sx={{ fontWeight: 'bold' }}>
                        {b.name}
                      </Link>
                      {b.is_stale && (
                        <Tooltip title={`Gespeichert ${points(b.stored_score)}, aktuell ${points(b.base_score)}`}>
                          <WarningAmberIcon color="warning" fontSize="small" sx={{ ml: 0.5, verticalAlign: 'middle' }} />
                        </Tooltip>
                      )}
                      <Typography variant="caption" display="block" color="textSecondary">
                        {b.member_count} Mitgl.{entries[index]?.categoryLabel ? ` · ${entries[index].categoryLabel}` : ''}
                      </Typography>
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {categories.map(category => (
                  <Fragment key={category}>
                    <TableRow className={NO_ZEBRA_ROW_CLASS}>
                      <TableCell colSpan={2 + breakdowns.length} sx={{ bgcolor: 'action.hover', fontWeight: 'bold' }}>
                        {category}
                      </TableCell>
                    </TableRow>
                    {criteria.filter(c => c.category === category).map(c => (
                      <TableRow key={c.key}>
                        <TableCell>{c.label}{c.manual ? ' (manuell)' : ''}</TableCell>
                        <TableCell align="right">{plain(c.weight)}</TableCell>
                        {breakdowns.map(b => {
                          const own = b.criteria.find(x => x.key === c.key)!;
                          if (!own.manual || !own.field) {
                            return <TableCell key={b.household_id} align="right">{points(own.points)}</TableCell>;
                          }
                          const field = own.field;
                          const value = manualValue(b, own);
                          const changed = isChanged(b, own);
                          return (
                            <TableCell key={b.household_id} align="right" sx={changed ? { bgcolor: SIMULATED_BG } : undefined}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                                <Slider
                                  size="small" min={0} max={1} step={0.05} value={value}
                                  onChange={(_, v) => setValue(b.household_id, field, v as number)}
                                  sx={{ width: 70 }}
                                />
                                <TextField
                                  size="small" type="number" value={value}
                                  onChange={e => setValue(b.household_id, field, parseFloat(e.target.value))}
                                  inputProps={{ min: 0, max: 1, step: 0.1, style: { textAlign: 'right', width: 48 } }}
                                />
                              </Box>
                              <Typography variant="caption" color="textSecondary">
                                {changed
                                  ? `${points(simulatedPoints(b, own))} Pkt. (bisher ${points(own.points)}, Wert ${plain(own.value)})`
                                  : `${points(own.points)} Pkt.`}
                              </Typography>
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    ))}
                  </Fragment>
                ))}
                <TableRow className={NO_ZEBRA_ROW_CLASS}>
                  <TableCell colSpan={2} sx={{ fontWeight: 'bold' }}>Grundpunktzahl</TableCell>
                  {breakdowns.map(b => (
                    <TableCell key={b.household_id} align="right" sx={{ fontWeight: 'bold' }}>
                      {points(simulatedTotal(b) - (b.occupancy?.points ?? 0))}
                    </TableCell>
                  ))}
                </TableRow>
                <TableRow className={NO_ZEBRA_ROW_CLASS}>
                  <TableCell>Wohnraumausnutzung</TableCell>
                  <TableCell />
                  {breakdowns.map(b => (
                    <TableCell key={b.household_id} align="right">{b.occupancy ? points(b.occupancy.points) : '—'}</TableCell>
                  ))}
                </TableRow>
                <TableRow className={NO_ZEBRA_ROW_CLASS} sx={{ '& td': { borderTop: 2, borderColor: 'divider' } }}>
                  <TableCell colSpan={2} sx={{ fontWeight: 'bold', fontSize: '1rem' }}>Gesamtpunktzahl</TableCell>
                  {breakdowns.map(b => {
                    const total = simulatedTotal(b);
                    const delta = total - b.total_score;
                    return (
                      <TableCell key={b.household_id} align="right" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                        {points(total)}
                        {Math.abs(delta) > 1e-9 && (
                          <Typography variant="caption" display="block" color={delta > 0 ? 'success.main' : 'error.main'}>
                            {delta > 0 ? '+' : ''}{num(delta, 2)} (bisher {points(b.total_score)})
                          </Typography>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
                <TableRow className={NO_ZEBRA_ROW_CLASS}>
                  <TableCell colSpan={2}>Rang in der Auswahl</TableCell>
                  {breakdowns.map(b => {
                    const now = simulatedRanks.get(b.household_id)!;
                    const before = originalRanks.get(b.household_id)!;
                    return (
                      <TableCell key={b.household_id} align="right">
                        <strong>{now}</strong>
                        {now !== before && (
                          <Tooltip title={`bisher Rang ${before}`}>
                            {now < before
                              ? <ArrowUpwardIcon color="success" fontSize="small" sx={{ verticalAlign: 'middle', ml: 0.5 }} />
                              : <ArrowDownwardIcon color="error" fontSize="small" sx={{ verticalAlign: 'middle', ml: 0.5 }} />}
                          </Tooltip>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
                <TableRow className={NO_ZEBRA_ROW_CLASS}>
                  <TableCell colSpan={2}>Abstand zum Ersten</TableCell>
                  {breakdowns.map(b => (
                    <TableCell key={b.household_id} align="right">{points(leader - simulatedTotal(b))}</TableCell>
                  ))}
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setValues({})} disabled={!hasChanges || busy}>Zurücksetzen</Button>
        <Button onClick={handleExport} disabled={!breakdowns || busy}>Als Excel exportieren</Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button onClick={onClose}>Schließen</Button>
        <Button variant="contained" onClick={() => setConfirmOpen(true)} disabled={!hasChanges || busy}>
          Werte übernehmen
        </Button>
      </DialogActions>
      <ConfirmDialog
        open={confirmOpen}
        title="Werte übernehmen"
        message={`Die geänderten manuellen Bewertungen von ${Object.keys(overrides).length} Haushalt(en) werden gespeichert und die Punkte aller Haushalte neu berechnet.`}
        confirmLabel="Übernehmen"
        busy={busy}
        onConfirm={handleApply}
        onClose={() => setConfirmOpen(false)}
      />
    </Dialog>
  );
}

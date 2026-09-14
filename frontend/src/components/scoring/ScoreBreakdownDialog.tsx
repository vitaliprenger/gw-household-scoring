import { Fragment, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Collapse, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRightIcon from '@mui/icons-material/KeyboardArrowRight';
import { BreakdownTarget, HouseholdBreakdown, ScoreCriterion } from '../../types';
import { calculateScores, exportScoreBreakdowns, getScoreBreakdowns } from '../../api';
import { NO_ZEBRA_ROW_CLASS } from '../common/tableStyles';
import {
  criterionFormula, membershipFormula, num, occupancyFormula, occupancyLabel, plain, points, termFormula,
} from './format';
import { formatDate } from '../applications/wishes';

interface ScoreBreakdownDialogProps {
  open: boolean;
  target: BreakdownTarget | null;
  /** Beschriftung der Kategorie, z. B. „3 Zimmer / WBS A“. */
  categoryLabel?: string;
  onClose: () => void;
  /** Wird nach „Punkte neu berechnen“ aufgerufen, damit die Rangliste nachlädt. */
  onRecalculated?: () => void;
}

/** Details eines Kriteriums: Rechenweg je Gruppe bzw. Eingangswerte. */
function CriterionDetail({ criterion }: { criterion: ScoreCriterion }) {
  if (criterion.kind === 'target') {
    return (
      <Box sx={{ py: 1 }}>
        {criterion.terms.length === 0 && (
          <Typography variant="body2" color="textSecondary">Keine Person mit Angabe zu diesem Merkmal → 0</Typography>
        )}
        {criterion.terms.length > 0 && (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Gruppe</TableCell>
                <TableCell>Personen</TableCell>
                <TableCell>Rechenweg</TableCell>
                <TableCell align="right">Wert</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {criterion.terms.map(term => (
                <TableRow key={term.group} sx={term.applies ? undefined : { '& td': { color: 'text.disabled' } }}>
                  <TableCell>{term.label}</TableCell>
                  <TableCell>{term.persons.join(', ')}</TableCell>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{termFormula(term)}</TableCell>
                  <TableCell align="right">{num(term.value, 3)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {criterion.ignored_persons.length > 0 && (
          <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
            Nicht berücksichtigt: {criterion.ignored_persons.map(p => `${p.name} (${p.reason})`).join('; ')}
          </Typography>
        )}
        <Typography variant="caption" color="textSecondary" component="p" sx={{ mt: 1 }}>
          Ist = Anteil der Bewohner-Personen mit Angabe (siehe Ist-Statistik). Jede Person trägt (Ziel − Ist) / Ziel bei:
          1 wenn ihre Gruppe unter den Bewohnern fehlt, 0 sobald der Zielwert erreicht ist. Die Beiträge aller Personen
          werden addiert.
        </Typography>
      </Box>
    );
  }
  if (criterion.kind === 'membership') {
    const m = criterion.membership;
    const persons = m?.persons ?? [];
    return (
      <Box sx={{ py: 1 }}>
        {persons.length === 0 ? (
          <Typography variant="body2" color="textSecondary">Für keine Person im Haushalt ist ein Eintrittsdatum gepflegt → 0</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Person</TableCell>
                <TableCell>Mitglied seit</TableCell>
                <TableCell>Rechenweg</TableCell>
                <TableCell align="right">Wert</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {persons.map(p => (
                <TableRow key={`${p.person_name}-${p.member_since}`}>
                  <TableCell>{p.person_name}</TableCell>
                  <TableCell>{formatDate(p.member_since)}</TableCell>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{membershipFormula(p, m!.max_years)}</TableCell>
                  <TableCell align="right">{num(p.value, 3)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {criterion.ignored_persons.length > 0 && (
          <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
            Nicht berücksichtigt: {criterion.ignored_persons.map(p => `${p.name} (${p.reason})`).join('; ')}
          </Typography>
        )}
        {m && (
          <Typography variant="caption" color="textSecondary" component="p" sx={{ mt: 1 }}>
            Jahre bis zum Stichtag {formatDate(m.reference_date)}. Jede Person erhält anteilig bis zu {plain(m.max_years)} Jahren
            höchstens 1; die Beiträge aller Personen werden addiert.
          </Typography>
        )}
      </Box>
    );
  }
  return (
    <Typography variant="body2" sx={{ py: 1 }}>
      Manuell bewertet im Haushaltsdetail-Dialog (0–1). Im Vergleich der Rangliste lassen sich andere Werte durchspielen.
    </Typography>
  );
}

/**
 * Aufschlüsselung der Punkte eines Haushalts: je Kriterium Teilscore, Gewicht,
 * Punkte und Rechenweg mit den tatsächlichen Werten.
 */
export default function ScoreBreakdownDialog({
  open, target, categoryLabel, onClose, onRecalculated,
}: ScoreBreakdownDialogProps) {
  const [breakdown, setBreakdown] = useState<HouseholdBreakdown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = async () => {
    if (!target) return;
    setError(null);
    try {
      const [result] = await getScoreBreakdowns([target]);
      setBreakdown(result ?? null);
    } catch {
      setError('Aufschlüsselung konnte nicht geladen werden.');
    }
  };

  useEffect(() => {
    if (open && target) {
      setBreakdown(null);
      setExpanded(new Set());
      load();
    }
  }, [open, target?.household_id, target?.size_rooms, target?.with_occupancy]);

  const toggle = (key: string) => setExpanded(prev => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  const handleRecalculate = async () => {
    setBusy(true);
    try {
      await calculateScores();
      await load();
      onRecalculated?.();
    } finally {
      setBusy(false);
    }
  };

  const handleExport = async () => {
    if (!target) return;
    setBusy(true);
    try {
      await exportScoreBreakdowns([target], {});
    } catch {
      setError('Export fehlgeschlagen.');
    } finally {
      setBusy(false);
    }
  };

  const categories = breakdown ? [...new Set(breakdown.criteria.map(c => c.category))] : [];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        Punkteaufschlüsselung{breakdown ? ` – ${breakdown.name}` : ''}
        {breakdown && (
          <Typography variant="body2" color="textSecondary">
            {breakdown.member_count} Mitglieder
            {categoryLabel ? ` · Kategorie ${categoryLabel}` : ' · ohne Wohnungskategorie'}
            {breakdown.score_calculated_at ? ' · Stichtag der Berechnung ' : ' · Stichtag heute '}
            {new Date(breakdown.calculated_at).toLocaleDateString('de-DE')}
          </Typography>
        )}
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {!breakdown && !error && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
        {breakdown && (
          <>
            {breakdown.is_stale && (
              <Alert
                severity="warning"
                sx={{ mb: 2 }}
                action={<Button color="inherit" size="small" disabled={busy} onClick={handleRecalculate}>Punkte neu berechnen</Button>}
              >
                {breakdown.score_calculated_at
                  ? `Punktzahl veraltet: gespeichert ${points(breakdown.stored_score)}, mit den heutigen Daten zum selben Stichtag ${points(breakdown.base_score)}. Die Daten des Haushalts, der Bewohner oder die Bewertungskonfiguration wurden seit der Berechnung geändert.`
                  : `Die gespeicherte Punktzahl (${points(breakdown.stored_score)}) stammt aus einer Berechnung ohne gespeicherten Stichtag; die Aufschlüsselung rechnet deshalb zu heute (${points(breakdown.base_score)}).`}
                {' '}Die Rangliste nutzt bis zur Neuberechnung den gespeicherten Wert.
              </Alert>
            )}
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 40 }} />
                    <TableCell>Kriterium</TableCell>
                    <TableCell>Rechenweg</TableCell>
                    <TableCell align="right">Teilscore</TableCell>
                    <TableCell align="right">Gewicht</TableCell>
                    <TableCell align="right">Punkte</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {categories.map(category => (
                    <Fragment key={category}>
                      <TableRow className={NO_ZEBRA_ROW_CLASS}>
                        <TableCell colSpan={6} sx={{ bgcolor: 'action.hover', fontWeight: 'bold' }}>{category}</TableCell>
                      </TableRow>
                      {breakdown.criteria.filter(c => c.category === category).map(c => (
                        <Fragment key={c.key}>
                          <TableRow hover onClick={() => toggle(c.key)} sx={{ cursor: 'pointer' }}>
                            <TableCell>
                              <IconButton size="small">
                                {expanded.has(c.key) ? <KeyboardArrowDownIcon /> : <KeyboardArrowRightIcon />}
                              </IconButton>
                            </TableCell>
                            <TableCell>
                              {c.label}
                              {c.manual && <Chip label="manuell bewertet" size="small" variant="outlined" sx={{ ml: 1 }} />}
                            </TableCell>
                            <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{criterionFormula(c)}</TableCell>
                            <TableCell align="right">{num(c.subscore, 3)}</TableCell>
                            <TableCell align="right">{plain(c.weight)}</TableCell>
                            <TableCell align="right">{points(c.points)}</TableCell>
                          </TableRow>
                          <TableRow className={NO_ZEBRA_ROW_CLASS}>
                            <TableCell colSpan={6} sx={{ py: 0, borderBottom: expanded.has(c.key) ? undefined : 'none' }}>
                              <Collapse in={expanded.has(c.key)} unmountOnExit>
                                <Box sx={{ pl: 6 }}><CriterionDetail criterion={c} /></Box>
                              </Collapse>
                            </TableCell>
                          </TableRow>
                        </Fragment>
                      ))}
                    </Fragment>
                  ))}
                  <TableRow className={NO_ZEBRA_ROW_CLASS}>
                    <TableCell />
                    <TableCell colSpan={4} sx={{ fontWeight: 'bold' }}>Grundpunktzahl (Summe)</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>{points(breakdown.base_score)}</TableCell>
                  </TableRow>
                  <TableRow className={NO_ZEBRA_ROW_CLASS}>
                    <TableCell />
                    <TableCell>Wohnraumausnutzung{breakdown.occupancy ? ` (${occupancyLabel(breakdown.occupancy.size_rooms)})` : ''}</TableCell>
                    <TableCell colSpan={3} sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                      {breakdown.occupancy
                        ? occupancyFormula(breakdown.occupancy)
                        : 'hängt an der Zimmerzahl – erst mit gewählter Wohnungskategorie'}
                    </TableCell>
                    <TableCell align="right">{breakdown.occupancy ? points(breakdown.occupancy.points) : '—'}</TableCell>
                  </TableRow>
                  <TableRow className={NO_ZEBRA_ROW_CLASS}>
                    <TableCell />
                    <TableCell colSpan={4} sx={{ fontWeight: 'bold', fontSize: '1rem' }}>Gesamtpunktzahl</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>{points(breakdown.total_score)}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
            <Typography variant="caption" color="textSecondary" component="p" sx={{ mt: 2 }}>
              Gewichte, Faktoren und Zielwerte stammen aus der Bewertungskonfiguration. Alter und Mitgliedsdauer gelten
              zum Stichtag der letzten Berechnung, damit die Summe genau der Rangliste entspricht. Eine Zeile anklicken
              zeigt den vollständigen Rechenweg.
            </Typography>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleExport} disabled={!breakdown || busy}>Als Excel exportieren</Button>
        <Button onClick={onClose}>Schließen</Button>
      </DialogActions>
    </Dialog>
  );
}

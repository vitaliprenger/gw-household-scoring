import { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Card, CardContent, Table, TableBody, TableCell,
  TableHead, TableRow, ToggleButton, ToggleButtonGroup, Grid, Alert,
} from '@mui/material';
import { getResidentStatistics } from '../../api';
import { ResidentStatistics, StatisticsCategory, StatisticsGroup } from '../../types';
import { zebraTableSx, NO_ZEBRA_ROW_CLASS } from '../common/tableStyles';

/** Darstellungsform der Ist-Statistik: absolute Zahlen oder Anteile. */
type Mode = 'absolute' | 'relative';

const formatCount = (value: number): string => value.toLocaleString('de-DE');

const formatDecimal = (value: number): string =>
  value.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const formatPercent = (value: number): string =>
  (value * 100).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' %';

/** Abweichung mit Vorzeichen — negativ heißt: unter dem Zielwert. */
const withSign = (value: number, format: (v: number) => string): string =>
  (value > 0 ? '+' : '') + format(value);

const basisLabel = (category: StatisticsCategory): string =>
  category.basis === 'household' ? 'Haushalte' : 'Personen';

function CategoryTable({ category, mode }: { category: StatisticsCategory; mode: Mode }) {
  const hasTargets = category.groups.some(g => g.target_ratio !== null && g.target_ratio !== undefined);
  const absolute = mode === 'absolute';

  const valueOf = (g: StatisticsGroup): string =>
    absolute ? formatCount(g.count) : formatPercent(g.ratio);

  const targetOf = (g: StatisticsGroup): string => {
    if (g.target_ratio === null || g.target_ratio === undefined) return '—';
    return absolute ? formatDecimal(g.target_count ?? 0) : formatPercent(g.target_ratio);
  };

  const deviationOf = (g: StatisticsGroup): string => {
    if (g.target_ratio === null || g.target_ratio === undefined) return '—';
    return absolute
      ? withSign(g.count - (g.target_count ?? 0), formatDecimal)
      : withSign(g.ratio - g.target_ratio, formatPercent);
  };

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="h6" sx={{ mb: 0.5 }}>{category.label}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {formatCount(category.total)} {basisLabel(category)} als Bezugsgröße
      </Typography>
      <Table size="small" sx={zebraTableSx}>
        <TableHead>
          <TableRow>
            <TableCell>Ausprägung</TableCell>
            <TableCell align="right">{absolute ? 'Anzahl' : 'Anteil'}</TableCell>
            {hasTargets && (
              <>
                <TableCell align="right">{absolute ? `Ziel (${basisLabel(category)})` : 'Zielwert'}</TableCell>
                <TableCell align="right">Abweichung</TableCell>
              </>
            )}
          </TableRow>
        </TableHead>
        <TableBody>
          {category.groups.map(group => (
            <TableRow key={group.key}>
              <TableCell>{group.label}</TableCell>
              <TableCell align="right">{valueOf(group)}</TableCell>
              {hasTargets && (
                <>
                  <TableCell align="right" sx={{ color: 'text.secondary' }}>{targetOf(group)}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary' }}>{deviationOf(group)}</TableCell>
                </>
              )}
            </TableRow>
          ))}
          <TableRow className={NO_ZEBRA_ROW_CLASS}>
            <TableCell><strong>Summe</strong></TableCell>
            <TableCell align="right">
              <strong>
                {absolute
                  ? formatCount(category.groups.reduce((sum, g) => sum + g.count, 0))
                  : formatPercent(category.groups.reduce((sum, g) => sum + g.ratio, 0))}
              </strong>
            </TableCell>
            {hasTargets && (
              <>
                <TableCell />
                <TableCell />
              </>
            )}
          </TableRow>
        </TableBody>
      </Table>
    </Paper>
  );
}

export default function StatisticsTab() {
  const [stats, setStats] = useState<ResidentStatistics | null>(null);
  const [mode, setMode] = useState<Mode>('absolute');
  const [error, setError] = useState(false);

  useEffect(() => { loadStatistics(); }, []);

  async function loadStatistics() {
    try {
      setStats(await getResidentStatistics());
      setError(false);
    } catch (e) {
      console.error('Failed to load resident statistics', e);
      setError(true);
    }
  }

  if (error) {
    return <Alert severity="error">Die Ist-Statistik konnte nicht geladen werden.</Alert>;
  }
  if (!stats) {
    return <Typography color="text.secondary">Statistik wird geladen …</Typography>;
  }

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Ist-Verteilung der aktuellen Bewohner — Grundlage sind alle nicht archivierten Personen
        in Haushalten, die einer Wohnung zugeordnet sind. Dieselben Zahlen bestimmen als
        IST-Verteilung die Durchmischungspunkte der Bewerber-Haushalte.
      </Typography>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>Bewohner-Haushalte</Typography>
              <Typography variant="h4">{formatCount(stats.household_count)}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>Personen</Typography>
              <Typography variant="h4">{formatCount(stats.person_count)}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <ToggleButtonGroup
        exclusive
        size="small"
        value={mode}
        onChange={(_, value: Mode | null) => value && setMode(value)}
        sx={{ mb: 2 }}
      >
        <ToggleButton value="absolute">Absolute Zahlen</ToggleButton>
        <ToggleButton value="relative">Relative Zahlen</ToggleButton>
      </ToggleButtonGroup>

      {stats.person_count === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Es sind keine Bewohner-Haushalte erfasst — die Ist-Statistik ist leer.
        </Alert>
      )}

      <Grid container spacing={2} alignItems="stretch">
        {stats.categories.map(category => (
          <Grid size={{ xs: 12, md: 6 }} key={category.key}>
            <CategoryTable category={category} mode={mode} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

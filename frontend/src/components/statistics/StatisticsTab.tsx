import { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Card, CardContent, Table, TableBody, TableCell,
  TableHead, TableRow, ToggleButton, ToggleButtonGroup, Grid, Alert, Button,
} from '@mui/material';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import { getResidentStatistics, getResidentMissingData } from '../../api';
import {
  ResidentStatistics, StatisticsCategory, StatisticsDimension, PersonMissingData,
} from '../../types';
import { zebraTableSx, NO_ZEBRA_ROW_CLASS } from '../common/tableStyles';
import MissingDataDialog from './MissingDataDialog';
import TargetDistributionChart from './TargetDistributionChart';
import {
  Mode, formatCount, formatPercent, formatValue, formatTarget, formatDeviation, hasTarget,
} from './format';

const basisLabel = (category: StatisticsCategory): string =>
  category.basis === 'household' ? 'Haushalte' : 'Personen';

function CategoryCard({ category, mode, onReview }: {
  category: StatisticsCategory;
  mode: Mode;
  /** Öffnet die Prüfliste der Personen ohne Angabe zu diesem Merkmal. */
  onReview: () => void;
}) {
  const hasTargets = category.groups.some(hasTarget);
  const absolute = mode === 'absolute';

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="h6" sx={{ mb: 0.5 }}>{category.label}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {formatCount(category.total)} {basisLabel(category)}
        {category.basis === 'person' ? ' mit Angabe' : ''} als Bezugsgröße
      </Typography>
      {hasTargets && category.total > 0 && (
        <TargetDistributionChart category={category} mode={mode} />
      )}
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
              <TableCell align="right">{formatValue(group, mode)}</TableCell>
              {hasTargets && (
                <>
                  <TableCell align="right" sx={{ color: 'text.secondary' }}>{formatTarget(group, mode)}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary' }}>{formatDeviation(group, mode)}</TableCell>
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
      {category.excluded_groups.filter(g => g.count > 0).map(g => (
        <Typography key={g.key} variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          {formatCount(g.count)} {g.count === 1 ? 'Person' : 'Personen'} {g.label} – nicht berücksichtigt
        </Typography>
      ))}
      {category.unknown_count > 0 && (
        <Box sx={{ mt: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {formatCount(category.unknown_count)} {category.unknown_count === 1 ? 'Person' : 'Personen'} ohne
            Angabe – nicht berücksichtigt
          </Typography>
          <Button size="small" startIcon={<FactCheckIcon />} onClick={onReview}>Prüfen</Button>
        </Box>
      )}
    </Paper>
  );
}

interface StatisticsTabProps {
  /** Öffnet den Haushaltsdetail-Dialog, um fehlende Angaben zu korrigieren. */
  onShowHousehold: (householdId: number) => void;
  /** Ändert sich nach Bearbeitungen im Haushaltsdetail-Dialog und löst ein Neuladen aus. */
  refreshKey: number;
}

export default function StatisticsTab({ onShowHousehold, refreshKey }: StatisticsTabProps) {
  const [stats, setStats] = useState<ResidentStatistics | null>(null);
  const [missing, setMissing] = useState<PersonMissingData[]>([]);
  const [mode, setMode] = useState<Mode>('absolute');
  const [error, setError] = useState(false);
  /** Offene Prüfliste: ein Merkmal, alle Merkmale (`null`) oder geschlossen (`undefined`). */
  const [review, setReview] = useState<StatisticsDimension | null | undefined>(undefined);

  useEffect(() => { loadStatistics(); }, [refreshKey]);

  async function loadStatistics() {
    try {
      const [statistics, missingData] = await Promise.all([
        getResidentStatistics(),
        getResidentMissingData(),
      ]);
      setStats(statistics);
      setMissing(missingData);
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
        IST-Verteilung die Durchmischungspunkte der Bewerber-Haushalte. Personen ohne Angabe zu
        einem Merkmal bleiben bei diesem Merkmal außen vor; über „Prüfen“ lassen sie sich einzeln
        kontrollieren. Die Altersgruppen beziehen sich wie ihre Zielwerte auf Personen ab 20 Jahren.
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
        <Grid size={{ xs: 12, sm: 6 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>Personen mit fehlenden Angaben</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                <Typography variant="h4">{formatCount(stats.incomplete_person_count)}</Typography>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<FactCheckIcon />}
                  disabled={stats.incomplete_person_count === 0}
                  onClick={() => setReview(null)}
                >
                  Prüfen
                </Button>
              </Box>
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
            <CategoryCard
              category={category}
              mode={mode}
              onReview={() => setReview(category.key as StatisticsDimension)}
            />
          </Grid>
        ))}
      </Grid>

      <MissingDataDialog
        open={review !== undefined}
        dimension={review ?? null}
        people={missing}
        onClose={() => setReview(undefined)}
        onShowHousehold={onShowHousehold}
      />
    </Box>
  );
}

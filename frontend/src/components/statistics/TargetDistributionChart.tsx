import { Box, Typography, useTheme } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import { useXScale, useYScale } from '@mui/x-charts/hooks';
import { StatisticsCategory, StatisticsGroup } from '../../types';
import { Mode, formatCount, formatValue, formatTarget, formatDeviation, hasTarget } from './format';

/** Farbe der Ist-Balken: Slot 1 (Blau) der validierten Diagrammpalette. */
const ACTUAL_COLOR = '#2a78d6';
/** Höhe je Ausprägung; mit dem Kategorieabstand ergibt das Balken von rund 19 px. */
const BAND_HEIGHT = 32;
const CATEGORY_GAP_RATIO = 0.4;
const X_AXIS_HEIGHT = 28;
const MARGIN = { top: 8, right: 16, bottom: 0, left: 0 };
/** Längere Ausprägungen werden an der Achse gekürzt; der Tooltip zeigt sie vollständig. */
const MAX_TICK_LABEL_LENGTH = 28;
/** So weit ragt die Zielmarke oben und unten über den Balken hinaus. */
const TARGET_OVERHANG = 4;

const actualOf = (g: StatisticsGroup, mode: Mode): number =>
  mode === 'absolute' ? g.count : g.ratio;

const targetOf = (g: StatisticsGroup, mode: Mode): number | null => {
  if (g.target_ratio === null || g.target_ratio === undefined) return null;
  return mode === 'absolute' ? g.target_count ?? 0 : g.target_ratio;
};

const shorten = (label: string): string =>
  label.length > MAX_TICK_LABEL_LENGTH ? label.slice(0, MAX_TICK_LABEL_LENGTH - 1).trimEnd() + '…' : label;

const formatAxisPercent = (value: number): string =>
  (value * 100).toLocaleString('de-DE', { maximumFractionDigits: 1 }) + ' %';

/** Rundet das Achsenende auf einen glatten Wert (0,4 / 0,5 / 20 / 25 …), damit auch Zielmarken jenseits des größten Ist-Werts sichtbar bleiben. */
function niceCeil(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(s => s * magnitude >= value - 1e-9) ?? 10;
  return Number((step * magnitude).toPrecision(12));
}

/** Senkrechte Zielmarke je Ausprägung, mit Rand in Flächenfarbe, damit sie sich vom Balken abhebt. */
function TargetMarks({ keys, targets }: { keys: string[]; targets: (number | null)[] }) {
  const theme = useTheme();
  const xScale = useXScale<'linear'>();
  const yScale = useYScale<'band'>();

  return (
    <g pointerEvents="none">
      {keys.map((key, i) => {
        const target = targets[i];
        const y = yScale(key);
        if (target === null || y === undefined) return null;
        const x = xScale(target);
        const y1 = y - TARGET_OVERHANG;
        const y2 = y + yScale.bandwidth() + TARGET_OVERHANG;
        return (
          <g key={key}>
            <line x1={x} x2={x} y1={y1} y2={y2} stroke={theme.palette.background.paper} strokeWidth={6} strokeLinecap="round" />
            <line x1={x} x2={x} y1={y1} y2={y2} stroke={theme.palette.text.primary} strokeWidth={2} strokeLinecap="round" />
          </g>
        );
      })}
    </g>
  );
}

function LegendItem({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      {swatch}
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Box>
  );
}

/**
 * Waagerechtes Balkendiagramm Ist vs. Zielwert eines Merkmals: je Ausprägung ein Balken für
 * den Ist-Wert und eine senkrechte Marke für den Zielwert. Die Tabelle darunter bleibt die
 * vollständige Zahlenansicht; der Tooltip ergänzt sie nur.
 */
export default function TargetDistributionChart({ category, mode }: {
  category: StatisticsCategory;
  mode: Mode;
}) {
  const { groups } = category;
  const absolute = mode === 'absolute';
  const keys = groups.map(g => g.key);
  const labels = new Map(groups.map(g => [g.key, g.label]));
  const actual = groups.map(g => actualOf(g, mode));
  const targets = groups.map(g => targetOf(g, mode));
  const withTargets = targets.some(t => t !== null);
  const max = niceCeil(Math.max(...actual, ...targets.map(t => t ?? 0)));

  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 2 }}>
        <LegendItem
          label="Ist"
          swatch={<Box sx={{ width: 12, height: 12, borderRadius: '2px', bgcolor: ACTUAL_COLOR }} />}
        />
        {withTargets && (
          <LegendItem
            label="Zielwert"
            swatch={<Box sx={{ width: 2, height: 14, borderRadius: '1px', bgcolor: 'text.primary' }} />}
          />
        )}
      </Box>
      <BarChart
        layout="horizontal"
        height={groups.length * BAND_HEIGHT + MARGIN.top + MARGIN.bottom + X_AXIS_HEIGHT}
        margin={MARGIN}
        hideLegend
        borderRadius={4}
        grid={{ vertical: true }}
        yAxis={[{
          scaleType: 'band',
          data: keys,
          categoryGapRatio: CATEGORY_GAP_RATIO,
          width: 'auto',
          disableTicks: true,
          valueFormatter: (key, context) => {
            const label = labels.get(String(key)) ?? String(key);
            return context.location === 'tick' ? shorten(label) : label;
          },
        }]}
        xAxis={[{
          min: 0,
          max,
          height: X_AXIS_HEIGHT,
          tickMinStep: absolute ? 1 : undefined,
          valueFormatter: (value: number) => (absolute ? formatCount(value) : formatAxisPercent(value)),
        }]}
        series={[{
          data: actual,
          label: 'Ist',
          color: ACTUAL_COLOR,
          valueFormatter: (_value, { dataIndex }) => {
            const g = groups[dataIndex];
            return hasTarget(g)
              ? `${formatValue(g, mode)} (Ziel ${formatTarget(g, mode)}, Abweichung ${formatDeviation(g, mode)})`
              : formatValue(g, mode);
          },
        }]}
      >
        {withTargets && <TargetMarks keys={keys} targets={targets} />}
      </BarChart>
    </Box>
  );
}

import { useMemo, useState } from 'react';
import {
  Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Link,
  Switch, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import { MissingValue, PersonMissingData, StatisticsDimension } from '../../types';
import { zebraTableSx } from '../common/tableStyles';

/** Personenfeld hinter dem Merkmal — so, wie es im Haushaltsdetail-Dialog heißt. */
const FIELD_LABELS: Record<StatisticsDimension, string> = {
  age: 'Geburtsdatum',
  gender: 'Geschlecht',
  occupation: 'Haupttätigkeit',
  education: 'Bildungsabschluss',
};

const reasonText = (m: MissingValue): string => {
  switch (m.reason) {
    case 'unrecognized': return `„${m.raw_value}“ nicht erkannt`;
    case 'category_0': return '0 – keine Zuordnung';
    default: return m.suspected_import_error ? 'leer trotz Individualbogen' : 'leer';
  }
};

const formatDate = (val?: string | null): string =>
  val ? new Date(val).toLocaleDateString('de-DE') : '—';

interface MissingDataDialogProps {
  open: boolean;
  /** Merkmal, dessen fehlende Angaben geprüft werden; `null` = alle Merkmale. */
  dimension: StatisticsDimension | null;
  people: PersonMissingData[];
  onClose: () => void;
  onShowHousehold: (householdId: number) => void;
}

/**
 * Prüfliste der Bewohner-Personen ohne Angabe. Fehlende Angaben können auf
 * Fehler beim Datenimport hindeuten; korrigiert wird im Haushaltsdetail-Dialog.
 */
export default function MissingDataDialog({
  open, dimension, people, onClose, onShowHousehold,
}: MissingDataDialogProps) {
  const [onlySuspected, setOnlySuspected] = useState(false);
  const [hideMinors, setHideMinors] = useState(false);

  const rows = useMemo(() => {
    const relevant = people
      .map(person => ({
        person,
        missing: person.missing.filter(m =>
          (dimension === null || m.dimension === dimension)
          && (!onlySuspected || m.suspected_import_error)),
      }))
      .filter(r => r.missing.length > 0)
      .filter(r => !hideMinors || r.person.age == null || r.person.age >= 20);
    // Verdachtsfälle zuerst; die Reihenfolge des Backends bleibt sonst erhalten.
    const rank = (r: typeof relevant[number]) => (r.missing.some(m => m.suspected_import_error) ? 0 : 1);
    return [...relevant].sort((a, b) => rank(a) - rank(b));
  }, [people, dimension, onlySuspected, hideMinors]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        {dimension ? `Ohne Angabe: ${FIELD_LABELS[dimension]}` : 'Personen mit fehlenden Angaben'}
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Diese Bewohner-Personen zählen beim jeweiligen Merkmal nicht mit. Ein nicht erkannter
          Wert oder ein leeres Feld trotz importiertem Individualbogen deutet auf einen Fehler beim
          Datenimport hin (orange markiert). Korrigiert wird über den Haushalt.
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 1 }}>
          <Typography variant="body2" sx={{ flexGrow: 1 }}>
            {rows.length} {rows.length === 1 ? 'Person' : 'Personen'}
          </Typography>
          <FormControlLabel
            control={<Switch size="small" checked={onlySuspected} onChange={e => setOnlySuspected(e.target.checked)} />}
            label="Nur Verdacht auf Importfehler"
          />
          <FormControlLabel
            control={<Switch size="small" checked={hideMinors} onChange={e => setHideMinors(e.target.checked)} />}
            label="Personen unter 20 ausblenden"
          />
        </Box>
        <TableContainer>
          <Table size="small" sx={zebraTableSx}>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Mitgl.-Nr.</TableCell>
                <TableCell>Haushalt</TableCell>
                <TableCell>Wohnung</TableCell>
                <TableCell align="right">Alter</TableCell>
                <TableCell>Individualbogen</TableCell>
                <TableCell>Fehlende Angabe</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map(({ person, missing }) => (
                <TableRow key={person.person_id}>
                  <TableCell>{person.first_name} {person.last_name}</TableCell>
                  <TableCell>{person.member_number ?? '—'}</TableCell>
                  <TableCell>
                    <Link component="button" variant="body2" onClick={() => onShowHousehold(person.household_id)}>
                      {person.household_name}
                    </Link>
                  </TableCell>
                  <TableCell>{person.apartment_unit ?? '—'}</TableCell>
                  <TableCell align="right">{person.age ?? '—'}</TableCell>
                  <TableCell>{formatDate(person.individual_import_timestamp)}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {missing.map(m => (
                        <Chip
                          key={m.dimension}
                          size="small"
                          label={dimension ? reasonText(m) : `${FIELD_LABELS[m.dimension]}: ${reasonText(m)}`}
                          color={m.suspected_import_error ? 'warning' : 'default'}
                          variant={m.reason === 'category_0' ? 'outlined' : 'filled'}
                        />
                      ))}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary">Keine Personen ohne Angabe.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Schließen</Button>
      </DialogActions>
    </Dialog>
  );
}

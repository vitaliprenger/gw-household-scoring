import { useState, useEffect, useMemo } from 'react';
import {
  Box, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Typography, TextField, FormControlLabel, Switch, Chip, Link, InputAdornment,
  TableSortLabel, IconButton, Tooltip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ArchiveIcon from '@mui/icons-material/Archive';
import UnarchiveIcon from '@mui/icons-material/Unarchive';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import { getAllPersons, toggleArchivePerson, unassignPerson } from '../../api';
import { PersonWithHousehold } from '../../types';
import AssignHouseholdDialog from './AssignHouseholdDialog';
import ConfirmDialog from '../common/ConfirmDialog';

interface PersonsTabProps {
  onShowHousehold: (householdId: number) => void;
}

type SortKey = 'last_name' | 'first_name' | 'birth_date' | 'gender' | 'household_name';
type SortDir = 'asc' | 'desc';

function formatDate(val?: string): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('de-DE');
  } catch {
    return val;
  }
}

function formatDateTime(val?: string): string {
  if (!val) return '—';
  try {
    const d = new Date(val);
    return d.toLocaleDateString('de-DE') + ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return val;
  }
}

export default function PersonsTab({ onShowHousehold }: PersonsTabProps) {
  const [persons, setPersons] = useState<PersonWithHousehold[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [onlyUnassigned, setOnlyUnassigned] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('last_name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [assignTarget, setAssignTarget] = useState<PersonWithHousehold | null>(null);
  const [unassignTarget, setUnassignTarget] = useState<PersonWithHousehold | null>(null);
  const [unassigning, setUnassigning] = useState(false);

  useEffect(() => {
    loadPersons();
  }, [showArchived]);

  const loadPersons = async () => {
    try {
      const data = await getAllPersons(showArchived);
      setPersons(data);
    } catch (e) {
      console.error('Failed to load persons', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const filtered = useMemo(() => {
    let list = persons;
    if (onlyUnassigned) {
      list = list.filter(p => !p.household_id);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(p =>
        `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
        (p.household_name ?? '').toLowerCase().includes(q) ||
        (p.member_number ?? '').toLowerCase().includes(q)
      );
    }
    const sorted = [...list].sort((a, b) => {
      const valA = (a[sortKey] ?? '') as string;
      const valB = (b[sortKey] ?? '') as string;
      const cmp = valA.localeCompare(valB, 'de', { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [persons, onlyUnassigned, search, sortKey, sortDir]);

  const handleToggleArchive = async (personId: number) => {
    try {
      await toggleArchivePerson(personId);
      await loadPersons();
    } catch (e) {
      console.error('Archive toggle failed', e);
    }
  };

  const handleUnassign = async () => {
    if (!unassignTarget) return;
    setUnassigning(true);
    try {
      await unassignPerson(unassignTarget.id);
      setUnassignTarget(null);
      await loadPersons();
    } catch (e) {
      console.error('Unassign failed', e);
    } finally {
      setUnassigning(false);
    }
  };

  const unassignedCount = useMemo(() => persons.filter(p => !p.household_id).length, [persons]);

  if (loading) {
    return <Typography>Lade Personen...</Typography>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder="Name oder Haushalt suchen..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ minWidth: 280 }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={onlyUnassigned}
              onChange={(_, checked) => setOnlyUnassigned(checked)}
            />
          }
          label={`Nur ohne Haushalt (${unassignedCount})`}
        />
        <FormControlLabel
          control={
            <Switch
              checked={showArchived}
              onChange={(_, checked) => setShowArchived(checked)}
            />
          }
          label="Archivierte anzeigen"
        />
        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          {filtered.length} von {persons.length} Personen
        </Typography>
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>
                <TableSortLabel
                  active={sortKey === 'last_name'}
                  direction={sortKey === 'last_name' ? sortDir : 'asc'}
                  onClick={() => handleSort('last_name')}
                >
                  Nachname
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortKey === 'first_name'}
                  direction={sortKey === 'first_name' ? sortDir : 'asc'}
                  onClick={() => handleSort('first_name')}
                >
                  Vorname
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortKey === 'birth_date'}
                  direction={sortKey === 'birth_date' ? sortDir : 'asc'}
                  onClick={() => handleSort('birth_date')}
                >
                  Geburtsdatum
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortKey === 'gender'}
                  direction={sortKey === 'gender' ? sortDir : 'asc'}
                  onClick={() => handleSort('gender')}
                >
                  Geschlecht
                </TableSortLabel>
              </TableCell>
              <TableCell>Mitgliedsnr.</TableCell>
              <TableCell>Letzter Import</TableCell>
              <TableCell>Letzte Bearbeitung</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortKey === 'household_name'}
                  direction={sortKey === 'household_name' ? sortDir : 'asc'}
                  onClick={() => handleSort('household_name')}
                >
                  Haushalt
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">Aktionen</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filtered.map(person => (
              <TableRow key={person.id} hover sx={{ opacity: person.archived ? 0.5 : 1 }}>
                <TableCell>
                  {person.last_name}
                  {person.archived && <Chip label="Archiviert" size="small" sx={{ ml: 1 }} color="default" />}
                </TableCell>
                <TableCell>{person.first_name}</TableCell>
                <TableCell>{formatDate(person.birth_date)}</TableCell>
                <TableCell>{person.gender || '—'}</TableCell>
                <TableCell>{person.member_number || '—'}</TableCell>
                <TableCell>{formatDateTime(person.individual_import_timestamp)}</TableCell>
                <TableCell>{formatDateTime(person.updated_at)}</TableCell>
                <TableCell>
                  {person.household_id && person.household_name ? (
                    <Link
                      component="button"
                      variant="body2"
                      onClick={() => onShowHousehold(person.household_id!)}
                    >
                      {person.household_name}
                    </Link>
                  ) : (
                    <Chip label="Kein Haushalt" size="small" color="warning" variant="outlined" />
                  )}
                </TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  {person.household_id ? (
                    <Tooltip title="Aus Haushalt entfernen">
                      <IconButton size="small" onClick={() => setUnassignTarget(person)}>
                        <LinkOffIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  ) : (
                    <Tooltip title="Haushalt zuordnen">
                      <IconButton size="small" color="primary" onClick={() => setAssignTarget(person)}>
                        <GroupAddIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                  <Tooltip title={person.archived ? 'Wiederherstellen' : 'Archivieren'}>
                    <IconButton size="small" onClick={() => handleToggleArchive(person.id)}>
                      {person.archived ? <UnarchiveIcon fontSize="small" /> : <ArchiveIcon fontSize="small" />}
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  {onlyUnassigned ? 'Keine Personen ohne Haushalt.' : 'Keine Personen vorhanden.'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <AssignHouseholdDialog
        open={assignTarget !== null}
        person={assignTarget}
        onClose={() => setAssignTarget(null)}
        onAssigned={loadPersons}
      />

      <ConfirmDialog
        open={unassignTarget !== null}
        title="Person aus Haushalt entfernen"
        message={
          unassignTarget
            ? `${unassignTarget.first_name} ${unassignTarget.last_name} aus dem Haushalt „${unassignTarget.household_name ?? ''}“ entfernen? `
              + 'Die Person bleibt erhalten und steht danach ohne Haushalt in der Liste.'
            : ''
        }
        confirmLabel="Entfernen"
        confirmColor="warning"
        busy={unassigning}
        onConfirm={handleUnassign}
        onClose={() => setUnassignTarget(null)}
      />
    </Box>
  );
}

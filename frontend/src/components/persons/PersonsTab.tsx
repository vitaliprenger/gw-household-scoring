import { useState, useEffect, useMemo } from 'react';
import {
  Box, Button, Typography, TextField, FormControlLabel, Switch, Chip, Link, InputAdornment,
  IconButton, Tooltip,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { deDE } from '@mui/x-data-grid/locales';
import SearchIcon from '@mui/icons-material/Search';
import ArchiveIcon from '@mui/icons-material/Archive';
import UnarchiveIcon from '@mui/icons-material/Unarchive';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  getAllPersons, toggleArchivePerson, unassignPerson, deletePerson, deleteUnassignedPersons,
} from '../../api';
import { PersonWithHousehold } from '../../types';
import AssignHouseholdDialog from './AssignHouseholdDialog';
import ConfirmDialog from '../common/ConfirmDialog';
import { zebraGridSx, zebraRowClassName } from '../common/tableStyles';

interface PersonsTabProps {
  onShowHousehold: (householdId: number) => void;
}

function formatDate(val?: string | null): string {
  if (!val) return '—';
  try { return new Date(val).toLocaleDateString('de-DE'); } catch { return String(val); }
}

function formatDateTime(val?: string | null): string {
  if (!val) return '—';
  try {
    const d = new Date(val);
    return d.toLocaleDateString('de-DE') + ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  } catch { return String(val); }
}

export default function PersonsTab({ onShowHousehold }: PersonsTabProps) {
  const [persons, setPersons] = useState<PersonWithHousehold[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [onlyUnassigned, setOnlyUnassigned] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [assignTarget, setAssignTarget] = useState<PersonWithHousehold | null>(null);
  const [unassignTarget, setUnassignTarget] = useState<PersonWithHousehold | null>(null);
  const [unassigning, setUnassigning] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PersonWithHousehold | null>(null);
  const [deleteDeleting, setDeleteDeleting] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  useEffect(() => { loadPersons(); }, [showArchived]);

  const loadPersons = async () => {
    try {
      setPersons(await getAllPersons(showArchived));
    } catch (e) {
      console.error('Failed to load persons', e);
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    let list = persons;
    if (onlyUnassigned) list = list.filter(p => !p.household_id);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(p =>
        `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
        (p.household_name ?? '').toLowerCase().includes(q) ||
        (p.member_number ?? '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [persons, onlyUnassigned, search]);

  const handleToggleArchive = async (personId: number) => {
    try { await toggleArchivePerson(personId); await loadPersons(); }
    catch (e) { console.error('Archive toggle failed', e); }
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

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleteDeleting(true);
    try {
      await deletePerson(deleteTarget.id);
      setDeleteTarget(null);
      await loadPersons();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(msg ?? 'Löschen fehlgeschlagen');
    } finally {
      setDeleteDeleting(false);
    }
  };

  const handleBulkDelete = async () => {
    setBulkDeleting(true);
    try {
      await deleteUnassignedPersons(showArchived);
      setBulkDeleteOpen(false);
      await loadPersons();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(msg ?? 'Löschen fehlgeschlagen');
    } finally {
      setBulkDeleting(false);
    }
  };

  const unassignedCount = useMemo(() => persons.filter(p => !p.household_id).length, [persons]);

  const columns: GridColDef<PersonWithHousehold>[] = useMemo(() => [
    {
      field: 'last_name', headerName: 'Nachname', flex: 1, minWidth: 130,
      renderCell: (params: GridRenderCellParams<PersonWithHousehold>) => (
        <>
          {params.value}
          {params.row.archived && <Chip label="Archiviert" size="small" sx={{ ml: 1 }} color="default" />}
        </>
      ),
    },
    { field: 'first_name', headerName: 'Vorname', flex: 1, minWidth: 120 },
    {
      field: 'birth_date', headerName: 'Geburtsdatum', width: 120,
      valueFormatter: (value: string | undefined) => formatDate(value),
    },
    { field: 'gender', headerName: 'Geschlecht', width: 100 },
    { field: 'member_number', headerName: 'Mitgliedsnr.', width: 120 },
    {
      field: 'individual_import_timestamp', headerName: 'Letzter Import', width: 160,
      valueFormatter: (value: string | undefined) => formatDateTime(value),
    },
    {
      field: 'updated_at', headerName: 'Letzte Bearbeitung', width: 160,
      valueFormatter: (value: string | undefined) => formatDateTime(value),
    },
    {
      field: 'household_name', headerName: 'Haushalt', flex: 1, minWidth: 140,
      renderCell: (params: GridRenderCellParams<PersonWithHousehold>) => {
        if (params.row.household_id && params.row.household_name) {
          return (
            <Link component="button" variant="body2"
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); onShowHousehold(params.row.household_id!); }}
            >
              {params.row.household_name}
            </Link>
          );
        }
        return <Chip label="Kein Haushalt" size="small" color="warning" variant="outlined" />;
      },
    },
    {
      field: 'actions', headerName: 'Aktionen', width: 140,
      sortable: false, filterable: false, disableColumnMenu: true,
      renderCell: (params: GridRenderCellParams<PersonWithHousehold>) => (
        <Box sx={{ whiteSpace: 'nowrap' }}>
          {params.row.household_id ? (
            <Tooltip title="Aus Haushalt entfernen">
              <IconButton size="small" onClick={() => setUnassignTarget(params.row)}>
                <LinkOffIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          ) : (
            <Tooltip title="Haushalt zuordnen">
              <IconButton size="small" color="primary" onClick={() => setAssignTarget(params.row)}>
                <GroupAddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title={params.row.archived ? 'Wiederherstellen' : 'Archivieren'}>
            <IconButton size="small" onClick={() => handleToggleArchive(params.row.id)}>
              {params.row.archived ? <UnarchiveIcon fontSize="small" /> : <ArchiveIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
          {!params.row.household_id && (
            <Tooltip title="Person löschen">
              <IconButton size="small" color="error" onClick={() => setDeleteTarget(params.row)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ], [onShowHousehold]);

  if (loading) return <Typography>Lade Personen...</Typography>;

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
                <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
              ),
            },
          }}
        />
        <FormControlLabel
          control={<Switch checked={onlyUnassigned} onChange={(_, checked) => setOnlyUnassigned(checked)} />}
          label={`Nur ohne Haushalt (${unassignedCount})`}
        />
        <FormControlLabel
          control={<Switch checked={showArchived} onChange={(_, checked) => setShowArchived(checked)} />}
          label="Archivierte anzeigen"
        />
        <Button
          size="small"
          color="error"
          variant="outlined"
          startIcon={<DeleteIcon />}
          disabled={unassignedCount === 0}
          onClick={() => setBulkDeleteOpen(true)}
        >
          Alle ohne Haushalt löschen ({unassignedCount})
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          {filtered.length} von {persons.length} Personen
        </Typography>
      </Box>

      <DataGrid
        rows={filtered}
        columns={columns}
        autoHeight
        density="compact"
        disableRowSelectionOnClick
        initialState={{
          sorting: { sortModel: [{ field: 'last_name', sort: 'asc' }] },
          pagination: { paginationModel: { pageSize: 100 } },
        }}
        pageSizeOptions={[10, 25, 50, 100]}
        getRowClassName={(params) =>
          [zebraRowClassName(params), params.row.archived ? 'archived-row' : ''].filter(Boolean).join(' ')
        }
        sx={{ ...zebraGridSx, '& .archived-row': { opacity: 0.5 } }}
        localeText={deDE.components.MuiDataGrid.defaultProps.localeText}
      />

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
            ? `${unassignTarget.first_name} ${unassignTarget.last_name} aus dem Haushalt „${unassignTarget.household_name ?? ''}" entfernen? `
              + 'Die Person bleibt erhalten und steht danach ohne Haushalt in der Liste.'
            : ''
        }
        confirmLabel="Entfernen"
        confirmColor="warning"
        busy={unassigning}
        onConfirm={handleUnassign}
        onClose={() => setUnassignTarget(null)}
      />

      <ConfirmDialog
        open={bulkDeleteOpen}
        title="Alle Personen ohne Haushalt löschen"
        message={
          `Sollen ${unassignedCount} Personen ohne Haushaltszuordnung endgültig gelöscht werden`
          + (showArchived ? ' (einschließlich archivierter Personen)' : '')
          + '? Diese Aktion kann nicht rückgängig gemacht werden.'
        }
        confirmLabel="Endgültig löschen"
        confirmColor="error"
        busy={bulkDeleting}
        onConfirm={handleBulkDelete}
        onClose={() => setBulkDeleteOpen(false)}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Person löschen"
        message={
          deleteTarget
            ? `Soll ${deleteTarget.first_name} ${deleteTarget.last_name} endgültig gelöscht werden? Diese Aktion kann nicht rückgängig gemacht werden.`
            : ''
        }
        confirmLabel="Endgültig löschen"
        confirmColor="error"
        busy={deleteDeleting}
        onConfirm={handleDelete}
        onClose={() => setDeleteTarget(null)}
      />
    </Box>
  );
}

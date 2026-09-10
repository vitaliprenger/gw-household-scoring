import { useState, useEffect, useMemo } from 'react';
import {
  Box, Typography, TextField, Chip, InputAdornment, IconButton,
  Tooltip, Button, MenuItem, FormControlLabel, Switch, Link,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { deDE } from '@mui/x-data-grid/locales';
import SearchIcon from '@mui/icons-material/Search';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import AddIcon from '@mui/icons-material/Add';
import { getApartments, unassignApartment, deleteApartment } from '../../api';
import { Apartment } from '../../types';
import ApartmentEditDialog from './ApartmentEditDialog';
import AssignApartmentDialog from './AssignApartmentDialog';
import ConfirmDialog from '../common/ConfirmDialog';
import { zebraGridSx, zebraRowClassName } from '../common/tableStyles';

interface ApartmentsTabProps {
  onShowHousehold: (householdId: number) => void;
  onChanged?: () => void;
}

const ALL = '__all__';

export default function ApartmentsTab({ onShowHousehold, onChanged }: ApartmentsTabProps) {
  const [apartments, setApartments] = useState<Apartment[]>([]);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>(ALL);
  const [fundingFilter, setFundingFilter] = useState<string>(ALL);
  const [onlyOccupied, setOnlyOccupied] = useState(false);

  const [editTarget, setEditTarget] = useState<Apartment | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [assignTarget, setAssignTarget] = useState<Apartment | null>(null);
  const [unassignTarget, setUnassignTarget] = useState<Apartment | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Apartment | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { loadApartments(); }, []);

  async function loadApartments() {
    try { setApartments(await getApartments()); }
    catch (e) { console.error('Failed to load apartments', e); }
  }

  function reload() { loadApartments(); onChanged?.(); }

  const categories = useMemo(
    () => [...new Set(apartments.map(a => a.apartment_category).filter(Boolean))].sort() as string[],
    [apartments],
  );
  const fundingTypes = useMemo(
    () => [...new Set(apartments.map(a => a.funding_type))].sort(),
    [apartments],
  );

  const visible = useMemo(() => {
    let list = apartments;
    if (categoryFilter !== ALL) list = list.filter(a => a.apartment_category === categoryFilter);
    if (fundingFilter !== ALL) list = list.filter(a => a.funding_type === fundingFilter);
    if (onlyOccupied) list = list.filter(a => a.household_id);
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(a =>
        a.unit_number.toLowerCase().includes(q) ||
        (a.apartment_category ?? '').toLowerCase().includes(q) ||
        (a.household_name ?? '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [apartments, search, categoryFilter, fundingFilter, onlyOccupied]);

  const occupiedCount = apartments.filter(a => a.household_id).length;

  async function handleUnassign() {
    if (!unassignTarget) return;
    setBusy(true);
    try {
      await unassignApartment(unassignTarget.id);
      setUnassignTarget(null);
      reload();
    } finally { setBusy(false); }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setBusy(true);
    try {
      await deleteApartment(deleteTarget.id);
      setDeleteTarget(null);
      reload();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(msg ?? 'Löschen fehlgeschlagen');
    } finally { setBusy(false); }
  }

  const columns: GridColDef<Apartment>[] = useMemo(() => [
    {
      field: 'unit_number', headerName: 'Wohnung', flex: 1, minWidth: 100,
      renderCell: (params: GridRenderCellParams<Apartment>) => <strong>{params.value}</strong>,
    },
    {
      field: 'size_rooms', headerName: 'Zimmer', width: 80, type: 'number',
      valueFormatter: (value: number | null | undefined) => value ?? '—',
    },
    {
      field: 'min_occupants', headerName: 'mind. Bew.', width: 100, type: 'number',
      valueFormatter: (value: number | null | undefined) => value ?? '—',
    },
    {
      field: 'is_small', headerName: 'Größe', width: 80, type: 'boolean',
      renderCell: (params: GridRenderCellParams<Apartment>) =>
        params.value
          ? <Chip label="klein" size="small" color="info" variant="outlined" />
          : <Typography variant="body2" color="text.secondary">—</Typography>,
    },
    { field: 'apartment_category', headerName: 'Wohnungsart', flex: 1, minWidth: 140 },
    {
      field: 'funding_type', headerName: 'Förderungsart', width: 130,
      renderCell: (params: GridRenderCellParams<Apartment>) => <Chip label={params.value} size="small" />,
    },
    {
      field: 'area_rent', headerName: 'qm mietwirksam', width: 130, type: 'number',
      valueFormatter: (value: number | null | undefined) => value ?? '—',
    },
    {
      field: 'household_name', headerName: 'Bewohnt von', flex: 1, minWidth: 140,
      renderCell: (params: GridRenderCellParams<Apartment>) => {
        if (params.row.household_id) {
          return (
            <Link component="button" variant="body2"
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); onShowHousehold(params.row.household_id!); }}
            >
              {params.row.household_name}
            </Link>
          );
        }
        return <Typography variant="body2" color="text.secondary">frei</Typography>;
      },
    },
    {
      field: 'actions', headerName: 'Aktionen', width: 160,
      sortable: false, filterable: false, disableColumnMenu: true,
      renderCell: (params: GridRenderCellParams<Apartment>) => (
        <Box sx={{ whiteSpace: 'nowrap' }}>
          <Tooltip title="Bearbeiten">
            <IconButton size="small" onClick={() => { setEditTarget(params.row); setEditOpen(true); }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={params.row.household_id ? 'Anderen Haushalt zuordnen' : 'Haushalt zuordnen'}>
            <IconButton size="small" onClick={() => setAssignTarget(params.row)}>
              <GroupAddIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {params.row.household_id && (
            <Tooltip title="Zuordnung lösen">
              <IconButton size="small" onClick={() => setUnassignTarget(params.row)}>
                <LinkOffIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Wohnung löschen">
            <IconButton size="small" color="error" onClick={() => setDeleteTarget(params.row)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], [onShowHousehold]);

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          size="small"
          placeholder="Wohnung, Wohnungsart oder Haushalt suchen"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 320 }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
              ),
            },
          }}
        />
        <TextField
          select size="small" label="Wohnungsart" sx={{ minWidth: 200 }}
          value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <MenuItem value={ALL}>Alle</MenuItem>
          {categories.map(c => <MenuItem key={c} value={c}>{c}</MenuItem>)}
        </TextField>
        <TextField
          select size="small" label="Förderungsart" sx={{ minWidth: 180 }}
          value={fundingFilter} onChange={(e) => setFundingFilter(e.target.value)}
        >
          <MenuItem value={ALL}>Alle</MenuItem>
          {fundingTypes.map(f => <MenuItem key={f} value={f}>{f}</MenuItem>)}
        </TextField>
        <FormControlLabel
          control={<Switch checked={onlyOccupied} onChange={(_, checked) => setOnlyOccupied(checked)} />}
          label="Nur belegte"
        />
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />}
          onClick={() => { setEditTarget(null); setEditOpen(true); }}
        >
          Wohnung anlegen
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {visible.length} von {apartments.length} Wohnungen · {occupiedCount} einem Haushalt zugeordnet
      </Typography>

      <DataGrid
        rows={visible}
        columns={columns}
        autoHeight
        density="compact"
        disableRowSelectionOnClick
        initialState={{
          sorting: { sortModel: [{ field: 'unit_number', sort: 'asc' }] },
          pagination: { paginationModel: { pageSize: 100 } },
        }}
        pageSizeOptions={[10, 25, 50, 100]}
        getRowClassName={zebraRowClassName}
        sx={zebraGridSx}
        localeText={deDE.components.MuiDataGrid.defaultProps.localeText}
      />

      <ApartmentEditDialog
        open={editOpen}
        apartment={editTarget}
        onClose={() => setEditOpen(false)}
        onSaved={reload}
      />

      <AssignApartmentDialog
        open={assignTarget !== null}
        apartment={assignTarget}
        onClose={() => setAssignTarget(null)}
        onAssigned={reload}
      />

      <ConfirmDialog
        open={unassignTarget !== null}
        title="Zuordnung lösen"
        message={
          unassignTarget
            ? `Soll die Zuordnung von "${unassignTarget.household_name}" zur Wohnung ${unassignTarget.unit_number} gelöst werden? Wohnung und Haushalt bleiben erhalten.`
            : ''
        }
        confirmLabel="Zuordnung lösen"
        confirmColor="warning"
        busy={busy}
        onConfirm={handleUnassign}
        onClose={() => setUnassignTarget(null)}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Wohnung löschen"
        message={
          deleteTarget
            ? `Soll die Wohnung ${deleteTarget.unit_number} endgültig gelöscht werden? Bewerbungen auf diese Wohnung werden mit gelöscht.`
            : ''
        }
        confirmLabel="Löschen"
        confirmColor="error"
        busy={busy}
        onConfirm={handleDelete}
        onClose={() => setDeleteTarget(null)}
      />
    </Box>
  );
}

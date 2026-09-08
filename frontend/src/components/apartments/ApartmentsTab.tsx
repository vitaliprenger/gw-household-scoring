import { useState, useEffect, useMemo } from 'react';
import {
    Box, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Typography, TextField, Chip, InputAdornment, TableSortLabel, IconButton,
    Tooltip, Button, MenuItem, FormControlLabel, Switch, Link,
} from '@mui/material';
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

interface ApartmentsTabProps {
    onShowHousehold: (householdId: number) => void;
    /** Wird nach Änderungen aufgerufen, damit Rangliste und Haushalte neu laden. */
    onChanged?: () => void;
}

type SortKey = 'unit_number' | 'floor' | 'apartment_type' | 'size_rooms'
    | 'funding_type' | 'area_rent' | 'min_occupants' | 'household_name';
type SortDir = 'asc' | 'desc';

const ALL = '__all__';

function num(value?: number | null): string {
    return value === null || value === undefined ? '—' : String(value);
}

export default function ApartmentsTab({ onShowHousehold, onChanged }: ApartmentsTabProps) {
    const [apartments, setApartments] = useState<Apartment[]>([]);
    const [search, setSearch] = useState('');
    const [categoryFilter, setCategoryFilter] = useState<string>(ALL);
    const [fundingFilter, setFundingFilter] = useState<string>(ALL);
    const [onlyOccupied, setOnlyOccupied] = useState(false);
    const [sortKey, setSortKey] = useState<SortKey>('unit_number');
    const [sortDir, setSortDir] = useState<SortDir>('asc');

    const [editTarget, setEditTarget] = useState<Apartment | null>(null);
    const [editOpen, setEditOpen] = useState(false);
    const [assignTarget, setAssignTarget] = useState<Apartment | null>(null);
    const [unassignTarget, setUnassignTarget] = useState<Apartment | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<Apartment | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        loadApartments();
    }, []);

    async function loadApartments() {
        try {
            setApartments(await getApartments());
        } catch (e) {
            console.error('Failed to load apartments', e);
        }
    }

    function reload() {
        loadApartments();
        onChanged?.();
    }

    const categories = useMemo(
        () => [...new Set(apartments.map(a => a.apartment_category).filter(Boolean))].sort() as string[],
        [apartments],
    );
    const fundingTypes = useMemo(
        () => [...new Set(apartments.map(a => a.funding_type))].sort(),
        [apartments],
    );

    function handleSort(key: SortKey) {
        if (sortKey === key) {
            setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
        } else {
            setSortKey(key);
            setSortDir('asc');
        }
    }

    const visible = useMemo(() => {
        let list = apartments;
        if (categoryFilter !== ALL) list = list.filter(a => a.apartment_category === categoryFilter);
        if (fundingFilter !== ALL) list = list.filter(a => a.funding_type === fundingFilter);
        if (onlyOccupied) list = list.filter(a => a.household_id);
        const q = search.trim().toLowerCase();
        if (q) {
            list = list.filter(a =>
                a.unit_number.toLowerCase().includes(q) ||
                (a.floor ?? '').toLowerCase().includes(q) ||
                (a.apartment_type ?? '').toLowerCase().includes(q) ||
                (a.household_name ?? '').toLowerCase().includes(q)
            );
        }
        const factor = sortDir === 'asc' ? 1 : -1;
        return [...list].sort((a, b) => {
            const av = a[sortKey];
            const bv = b[sortKey];
            if (av === bv) return a.unit_number.localeCompare(b.unit_number);
            if (av === null || av === undefined) return 1;
            if (bv === null || bv === undefined) return -1;
            if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * factor;
            return String(av).localeCompare(String(bv), 'de', { numeric: true }) * factor;
        });
    }, [apartments, search, categoryFilter, fundingFilter, onlyOccupied, sortKey, sortDir]);

    const occupiedCount = apartments.filter(a => a.household_id).length;

    async function handleUnassign() {
        if (!unassignTarget) return;
        setBusy(true);
        try {
            await unassignApartment(unassignTarget.id);
            setUnassignTarget(null);
            reload();
        } finally {
            setBusy(false);
        }
    }

    async function handleDelete() {
        if (!deleteTarget) return;
        setBusy(true);
        try {
            await deleteApartment(deleteTarget.id);
            setDeleteTarget(null);
            reload();
        } finally {
            setBusy(false);
        }
    }

    const columns: { key: SortKey; label: string; align?: 'right' }[] = [
        { key: 'unit_number', label: 'Wohnung' },
        { key: 'floor', label: 'Etage' },
        { key: 'apartment_type', label: 'Typ' },
        { key: 'size_rooms', label: 'Zimmer', align: 'right' },
        { key: 'funding_type', label: 'Förderungsart' },
        { key: 'area_rent', label: 'qm mietwirksam', align: 'right' },
        { key: 'min_occupants', label: 'mind. Bew.', align: 'right' },
        { key: 'household_name', label: 'Bewohnt von' },
    ];

    return (
        <Box>
            <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                <TextField
                    size="small"
                    placeholder="Wohnung, Etage, Typ oder Haushalt suchen"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    sx={{ minWidth: 320 }}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
                        ),
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
                    control={
                        <Switch
                            checked={onlyOccupied}
                            onChange={(_, checked) => setOnlyOccupied(checked)}
                        />
                    }
                    label="Nur belegte"
                />
                <Box sx={{ flexGrow: 1 }} />
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => { setEditTarget(null); setEditOpen(true); }}
                >
                    Wohnung anlegen
                </Button>
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {visible.length} von {apartments.length} Wohnungen · {occupiedCount} einem Haushalt zugeordnet
            </Typography>

            <TableContainer component={Paper}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            {columns.map(col => (
                                <TableCell key={col.key} align={col.align}>
                                    <TableSortLabel
                                        active={sortKey === col.key}
                                        direction={sortKey === col.key ? sortDir : 'asc'}
                                        onClick={() => handleSort(col.key)}
                                    >
                                        {col.label}
                                    </TableSortLabel>
                                </TableCell>
                            ))}
                            <TableCell align="right">Aktionen</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {visible.map((apt) => (
                            <TableRow key={apt.id} hover>
                                <TableCell><strong>{apt.unit_number}</strong></TableCell>
                                <TableCell>{apt.floor ?? '—'}</TableCell>
                                <TableCell>
                                    {apt.apartment_type ?? '—'}
                                    {apt.apartment_category && apt.apartment_category !== 'Standard Wohnungstypen' && (
                                        <Chip label={apt.apartment_category} size="small" sx={{ ml: 1 }} />
                                    )}
                                </TableCell>
                                <TableCell align="right">{num(apt.size_rooms)}</TableCell>
                                <TableCell>
                                    <Chip label={apt.funding_type} size="small" />
                                    {apt.wbs_raw && apt.wbs_raw !== 'N' && (
                                        <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                                            {apt.wbs_raw}
                                        </Typography>
                                    )}
                                </TableCell>
                                <TableCell align="right">{num(apt.area_rent)}</TableCell>
                                <TableCell align="right">{num(apt.min_occupants)}</TableCell>
                                <TableCell>
                                    {apt.household_id ? (
                                        <Link
                                            component="button"
                                            variant="body2"
                                            onClick={() => onShowHousehold(apt.household_id!)}
                                        >
                                            {apt.household_name}
                                        </Link>
                                    ) : (
                                        <Typography variant="body2" color="text.secondary">frei</Typography>
                                    )}
                                </TableCell>
                                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                                    <Tooltip title="Bearbeiten">
                                        <IconButton
                                            size="small"
                                            onClick={() => { setEditTarget(apt); setEditOpen(true); }}
                                        >
                                            <EditIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title={apt.household_id ? 'Anderen Haushalt zuordnen' : 'Haushalt zuordnen'}>
                                        <IconButton size="small" onClick={() => setAssignTarget(apt)}>
                                            <GroupAddIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                    {apt.household_id && (
                                        <Tooltip title="Zuordnung lösen">
                                            <IconButton size="small" onClick={() => setUnassignTarget(apt)}>
                                                <LinkOffIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    )}
                                    <Tooltip title="Wohnung löschen">
                                        <IconButton size="small" color="error" onClick={() => setDeleteTarget(apt)}>
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                </TableCell>
                            </TableRow>
                        ))}
                        {visible.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={columns.length + 1} align="center">
                                    Keine Wohnungen gefunden.
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

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

import { useState, useEffect, useMemo } from 'react';
import {
    Box, Typography, TextField, Chip, InputAdornment, IconButton, Tooltip,
    Button, MenuItem, Link, Paper, Stack,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { deDE } from '@mui/x-data-grid/locales';
import SearchIcon from '@mui/icons-material/Search';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
    Application, ApplicationKind, Household, JokerWaitEntry,
    APPLICATION_KIND_LABELS, APPLICATION_STATUS_LABELS,
} from '../../types';
import { getApplications, deleteApplication, getJokerWaitlist, getHouseholds } from '../../api';
import ApplicationEditDialog from './ApplicationEditDialog';
import ConfirmDialog from '../common/ConfirmDialog';
import { wishLabel, formatDate } from './wishes';
import { zebraGridSx, zebraRowClassName } from '../common/tableStyles';

interface ApplicationsTabProps {
    onShowHousehold: (householdId: number) => void;
    onChanged?: () => void;
}

const ALL = '__all__';

const KIND_COLOR: Record<ApplicationKind, 'default' | 'primary' | 'secondary'> = {
    wartepool: 'default',
    wechselwunsch: 'primary',
    joker: 'secondary',
};

const STATUS_COLOR: Record<string, 'warning' | 'success' | 'default'> = {
    offen: 'warning',
    erfuellt: 'success',
    zurueckgezogen: 'default',
};

/** Sonderfall-Kennzeichen mit der Begründung als Tooltip. */
function SpecialCaseMark({ note }: { note?: string | null }) {
    return (
        <Tooltip title={note || 'Sonderfall beachten'}>
            <WarningAmberIcon color="warning" fontSize="small" sx={{ verticalAlign: 'middle' }} />
        </Tooltip>
    );
}

export default function ApplicationsTab({ onShowHousehold, onChanged }: ApplicationsTabProps) {
    const [applications, setApplications] = useState<Application[]>([]);
    const [households, setHouseholds] = useState<Household[]>([]);
    const [joker, setJoker] = useState<JokerWaitEntry[]>([]);
    const [search, setSearch] = useState('');
    const [kindFilter, setKindFilter] = useState<string>(ALL);
    // Offene Bewerbungen sind der Normalfall der Pflege; die Historie steht hinter dem Filter.
    const [statusFilter, setStatusFilter] = useState<string>('offen');

    const [editTarget, setEditTarget] = useState<Application | null>(null);
    const [editOpen, setEditOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Application | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => { load(); }, []);

    async function load() {
        try {
            const [apps, hhs, jokerList] = await Promise.all([
                getApplications({ include_archived: true }),
                getHouseholds(),
                getJokerWaitlist(),
            ]);
            setApplications(apps);
            setHouseholds(hhs.sort((a, b) => a.name.localeCompare(b.name, 'de')));
            setJoker(jokerList);
        } catch (e) {
            console.error('Failed to load applications', e);
        }
    }

    function reload() { load(); onChanged?.(); }

    const visible = useMemo(() => {
        let list = applications;
        if (kindFilter !== ALL) list = list.filter((a) => a.kind === kindFilter);
        if (statusFilter !== ALL) list = list.filter((a) => a.status === statusFilter);
        const q = search.trim().toLowerCase();
        if (q) {
            list = list.filter((a) =>
                (a.household_name ?? '').toLowerCase().includes(q) ||
                (a.note ?? '').toLowerCase().includes(q) ||
                (a.special_case_note ?? '').toLowerCase().includes(q) ||
                (a.current_apartment_unit ?? '').toLowerCase().includes(q) ||
                a.wishes.some((w) => wishLabel(w).toLowerCase().includes(q)));
        }
        return list;
    }, [applications, kindFilter, statusFilter, search]);

    const columns: GridColDef<Application>[] = [
        {
            field: 'household_name', headerName: 'Haushalt', flex: 1, minWidth: 180,
            renderCell: (params: GridRenderCellParams<Application>) => (
                <>
                    <Link
                        component="button" underline="hover" type="button"
                        onClick={() => onShowHousehold(params.row.household_id)}
                    >
                        {params.value || '—'}
                    </Link>
                    {params.row.special_case && (
                        <Box component="span" sx={{ ml: 1 }}>
                            <SpecialCaseMark note={params.row.special_case_note} />
                        </Box>
                    )}
                </>
            ),
        },
        {
            field: 'kind', headerName: 'Typ', width: 140,
            renderCell: (params: GridRenderCellParams<Application>) => (
                <Chip
                    size="small"
                    label={APPLICATION_KIND_LABELS[params.row.kind]}
                    color={KIND_COLOR[params.row.kind]}
                />
            ),
        },
        {
            field: 'wishes', headerName: 'Wunsch', flex: 1, minWidth: 200, sortable: false,
            renderCell: (params: GridRenderCellParams<Application>) => (
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                    {params.row.wishes.length === 0
                        ? <Typography variant="body2" color="text.secondary">—</Typography>
                        : params.row.wishes.map((w, i) => (
                            <Chip key={i} size="small" variant="outlined" label={wishLabel(w)} />
                        ))}
                </Box>
            ),
        },
        {
            field: 'requested_at', headerName: 'Wunsch seit', width: 120,
            valueFormatter: (value: string | undefined) => formatDate(value),
        },
        {
            field: 'status', headerName: 'Status', width: 130,
            renderCell: (params: GridRenderCellParams<Application>) => (
                <Tooltip title={params.row.status_note || ''}>
                    <Chip
                        size="small"
                        label={APPLICATION_STATUS_LABELS[params.row.status]}
                        color={STATUS_COLOR[params.row.status] ?? 'default'}
                    />
                </Tooltip>
            ),
        },
        // "Aktuelle Wohnung" und "Neue Wohnung" tragen keine eigene Information:
        // die aktuelle Wohnung steht am Haushalt (ein Klick auf den Namen), die
        // neue entsteht beim Einzug von selbst. Sie bleiben als Daten erhalten
        // (Suche, Haushaltsdetail), kosten hier aber nur Breite.
        {
            field: 'note', headerName: 'Kommentar', flex: 1.5, minWidth: 220,
            renderCell: (params: GridRenderCellParams<Application>) => (
                <Tooltip title={params.value || ''}>
                    <Typography variant="body2" noWrap>{params.value || '—'}</Typography>
                </Tooltip>
            ),
        },
        {
            field: 'actions', headerName: '', width: 96, sortable: false, filterable: false,
            renderCell: (params: GridRenderCellParams<Application>) => (
                <>
                    <Tooltip title="Bearbeiten">
                        <IconButton
                            size="small"
                            onClick={() => { setEditTarget(params.row); setEditOpen(true); }}
                        >
                            <EditIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Löschen">
                        <IconButton size="small" onClick={() => setDeleteTarget(params.row)}>
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </>
            ),
        },
    ];

    async function handleDelete() {
        if (!deleteTarget) return;
        setBusy(true);
        try {
            await deleteApplication(deleteTarget.id);
            setDeleteTarget(null);
            reload();
        } finally {
            setBusy(false);
        }
    }

    return (
        <Box>
            <Box sx={{ display: 'flex', mb: 2, alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                <TextField
                    size="small"
                    placeholder="Haushalt, Wunsch oder Kommentar suchen"
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
                    select size="small" label="Typ" value={kindFilter}
                    onChange={(e) => setKindFilter(e.target.value)} sx={{ minWidth: 170 }}
                >
                    <MenuItem value={ALL}>Alle</MenuItem>
                    {Object.entries(APPLICATION_KIND_LABELS).map(([value, label]) => (
                        <MenuItem key={value} value={value}>{label}</MenuItem>
                    ))}
                </TextField>
                <TextField
                    select size="small" label="Status" value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)} sx={{ minWidth: 170 }}
                >
                    <MenuItem value={ALL}>Alle</MenuItem>
                    {Object.entries(APPLICATION_STATUS_LABELS).map(([value, label]) => (
                        <MenuItem key={value} value={value}>{label}</MenuItem>
                    ))}
                </TextField>
                <Box sx={{ flexGrow: 1 }} />
                <Button
                    variant="contained" startIcon={<AddIcon />}
                    onClick={() => { setEditTarget(null); setEditOpen(true); }}
                >
                    Bewerbung anlegen
                </Button>
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {visible.length} von {applications.length} Bewerbungen. Erfüllte und
                zurückgezogene Bewerbungen bleiben als Historie erhalten.
            </Typography>

            <DataGrid
                rows={visible}
                columns={columns}
                autoHeight
                density="compact"
                disableRowSelectionOnClick
                initialState={{
                    sorting: { sortModel: [{ field: 'requested_at', sort: 'asc' }] },
                    pagination: { paginationModel: { pageSize: 100 } },
                }}
                pageSizeOptions={[10, 25, 50, 100]}
                getRowClassName={zebraRowClassName}
                sx={zebraGridSx}
                localeText={deDE.components.MuiDataGrid.defaultProps.localeText}
            />

            <Paper sx={{ mt: 4, p: 2 }}>
                <Typography variant="h6" gutterBottom>Joker-Warteliste</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Joker-Zimmer können nur von bestehenden Haushalten angemietet werden und
                    bilden keine Wohnungskategorie. Die Vergabe folgt der Reihenfolge, in der
                    der Wunsch geäußert wurde.
                </Typography>
                {joker.length === 0 ? (
                    <Typography color="text.secondary">Keine offenen Joker-Bewerbungen.</Typography>
                ) : (
                    <Stack spacing={1}>
                        {joker.map((entry) => (
                            <Box
                                key={entry.application_id}
                                sx={{ display: 'flex', gap: 2, alignItems: 'center' }}
                            >
                                <Typography sx={{ width: 28 }} color="text.secondary">
                                    {entry.rank}.
                                </Typography>
                                <Link
                                    component="button" underline="hover" type="button"
                                    onClick={() => onShowHousehold(entry.household_id)}
                                >
                                    {entry.household_name}
                                </Link>
                                {entry.special_case && <SpecialCaseMark note={entry.special_case_note} />}
                                <Box sx={{ flexGrow: 1 }} />
                                <Typography variant="body2" color="text.secondary">
                                    {entry.current_apartment_unit || '—'}
                                </Typography>
                                <Typography variant="body2">
                                    seit {formatDate(entry.requested_at)}
                                </Typography>
                            </Box>
                        ))}
                    </Stack>
                )}
            </Paper>

            <ApplicationEditDialog
                open={editOpen}
                application={editTarget}
                households={households}
                onClose={() => { setEditOpen(false); setEditTarget(null); }}
                onSaved={reload}
            />

            <ConfirmDialog
                open={!!deleteTarget}
                title="Bewerbung löschen?"
                message={`Die Bewerbung von "${deleteTarget?.household_name ?? ''}" wird endgültig `
                    + 'gelöscht. Soll die Bewerbung nur nicht mehr gelten, setze stattdessen den '
                    + 'Status auf "zurückgezogen" — dann bleibt sie als Historie erhalten.'}
                confirmLabel="Löschen"
                busy={busy}
                onConfirm={handleDelete}
                onClose={() => setDeleteTarget(null)}
            />
        </Box>
    );
}

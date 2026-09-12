import { useState, useEffect } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Typography, Grid, TextField, Select, MenuItem,
    FormControl, InputLabel, Switch, FormControlLabel, Divider,
    Box, Alert, CircularProgress, Chip, Tooltip, IconButton, Stack,
} from '@mui/material';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
    Application, Household, Person,
    APPLICATION_KIND_LABELS, APPLICATION_STATUS_LABELS,
} from '../../types';
import {
    getHousehold, updateHousehold, updatePerson, toggleArchiveHousehold, unassignPerson,
    deleteHousehold, getApplications,
} from '../../api';
import PersonCard from './PersonCard';
import AddPersonDialog from './AddPersonDialog';
import ConfirmDialog from '../common/ConfirmDialog';
import ApplicationEditDialog from '../applications/ApplicationEditDialog';
import { wishLabel, formatDate } from '../applications/wishes';

interface HouseholdDetailDialogProps {
    open: boolean;
    householdId: number | null;
    onClose: () => void;
    onSaved: () => void;
}

const WBS_OPTIONS = ['', 'kein WBS', 'WBS A', 'WBS B'];

export default function HouseholdDetailDialog({
    open, householdId, onClose, onSaved,
}: HouseholdDetailDialogProps) {
    const [household, setHousehold] = useState<Household | null>(null);
    const [editing, setEditing] = useState(false);
    const [editHH, setEditHH] = useState<Partial<Household>>({});
    const [editPersons, setEditPersons] = useState<Record<number, Partial<Person>>>({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [addPersonOpen, setAddPersonOpen] = useState(false);
    const [removeTarget, setRemoveTarget] = useState<Person | null>(null);
    const [removing, setRemoving] = useState(false);
    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [applications, setApplications] = useState<Application[]>([]);
    const [applicationTarget, setApplicationTarget] = useState<Application | null>(null);
    const [applicationOpen, setApplicationOpen] = useState(false);

    useEffect(() => {
        if (open && householdId) {
            setLoading(true);
            setEditing(false);
            setError('');
            getHousehold(householdId)
                .then((hh) => {
                    setHousehold(hh);
                    setEditHH({});
                    setEditPersons({});
                })
                .catch(() => setError('Haushalt konnte nicht geladen werden'))
                .finally(() => setLoading(false));
            loadApplications(householdId);
        }
    }, [open, householdId]);

    function loadApplications(id: number) {
        getApplications({ household_id: id, include_archived: true })
            .then(setApplications)
            .catch(() => setApplications([]));
    }

    if (!open) return null;

    const currentHH = household
        ? { ...household, ...editHH }
        : null;

    const nameError = editing && (currentHH?.name ?? '').trim() === '';

    function handleHHChange(field: string, value: string | number | boolean | string[]) {
        setEditHH((prev) => ({ ...prev, [field]: value }));
    }

    function handlePersonChange(personId: number, field: string, value: string | boolean) {
        setEditPersons((prev) => ({
            ...prev,
            [personId]: { ...prev[personId], [field]: value },
        }));
    }

    async function handleSave() {
        if (!household) return;
        const payload = { ...editHH };
        if (payload.name !== undefined) {
            const trimmedName = payload.name.trim();
            if (!trimmedName) {
                setError('Haushaltsname darf nicht leer sein');
                return;
            }
            payload.name = trimmedName;
        }
        setSaving(true);
        setError('');
        try {
            if (Object.keys(payload).length > 0) {
                await updateHousehold(household.id, payload);
            }
            for (const [idStr, data] of Object.entries(editPersons)) {
                if (Object.keys(data).length > 0) {
                    await updatePerson(Number(idStr), data);
                }
            }
            setEditing(false);
            onSaved();
            const refreshed = await getHousehold(household.id);
            setHousehold(refreshed);
            setEditHH({});
            setEditPersons({});
        } catch {
            setError('Speichern fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    async function handleToggleArchive() {
        if (!household) return;
        setSaving(true);
        try {
            await toggleArchiveHousehold(household.id);
            onSaved();
            const refreshed = await getHousehold(household.id);
            setHousehold(refreshed);
        } catch {
            setError('Archivierung fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        if (!household) return;
        setDeleting(true);
        try {
            await deleteHousehold(household.id);
            setDeleteConfirmOpen(false);
            onSaved();
            onClose();
        } catch {
            setError('Löschen fehlgeschlagen');
        } finally {
            setDeleting(false);
        }
    }

    async function reloadHousehold() {
        if (!householdId) return;
        const refreshed = await getHousehold(householdId);
        setHousehold(refreshed);
    }

    async function handleRemovePerson() {
        if (!removeTarget) return;
        setRemoving(true);
        setError('');
        try {
            await unassignPerson(removeTarget.id);
            setEditPersons((prev) => {
                const rest = { ...prev };
                delete rest[removeTarget.id];
                return rest;
            });
            setRemoveTarget(null);
            onSaved();
            await reloadHousehold();
        } catch {
            setError('Person konnte nicht entfernt werden');
        } finally {
            setRemoving(false);
        }
    }

    function handleCancel() {
        setEditing(false);
        setEditHH({});
        setEditPersons({});
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

    const mergedPersons: Person[] = (household?.people ?? []).map((p) => ({
        ...p,
        ...editPersons[p.id],
    }));

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1, mr: 2 }}>
                    {editing ? (
                        <TextField
                            label="Haushaltsname"
                            size="small"
                            fullWidth
                            value={currentHH?.name ?? ''}
                            error={nameError}
                            helperText={nameError ? 'Haushaltsname darf nicht leer sein' : undefined}
                            onChange={(e) => handleHHChange('name', e.target.value)}
                            sx={{ maxWidth: 420 }}
                        />
                    ) : (
                        currentHH?.name ?? 'Haushalt'
                    )}
                    {currentHH?.archived && <Chip label="Archiviert" size="small" color="default" />}
                </Box>
                {!editing && (
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                            variant="outlined"
                            size="small"
                            color="error"
                            onClick={() => setDeleteConfirmOpen(true)}
                            disabled={saving}
                        >
                            Löschen
                        </Button>
                        <Button
                            variant="outlined"
                            size="small"
                            color={currentHH?.archived ? 'success' : 'warning'}
                            onClick={handleToggleArchive}
                            disabled={saving}
                        >
                            {currentHH?.archived ? 'Wiederherstellen' : 'Archivieren'}
                        </Button>
                        <Button variant="outlined" size="small" onClick={() => setEditing(true)}>
                            Bearbeiten
                        </Button>
                    </Box>
                )}
            </DialogTitle>
            <DialogContent dividers>
                {loading && <CircularProgress />}
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {currentHH && !loading && (
                    <>
                        <Typography variant="h6" gutterBottom>Haushaltsdaten</Typography>
                        <Grid container spacing={2} sx={{ mb: 3 }}>
                            <GridField label="Engagement (0–1)" value={String(currentHH.engagement_score)} editing={editing}
                                onChange={(v) => handleHHChange('engagement_score', Math.min(1, Math.max(0, parseFloat(v) || 0)))} />
                            <GridField label="Kulturelle Vielfalt (0–1)" value={String(currentHH.cultural_diversity_score)} editing={editing}
                                onChange={(v) => handleHHChange('cultural_diversity_score', Math.min(1, Math.max(0, parseFloat(v) || 0)))} />
                            <GridField label="Besondere Lebenslagen (0–1)" value={String(currentHH.special_needs_score)} editing={editing}
                                onChange={(v) => handleHHChange('special_needs_score', Math.min(1, Math.max(0, parseFloat(v) || 0)))} />
                            <Grid size={{ xs: 6, sm: 4 }}>
                                {editing ? (
                                    <FormControl size="small" fullWidth>
                                        <InputLabel>WBS-Status</InputLabel>
                                        <Select value={currentHH.wbs_status ?? ''} label="WBS-Status"
                                            onChange={(e) => handleHHChange('wbs_status', e.target.value)}>
                                            {WBS_OPTIONS.map((o) => <MenuItem key={o} value={o}>{o || '—'}</MenuItem>)}
                                        </Select>
                                    </FormControl>
                                ) : (
                                    <FieldDisplay label="WBS-Status" value={currentHH.wbs_status} />
                                )}
                            </Grid>
                            <GridField label="Haustiere (Anzahl)" value={String(currentHH.pets_count)} editing={editing}
                                onChange={(v) => handleHHChange('pets_count', parseInt(v) || 0)} />
                            <GridField label="Haustiere (Info)" value={currentHH.pets_info ?? ''} editing={editing}
                                onChange={(v) => handleHHChange('pets_info', v)} />
                            <Grid size={{ xs: 6, sm: 4 }}>
                                {editing ? (
                                    <FormControlLabel
                                        control={<Switch checked={currentHH.wheelchair_accessible}
                                            onChange={(e) => handleHHChange('wheelchair_accessible', e.target.checked)} />}
                                        label="Rollstuhlgerecht?" />
                                ) : (
                                    <FieldDisplay label="Rollstuhlgerecht?" value={currentHH.wheelchair_accessible ? 'Ja' : 'Nein'} />
                                )}
                            </Grid>
                            <GridField label="Finanzielle Rahmenbedingungen" value={currentHH.financial_status ?? ''} editing={editing}
                                onChange={(v) => handleHHChange('financial_status', v)} />
                            <Grid size={{ xs: 6, sm: 4 }}>
                                <FieldDisplay
                                    label="Zugeordnete Wohnung"
                                    value={currentHH.assigned_apartment_unit ?? undefined}
                                />
                            </Grid>
                            <GridField label="Deklarierte Mitglieder" value={currentHH.household_member_count != null ? String(currentHH.household_member_count) : ''} editing={editing}
                                onChange={(v) => handleHHChange('household_member_count', parseInt(v) || 0)} />
                        </Grid>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 2 }}>
                            <FieldDisplay label="Import-Quelle" value={currentHH.import_source} />
                            <FieldDisplay label="Letzter Import" value={formatDateTime(currentHH.import_timestamp)} />
                            <FieldDisplay label="Letzte Bearbeitung" value={formatDateTime(currentHH.updated_at)} />
                            <FieldDisplay label="Grundpunktzahl (ohne Wohnraumausnutzung)" value={currentHH.total_score.toFixed(2)} />
                        </Box>

                        <Divider sx={{ my: 2 }} />
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography variant="h6">
                                Bewerbungen ({applications.length})
                            </Typography>
                            <Button
                                variant="outlined"
                                size="small"
                                startIcon={<AddIcon />}
                                onClick={() => { setApplicationTarget(null); setApplicationOpen(true); }}
                                disabled={editing}
                            >
                                Bewerbung anlegen
                            </Button>
                        </Box>
                        {applications.length === 0 ? (
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                Dieser Haushalt hat keine Bewerbung. Ohne offene Bewerbung
                                erscheint er in keiner Rangliste.
                            </Typography>
                        ) : (
                            <Stack spacing={1} sx={{ mb: 1 }}>
                                {applications.map((application) => (
                                    <Box
                                        key={application.id}
                                        sx={{
                                            display: 'flex', alignItems: 'center', gap: 1,
                                            flexWrap: 'wrap', p: 1,
                                            border: 1, borderColor: 'divider', borderRadius: 1,
                                        }}
                                    >
                                        <Chip size="small" label={APPLICATION_KIND_LABELS[application.kind]} />
                                        <Chip
                                            size="small"
                                            color={application.status === 'offen' ? 'warning' : 'default'}
                                            label={APPLICATION_STATUS_LABELS[application.status]}
                                        />
                                        {application.wishes.map((wish, i) => (
                                            <Chip key={i} size="small" variant="outlined" label={wishLabel(wish)} />
                                        ))}
                                        {application.wishes.length === 0 && (
                                            <Typography variant="body2" color="text.secondary">
                                                kein Wunsch gepflegt
                                            </Typography>
                                        )}
                                        {application.special_case && (
                                            <Tooltip title={application.special_case_note || 'Sonderfall beachten'}>
                                                <WarningAmberIcon color="warning" fontSize="small" />
                                            </Tooltip>
                                        )}
                                        <Box sx={{ flexGrow: 1 }} />
                                        <Typography variant="body2" color="text.secondary">
                                            seit {formatDate(application.requested_at)}
                                        </Typography>
                                        {application.fulfilled_apartment_unit && (
                                            <Typography variant="body2">
                                                → {application.fulfilled_apartment_unit}
                                            </Typography>
                                        )}
                                        <Tooltip title="Bearbeiten">
                                            <span>
                                                <IconButton
                                                    size="small"
                                                    disabled={editing}
                                                    onClick={() => {
                                                        setApplicationTarget(application);
                                                        setApplicationOpen(true);
                                                    }}
                                                >
                                                    <EditIcon fontSize="small" />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                    </Box>
                                ))}
                            </Stack>
                        )}

                        <Divider sx={{ my: 2 }} />
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography variant="h6">
                                Personen ({mergedPersons.length})
                            </Typography>
                            <Button
                                variant="outlined"
                                size="small"
                                startIcon={<PersonAddIcon />}
                                onClick={() => setAddPersonOpen(true)}
                                disabled={editing}
                            >
                                Person hinzufügen
                            </Button>
                        </Box>
                        {mergedPersons.length === 0 && (
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                Diesem Haushalt ist noch keine Person zugeordnet.
                            </Typography>
                        )}
                        {mergedPersons.map((person) => (
                            <PersonCard
                                key={person.id}
                                person={person}
                                editing={editing}
                                onChange={handlePersonChange}
                                onRemove={editing ? undefined : setRemoveTarget}
                            />
                        ))}
                    </>
                )}
            </DialogContent>
            <DialogActions>
                {editing ? (
                    <>
                        <Button onClick={handleCancel}>Abbrechen</Button>
                        <Button variant="contained" onClick={handleSave} disabled={saving || nameError}>
                            {saving ? 'Speichere...' : 'Speichern'}
                        </Button>
                    </>
                ) : (
                    <Button onClick={onClose}>Schließen</Button>
                )}
            </DialogActions>

            <ApplicationEditDialog
                open={applicationOpen}
                application={applicationTarget}
                households={[]}
                fixedHousehold={household}
                onClose={() => { setApplicationOpen(false); setApplicationTarget(null); }}
                onSaved={() => {
                    if (householdId) loadApplications(householdId);
                    onSaved();
                }}
            />

            <AddPersonDialog
                open={addPersonOpen}
                householdId={householdId}
                householdName={currentHH?.name}
                onClose={() => setAddPersonOpen(false)}
                onAdded={async () => {
                    onSaved();
                    await reloadHousehold();
                }}
            />

            <ConfirmDialog
                open={deleteConfirmOpen}
                title="Haushalt löschen"
                message={
                    household
                        ? `Soll der Haushalt „${household.name}" endgültig gelöscht werden? `
                          + `Alle ${household.people.length} zugehörigen Personen und Bewerbungen werden mitgelöscht.`
                        : ''
                }
                confirmLabel="Endgültig löschen"
                confirmColor="error"
                busy={deleting}
                onConfirm={handleDelete}
                onClose={() => setDeleteConfirmOpen(false)}
            />

            <ConfirmDialog
                open={removeTarget !== null}
                title="Person aus Haushalt entfernen"
                message={
                    removeTarget
                        ? `${removeTarget.first_name} ${removeTarget.last_name} aus diesem Haushalt entfernen? `
                          + 'Die Person bleibt erhalten und ist danach keinem Haushalt zugeordnet.'
                        : ''
                }
                confirmLabel="Entfernen"
                confirmColor="warning"
                busy={removing}
                onConfirm={handleRemovePerson}
                onClose={() => setRemoveTarget(null)}
            />
        </Dialog>
    );
}

function GridField({ label, value, editing, onChange }: {
    label: string; value: string; editing: boolean; onChange: (v: string) => void;
}) {
    return (
        <Grid size={{ xs: 6, sm: 4 }}>
            {editing ? (
                <TextField label={label} size="small" fullWidth value={value} onChange={(e) => onChange(e.target.value)} />
            ) : (
                <FieldDisplay label={label} value={value} />
            )}
        </Grid>
    );
}

function FieldDisplay({ label, value }: { label: string; value?: string | null }) {
    return (
        <Box>
            <Typography variant="caption" color="text.secondary">{label}</Typography>
            <Typography variant="body2">{value || '—'}</Typography>
        </Box>
    );
}

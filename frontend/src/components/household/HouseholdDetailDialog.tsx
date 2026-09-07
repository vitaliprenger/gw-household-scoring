import { useState, useEffect } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Typography, Grid, TextField, Select, MenuItem,
    FormControl, InputLabel, Switch, FormControlLabel, Divider,
    Box, Alert, CircularProgress, Checkbox, ListItemText, Chip,
    OutlinedInput,
} from '@mui/material';
import { Household, Person } from '../../types';
import { getHousehold, updateHousehold, updatePerson } from '../../api';
import PersonCard from './PersonCard';

interface HouseholdDetailDialogProps {
    open: boolean;
    householdId: number | null;
    onClose: () => void;
    onSaved: () => void;
}

const WBS_OPTIONS = ['', 'kein WBS', 'WBS Einkommensgruppe A', 'WBS Einkommensgruppe B'];

const APARTMENT_TYPE_OPTIONS = [
    'Standard Wohnungstypen',
    'Clusterwohnung',
    'Ausbauwohnung',
    'Atelierwohnung',
    'Gartencluster',
];

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
        }
    }, [open, householdId]);

    if (!open) return null;

    const currentHH = household
        ? { ...household, ...editHH }
        : null;

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
        setSaving(true);
        setError('');
        try {
            if (Object.keys(editHH).length > 0) {
                await updateHousehold(household.id, editHH);
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

    function handleCancel() {
        setEditing(false);
        setEditHH({});
        setEditPersons({});
    }

    function formatDate(val?: string): string {
        if (!val) return '—';
        try {
            return new Date(val).toLocaleDateString('de-DE');
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
                {currentHH?.name ?? 'Haushalt'}
                {!editing && (
                    <Button variant="outlined" size="small" onClick={() => setEditing(true)}>
                        Bearbeiten
                    </Button>
                )}
            </DialogTitle>
            <DialogContent dividers>
                {loading && <CircularProgress />}
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {currentHH && !loading && (
                    <>
                        <Typography variant="h6" gutterBottom>Haushaltsdaten</Typography>
                        <Grid container spacing={2} sx={{ mb: 3 }}>
                            <GridField label="Mitglied seit" value={formatDate(currentHH.member_since)} editing={editing}
                                onChange={(v) => handleHHChange('member_since', v)} />
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
                            <GridField label="Gewünschte Wohnungsgröße" value={currentHH.desired_apartment_size ?? ''} editing={editing}
                                onChange={(v) => handleHHChange('desired_apartment_size', v)} />
                            <Grid size={{ xs: 6, sm: 4 }}>
                                {editing ? (
                                    <FormControl size="small" fullWidth>
                                        <InputLabel>Wohnungsart</InputLabel>
                                        <Select
                                            multiple
                                            value={currentHH.desired_apartment_type ?? []}
                                            label="Wohnungsart"
                                            input={<OutlinedInput label="Wohnungsart" />}
                                            onChange={(e) => handleHHChange('desired_apartment_type', e.target.value as string[])}
                                            renderValue={(selected) => (
                                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                                    {(selected as string[]).map((v) => (
                                                        <Chip key={v} label={v} size="small" />
                                                    ))}
                                                </Box>
                                            )}
                                        >
                                            {APARTMENT_TYPE_OPTIONS.map((opt) => (
                                                <MenuItem key={opt} value={opt}>
                                                    <Checkbox checked={(currentHH.desired_apartment_type ?? []).includes(opt)} />
                                                    <ListItemText primary={opt} />
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                ) : (
                                    <FieldDisplay
                                        label="Wohnungsart"
                                        value={(currentHH.desired_apartment_type ?? []).join(', ') || undefined}
                                    />
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
                                {editing ? (
                                    <FormControlLabel
                                        control={<Switch checked={currentHH.is_resident}
                                            onChange={(e) => handleHHChange('is_resident', e.target.checked)} />}
                                        label="Bewohner (is_resident)" />
                                ) : (
                                    <FieldDisplay label="Bewohner" value={currentHH.is_resident ? 'Ja' : 'Nein'} />
                                )}
                            </Grid>
                            <GridField label="Deklarierte Mitglieder" value={currentHH.household_member_count != null ? String(currentHH.household_member_count) : ''} editing={editing}
                                onChange={(v) => handleHHChange('household_member_count', parseInt(v) || 0)} />
                        </Grid>

                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <FieldDisplay label="Import-Quelle" value={currentHH.import_source} />
                            <FieldDisplay label="Import-Zeitstempel" value={formatDate(currentHH.import_timestamp)} />
                            <FieldDisplay label="Gesamt-Score" value={currentHH.total_score.toFixed(2)} />
                        </Box>

                        <Divider sx={{ my: 2 }} />
                        <Typography variant="h6" gutterBottom>
                            Personen ({mergedPersons.length})
                        </Typography>
                        {mergedPersons.map((person) => (
                            <PersonCard
                                key={person.id}
                                person={person}
                                editing={editing}
                                onChange={handlePersonChange}
                            />
                        ))}
                    </>
                )}
            </DialogContent>
            <DialogActions>
                {editing ? (
                    <>
                        <Button onClick={handleCancel}>Abbrechen</Button>
                        <Button variant="contained" onClick={handleSave} disabled={saving}>
                            {saving ? 'Speichere...' : 'Speichern'}
                        </Button>
                    </>
                ) : (
                    <Button onClick={onClose}>Schließen</Button>
                )}
            </DialogActions>
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

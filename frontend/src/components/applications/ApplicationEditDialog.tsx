import { useEffect, useMemo, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Grid,
    Alert, MenuItem, FormControlLabel, Switch, Autocomplete, Chip, Box, Typography,
    Checkbox, ListItemText, Select, InputLabel, FormControl, OutlinedInput,
} from '@mui/material';
import {
    Application, ApartmentCategory, Household,
    APPLICATION_KIND_LABELS, APPLICATION_STATUS_LABELS,
} from '../../types';
import { createApplication, updateApplication, getApartmentCategories } from '../../api';
import { categoryToWish, wishKey, wishLabel, toDateInput } from './wishes';

interface ApplicationEditDialogProps {
    open: boolean;
    /** Bewerbung zum Bearbeiten; null legt eine neue an. */
    application: Application | null;
    /** Auswahlliste der Haushalte; entfällt, wenn `fixedHousehold` gesetzt ist. */
    households: Household[];
    /** Vorgegebener Haushalt (Aufruf aus der Haushaltsdetailansicht). */
    fixedHousehold?: Household | null;
    onClose: () => void;
    onSaved: () => void;
}

type FormState = {
    household_id: number | null;
    kind: string;
    requested_at: string;
    wishKeys: string[];
    status: string;
    status_note: string;
    special_case: boolean;
    special_case_note: string;
    note: string;
};

const EMPTY: FormState = {
    household_id: null,
    kind: 'wartepool',
    requested_at: '',
    wishKeys: [],
    status: 'offen',
    status_note: '',
    special_case: false,
    special_case_note: '',
    note: '',
};

export default function ApplicationEditDialog({
    open, application, households, fixedHousehold, onClose, onSaved,
}: ApplicationEditDialogProps) {
    const [form, setForm] = useState<FormState>(EMPTY);
    const [categories, setCategories] = useState<ApartmentCategory[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!open) return;
        getApartmentCategories().then(setCategories).catch(() => setCategories([]));
    }, [open]);

    useEffect(() => {
        if (!open) return;
        setError('');
        if (application) {
            setForm({
                household_id: application.household_id,
                kind: application.kind,
                requested_at: toDateInput(application.requested_at),
                wishKeys: application.wishes.map(wishKey),
                status: application.status,
                status_note: application.status_note ?? '',
                special_case: application.special_case,
                special_case_note: application.special_case_note ?? '',
                note: application.note ?? '',
            });
            return;
        }
        // Bewohner wollen wechseln, alle anderen bewerben sich auf den Wartepool.
        const household = fixedHousehold ?? null;
        setForm({
            ...EMPTY,
            household_id: household?.id ?? null,
            kind: household?.is_resident ? 'wechselwunsch' : 'wartepool',
            requested_at: new Date().toISOString().slice(0, 10),
        });
    }, [open, application, fixedHousehold]);

    const categoryByKey = useMemo(() => {
        const map = new Map<string, ApartmentCategory>();
        categories.forEach((c) => map.set(wishKey(categoryToWish(c)), c));
        return map;
    }, [categories]);

    const set = <K extends keyof FormState>(field: K, value: FormState[K]) =>
        setForm((prev) => ({ ...prev, [field]: value }));

    const selectedHousehold = fixedHousehold
        ?? households.find((h) => h.id === form.household_id)
        ?? null;

    async function handleSave() {
        if (!form.household_id) {
            setError('Bitte einen Haushalt wählen.');
            return;
        }
        setSaving(true);
        setError('');
        const payload: Partial<Application> = {
            household_id: form.household_id,
            kind: form.kind as Application['kind'],
            requested_at: form.requested_at || null,
            wishes: form.wishKeys
                .map((k) => categoryByKey.get(k))
                .filter((c): c is ApartmentCategory => !!c)
                .map(categoryToWish),
            status: form.status as Application['status'],
            status_note: form.status_note.trim() || null,
            special_case: form.special_case,
            special_case_note: form.special_case_note.trim() || null,
            note: form.note.trim() || null,
        };
        try {
            if (application) {
                await updateApplication(application.id, payload);
            } else {
                await createApplication(payload);
            }
            onSaved();
            onClose();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Speichern fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                {application ? 'Bewerbung bearbeiten' : 'Bewerbung anlegen'}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                <Grid container spacing={2} sx={{ mt: 0 }}>
                    <Grid size={{ xs: 12 }}>
                        {fixedHousehold || application ? (
                            <TextField
                                fullWidth label="Haushalt" disabled
                                value={selectedHousehold?.name
                                    ?? application?.household_name ?? ''}
                            />
                        ) : (
                            <Autocomplete
                                options={households}
                                getOptionLabel={(h) => h.name}
                                value={selectedHousehold}
                                onChange={(_, value) => setForm((prev) => ({
                                    ...prev,
                                    household_id: value?.id ?? null,
                                    kind: value?.is_resident ? 'wechselwunsch' : 'wartepool',
                                }))}
                                renderInput={(params) => (
                                    <TextField {...params} autoFocus required label="Haushalt" />
                                )}
                            />
                        )}
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            select fullWidth label="Bewerbungsart" value={form.kind}
                            onChange={(e) => set('kind', e.target.value)}
                            helperText={form.kind === 'wartepool'
                                ? 'Wird per Scoring gereiht'
                                : 'Vorrang nach dem Zeitpunkt des Wunsches'}
                        >
                            {Object.entries(APPLICATION_KIND_LABELS).map(([value, label]) => (
                                <MenuItem key={value} value={value}>{label}</MenuItem>
                            ))}
                        </TextField>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth type="date" label="Mail / Info von"
                            slotProps={{ inputLabel: { shrink: true } }}
                            value={form.requested_at}
                            onChange={(e) => set('requested_at', e.target.value)}
                        />
                    </Grid>

                    <Grid size={{ xs: 12 }}>
                        <FormControl fullWidth>
                            <InputLabel id="wish-label">Wunsch</InputLabel>
                            <Select
                                labelId="wish-label"
                                multiple
                                value={form.wishKeys}
                                onChange={(e) => set('wishKeys', e.target.value as string[])}
                                input={<OutlinedInput label="Wunsch" />}
                                renderValue={(selected) => (
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {(selected as string[]).map((key) => {
                                            const category = categoryByKey.get(key);
                                            return (
                                                <Chip
                                                    key={key} size="small"
                                                    label={category
                                                        ? category.label
                                                        : wishLabel({})}
                                                />
                                            );
                                        })}
                                    </Box>
                                )}
                                MenuProps={{ slotProps: { paper: { sx: { maxHeight: 360 } } } }}
                            >
                                {categories.map((category) => {
                                    const key = wishKey(categoryToWish(category));
                                    return (
                                        <MenuItem key={key} value={key}>
                                            <Checkbox checked={form.wishKeys.includes(key)} />
                                            <ListItemText
                                                primary={category.label}
                                                secondary={`${category.apartment_count} Wohnung(en)`}
                                            />
                                        </MenuItem>
                                    );
                                })}
                            </Select>
                        </FormControl>
                        <Typography variant="caption" color="text.secondary">
                            Die Auswahl kommt aus den Wohnungsstammdaten. Ein Haushalt erscheint
                            zusätzlich in jeder gewünschten Kategorie — auch dort, wo die
                            Eignungsprüfung ihn ausschließen würde.
                        </Typography>
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            select fullWidth label="Status" value={form.status}
                            onChange={(e) => set('status', e.target.value)}
                        >
                            {Object.entries(APPLICATION_STATUS_LABELS).map(([value, label]) => (
                                <MenuItem key={value} value={value}>{label}</MenuItem>
                            ))}
                        </TextField>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth label="Notiz zum Status"
                            placeholder="z. B. Grund der Rücknahme"
                            value={form.status_note}
                            onChange={(e) => set('status_note', e.target.value)}
                        />
                    </Grid>

                    <Grid size={{ xs: 12 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={form.special_case}
                                    onChange={(_, checked) => set('special_case', checked)}
                                />
                            }
                            label="Sonderfall beachten (Abweichung von der Regelvergabe prüfen)"
                        />
                    </Grid>
                    {form.special_case && (
                        <Grid size={{ xs: 12 }}>
                            <TextField
                                fullWidth multiline minRows={2} label="Begründung der Abweichung"
                                value={form.special_case_note}
                                onChange={(e) => set('special_case_note', e.target.value)}
                            />
                        </Grid>
                    )}
                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth multiline minRows={3} label="Kommentar"
                            value={form.note}
                            onChange={(e) => set('note', e.target.value)}
                        />
                    </Grid>
                </Grid>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button variant="contained" onClick={handleSave} disabled={saving}>
                    {saving ? 'Speichere...' : 'Speichern'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

import { useEffect, useMemo, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, TextField, Alert, Grid, FormControl, InputLabel, Select, MenuItem,
} from '@mui/material';
import { PersonWithHousehold } from '../../types';
import { createPerson, getAllPersons } from '../../api';
import { EDUCATION_OPTIONS, FIELD_LABELS, OCCUPATION_OPTIONS } from '../household/PersonCard';

interface CreatePersonDialogProps {
    open: boolean;
    /** Haushalt, in dem die Person sofort steht; ohne Angabe hat sie keinen. */
    householdId?: number | null;
    householdName?: string;
    onClose: () => void;
    onCreated: () => void;
}

const EMPTY = {
    first_name: '',
    last_name: '',
    member_number: '',
    member_since: '',
    birth_date: '',
    gender: '',
    occupation_type: '',
    education_level: '',
    cultural_background: '',
    special_needs: '',
};

type Form = typeof EMPTY;

const GENDER_OPTIONS = [
    { value: '', label: '—' },
    { value: 'f', label: 'weiblich' },
    { value: 'm', label: 'männlich' },
    { value: 'd', label: 'divers' },
];

/** „3“ und „003“ sind dieselbe Mitgliedsnummer. */
function memberNumberKey(raw?: string | null): string {
    const digits = (raw ?? '').match(/\d+/)?.[0];
    return digits ? String(parseInt(digits, 10)) : '';
}

/**
 * Wie die Importe: Zwei Namen sind gleich, wenn sie aus denselben Bestandteilen
 * bestehen, gleich in welcher Reihenfolge und Aufteilung.
 */
function nameKey(firstName?: string | null, lastName?: string | null): string {
    const parts = `${firstName ?? ''} ${lastName ?? ''}`.toLowerCase().split(/[\s,]+/).filter(Boolean);
    return [...new Set(parts)].sort().join(' ');
}

function describe(person: PersonWithHousehold): string {
    const name = `${person.first_name} ${person.last_name}`.trim();
    const number = person.member_number ? `, Nr. ${person.member_number}` : '';
    const household = person.household_name ? `, Haushalt „${person.household_name}“` : ', ohne Haushalt';
    return `${name}${number}${household}${person.archived ? ', archiviert' : ''}`;
}

export default function CreatePersonDialog({
    open, householdId, householdName, onClose, onCreated,
}: CreatePersonDialogProps) {
    const [form, setForm] = useState<Form>(EMPTY);
    const [existing, setExisting] = useState<PersonWithHousehold[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!open) return;
        setForm(EMPTY);
        setError('');
        // Auch archivierte Personen, damit die Warnung keine Dublette übersieht.
        getAllPersons(true).then(setExisting).catch(() => setExisting([]));
    }, [open]);

    const duplicates = useMemo(() => {
        const number = memberNumberKey(form.member_number);
        const name = nameKey(form.first_name, form.last_name);
        const hasName = form.first_name.trim() !== '' && form.last_name.trim() !== '';
        return existing.filter((person) =>
            (number !== '' && memberNumberKey(person.member_number) === number)
            || (hasName && nameKey(person.first_name, person.last_name) === name));
    }, [existing, form.first_name, form.last_name, form.member_number]);

    const complete = form.first_name.trim() !== '' && form.last_name.trim() !== '';

    function set(field: keyof Form, value: string) {
        setForm((prev) => ({ ...prev, [field]: value }));
    }

    async function handleCreate() {
        setSaving(true);
        setError('');
        try {
            await createPerson({
                first_name: form.first_name.trim(),
                last_name: form.last_name.trim(),
                member_number: form.member_number.trim() || undefined,
                member_since: form.member_since ? `${form.member_since}T00:00:00` : undefined,
                birth_date: form.birth_date ? `${form.birth_date}T00:00:00` : undefined,
                gender: form.gender || undefined,
                occupation_type: form.occupation_type || undefined,
                education_level: form.education_level || undefined,
                cultural_background: form.cultural_background.trim() || undefined,
                special_needs: form.special_needs.trim() || undefined,
                household_id: householdId ?? undefined,
            });
            onCreated();
            onClose();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Person konnte nicht angelegt werden');
        } finally {
            setSaving(false);
        }
    }

    const text = (field: keyof Form, required = false) => (
        <TextField
            label={FIELD_LABELS[field]}
            size="small"
            fullWidth
            required={required}
            value={form[field]}
            onChange={(e) => set(field, e.target.value)}
        />
    );

    const date = (field: 'birth_date' | 'member_since') => (
        <TextField
            label={FIELD_LABELS[field]}
            type="date"
            size="small"
            fullWidth
            value={form[field]}
            onChange={(e) => set(field, e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
        />
    );

    const select = (field: keyof Form, options: { value: string; label: string }[]) => (
        <FormControl size="small" fullWidth>
            <InputLabel>{FIELD_LABELS[field]}</InputLabel>
            <Select
                value={form[field]}
                label={FIELD_LABELS[field]}
                onChange={(e) => set(field, e.target.value)}
            >
                {options.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
            </Select>
        </FormControl>
    );

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                {householdId ? `Neue Person in „${householdName ?? 'Haushalt'}“ anlegen` : 'Person anlegen'}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {!householdId && (
                    <Alert severity="info" sx={{ mb: 2 }}>
                        Die Person hat zunächst keinen Haushalt. Zuordnen kannst du sie danach in der Liste.
                    </Alert>
                )}
                <Grid container spacing={2} sx={{ mt: 0.5 }}>
                    <Grid size={{ xs: 12, sm: 6 }}>{text('first_name', true)}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{text('last_name', true)}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{text('member_number')}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{date('member_since')}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{date('birth_date')}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{select('gender', GENDER_OPTIONS)}</Grid>
                    <Grid size={{ xs: 12 }}>{select('occupation_type', OCCUPATION_OPTIONS)}</Grid>
                    <Grid size={{ xs: 12 }}>{select('education_level', EDUCATION_OPTIONS)}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{text('cultural_background')}</Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>{text('special_needs')}</Grid>
                </Grid>
                {duplicates.length > 0 && (
                    <Alert severity="warning" sx={{ mt: 2 }}>
                        <strong>Diese Person gibt es vielleicht schon:</strong>
                        <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                            {duplicates.map((person) => <li key={person.id}>{describe(person)}</li>)}
                        </ul>
                    </Alert>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button
                    variant="contained"
                    color={duplicates.length > 0 ? 'warning' : 'primary'}
                    onClick={handleCreate}
                    disabled={!complete || saving}
                >
                    {saving ? 'Speichere...' : duplicates.length > 0 ? 'Trotzdem anlegen' : 'Anlegen'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

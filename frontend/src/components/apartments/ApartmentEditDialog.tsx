import { useEffect, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, TextField, Grid, Alert, MenuItem, FormControlLabel, Switch,
} from '@mui/material';
import { Apartment } from '../../types';
import { createApartment, updateApartment } from '../../api';

interface ApartmentEditDialogProps {
    open: boolean;
    /** Wohnung zum Bearbeiten; null legt eine neue Wohnung an. */
    apartment: Apartment | null;
    onClose: () => void;
    onSaved: () => void;
}

const FUNDING_TYPES = ['freifinanziert', 'WBS A', 'WBS B'];

const CATEGORIES = [
    'Standard Wohnungstypen',
    'Clusterwohnung',
    'Ausbauwohnung',
    'Atelierwohnung',
    'Joker',
];

type FormState = {
    unit_number: string;
    size_rooms: string;
    apartment_category: string;
    is_small: boolean;
    area_shares: string;
    area_rent: string;
    area_utilities: string;
    funding_type: string;
    min_occupants: string;
};

const EMPTY: FormState = {
    unit_number: '',
    size_rooms: '',
    apartment_category: '',
    is_small: false,
    area_shares: '',
    area_rent: '',
    area_utilities: '',
    funding_type: 'freifinanziert',
    min_occupants: '',
};

function toForm(apt: Apartment): FormState {
    const str = (v: number | string | null | undefined) =>
        v === null || v === undefined ? '' : String(v);
    return {
        unit_number: apt.unit_number ?? '',
        size_rooms: str(apt.size_rooms),
        apartment_category: apt.apartment_category ?? '',
        is_small: apt.is_small ?? false,
        area_shares: str(apt.area_shares),
        area_rent: str(apt.area_rent),
        area_utilities: str(apt.area_utilities),
        funding_type: apt.funding_type ?? 'freifinanziert',
        min_occupants: str(apt.min_occupants),
    };
}

function toNumber(value: string): number | undefined {
    const trimmed = value.trim().replace(',', '.');
    if (!trimmed) return undefined;
    const parsed = Number(trimmed);
    return Number.isNaN(parsed) ? undefined : parsed;
}

export default function ApartmentEditDialog({
    open, apartment, onClose, onSaved,
}: ApartmentEditDialogProps) {
    const [form, setForm] = useState<FormState>(EMPTY);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!open) return;
        setForm(apartment ? toForm(apartment) : EMPTY);
        setError('');
    }, [open, apartment]);

    const set = (field: keyof FormState) => (
        (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
            setForm((prev) => ({ ...prev, [field]: e.target.value }))
    );

    async function handleSave() {
        if (!form.unit_number.trim()) {
            setError('Die Wohnungsnummer ist erforderlich.');
            return;
        }
        const rooms = toNumber(form.size_rooms);
        if (rooms !== undefined && !Number.isInteger(rooms)) {
            setError('Die Zimmerzahl wird als ganze Zahl geführt (aus 3,5 wird 3).');
            return;
        }
        setSaving(true);
        setError('');
        const payload: Partial<Apartment> = {
            unit_number: form.unit_number.trim(),
            size_rooms: rooms ?? null,
            apartment_category: form.apartment_category.trim() || undefined,
            is_small: form.is_small,
            area_shares: toNumber(form.area_shares),
            area_rent: toNumber(form.area_rent),
            area_utilities: toNumber(form.area_utilities),
            funding_type: form.funding_type,
            min_occupants: toNumber(form.min_occupants),
        };
        try {
            if (apartment) {
                await updateApartment(apartment.id, payload);
            } else {
                await createApartment(payload);
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
                {apartment ? `Wohnung ${apartment.unit_number} bearbeiten` : 'Neue Wohnung anlegen'}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                <Grid container spacing={2} sx={{ mt: 0 }}>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth autoFocus required label="Wohnungsnummer"
                            placeholder="z. B. W.002"
                            value={form.unit_number} onChange={set('unit_number')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            select fullWidth label="Wohnungsart"
                            value={form.apartment_category} onChange={set('apartment_category')}
                        >
                            <MenuItem value="">–</MenuItem>
                            {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
                        </TextField>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth label="Zimmer" type="number"
                            inputProps={{ step: 1, min: 0 }}
                            helperText="Ganze Zahl; leer lassen bei Wohnungen ohne Zimmerangabe"
                            value={form.size_rooms} onChange={set('size_rooms')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth label="mind. Bewohner" type="number"
                            value={form.min_occupants} onChange={set('min_occupants')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={form.is_small}
                                    onChange={(_, checked) =>
                                        setForm((prev) => ({ ...prev, is_small: checked }))}
                                />
                            }
                            label="Klein für ihre Zimmerzahl"
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            select fullWidth label="Förderungsart"
                            value={form.funding_type} onChange={set('funding_type')}
                        >
                            {FUNDING_TYPES.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
                        </TextField>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                            fullWidth label="qm Anteile" type="number"
                            value={form.area_shares} onChange={set('area_shares')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                            fullWidth label="qm mietwirksam" type="number"
                            value={form.area_rent} onChange={set('area_rent')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                            fullWidth label="qm Nebenkosten" type="number"
                            value={form.area_utilities} onChange={set('area_utilities')}
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

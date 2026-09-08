import { useEffect, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, TextField, Grid, Alert, MenuItem,
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
    'Wohngemeinschaft',
    'C-Riegel',
    'Joker',
    'Gartencluster',
];

type FormState = {
    unit_number: string;
    floor: string;
    area_shares: string;
    area_rent: string;
    area_utilities: string;
    apartment_type: string;
    apartment_category: string;
    size_rooms: string;
    wbs_raw: string;
    funding_type: string;
    min_occupants: string;
};

const EMPTY: FormState = {
    unit_number: '',
    floor: '',
    area_shares: '',
    area_rent: '',
    area_utilities: '',
    apartment_type: '',
    apartment_category: '',
    size_rooms: '',
    wbs_raw: '',
    funding_type: 'freifinanziert',
    min_occupants: '',
};

function toForm(apt: Apartment): FormState {
    const str = (v: number | string | null | undefined) =>
        v === null || v === undefined ? '' : String(v);
    return {
        unit_number: apt.unit_number ?? '',
        floor: apt.floor ?? '',
        area_shares: str(apt.area_shares),
        area_rent: str(apt.area_rent),
        area_utilities: str(apt.area_utilities),
        apartment_type: apt.apartment_type ?? '',
        apartment_category: apt.apartment_category ?? '',
        size_rooms: str(apt.size_rooms),
        wbs_raw: apt.wbs_raw ?? '',
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
        setSaving(true);
        setError('');
        const payload: Partial<Apartment> = {
            unit_number: form.unit_number.trim(),
            floor: form.floor.trim() || undefined,
            area_shares: toNumber(form.area_shares),
            area_rent: toNumber(form.area_rent),
            area_utilities: toNumber(form.area_utilities),
            apartment_type: form.apartment_type.trim() || undefined,
            apartment_category: form.apartment_category.trim() || undefined,
            size_rooms: toNumber(form.size_rooms) ?? null,
            wbs_raw: form.wbs_raw.trim() || undefined,
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
                            fullWidth label="Etage" placeholder="EG, 1.OG, ..."
                            value={form.floor} onChange={set('floor')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth label="Typ" placeholder="1.5, CL Punkt, Mini WG, ..."
                            value={form.apartment_type} onChange={set('apartment_type')}
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
                            helperText="Leer lassen bei Sondertypen ohne Zimmerzahl"
                            value={form.size_rooms} onChange={set('size_rooms')}
                        />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth label="mind. Bewohner" type="number"
                            value={form.min_occupants} onChange={set('min_occupants')}
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
                    <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                            fullWidth label="WBS-Kennzeichen" placeholder="N, A, B, WPG-A, ..."
                            helperText="Rohwert aus der Wohnungsübersicht"
                            value={form.wbs_raw} onChange={set('wbs_raw')}
                        />
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

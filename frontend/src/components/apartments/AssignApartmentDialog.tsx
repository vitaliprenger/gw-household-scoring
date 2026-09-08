import { useState, useEffect } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Autocomplete, TextField, Alert, Typography, Box, Chip,
} from '@mui/material';
import { Apartment, Household } from '../../types';
import { getHouseholds, assignApartment } from '../../api';

interface AssignApartmentDialogProps {
    open: boolean;
    apartment: Apartment | null;
    onClose: () => void;
    onAssigned: () => void;
}

export default function AssignApartmentDialog({
    open, apartment, onClose, onAssigned,
}: AssignApartmentDialogProps) {
    const [households, setHouseholds] = useState<Household[]>([]);
    const [selected, setSelected] = useState<Household | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!open) return;
        setSelected(null);
        setError('');
        setLoading(true);
        getHouseholds()
            .then((all) => {
                setHouseholds(all);
                const current = all.find((hh) => hh.id === apartment?.household_id);
                if (current) setSelected(current);
            })
            .catch(() => setError('Haushalte konnten nicht geladen werden'))
            .finally(() => setLoading(false));
    }, [open, apartment]);

    async function handleAssign() {
        if (!apartment || !selected) return;
        setSaving(true);
        setError('');
        try {
            await assignApartment(apartment.id, selected.id);
            onAssigned();
            onClose();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Zuordnung fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Haushalt zuordnen</DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {apartment && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <Typography variant="body2" color="text.secondary">Wohnung:</Typography>
                        <Typography variant="body2" fontWeight="bold">{apartment.unit_number}</Typography>
                        {apartment.apartment_type && <Chip label={apartment.apartment_type} size="small" />}
                        <Chip label={apartment.funding_type} size="small" />
                    </Box>
                )}
                <Alert severity="info" sx={{ mb: 2 }}>
                    Der zugeordnete Haushalt gilt als aktueller Bewohner dieser Wohnung.
                    Eine bestehende Zuordnung des Haushalts zu einer anderen Wohnung wird gelöst.
                </Alert>
                <Autocomplete
                    options={households}
                    loading={loading}
                    value={selected}
                    onChange={(_, value) => setSelected(value)}
                    getOptionLabel={(hh) => hh.name}
                    isOptionEqualToValue={(a, b) => a.id === b.id}
                    renderOption={(props, hh) => (
                        <li {...props} key={hh.id}>
                            {hh.name} ({hh.people.length} Personen)
                            {hh.apartment_unit ? ` – bisher ${hh.apartment_unit}` : ''}
                        </li>
                    )}
                    renderInput={(params) => (
                        <TextField {...params} autoFocus label="Haushalt" placeholder="Haushalt suchen..." />
                    )}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button
                    variant="contained"
                    onClick={handleAssign}
                    disabled={!selected || saving || selected.id === apartment?.household_id}
                >
                    {saving ? 'Speichere...' : 'Zuordnen'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

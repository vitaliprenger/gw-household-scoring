import { useState, useEffect } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Autocomplete, TextField, Alert, Typography, Box, Chip,
} from '@mui/material';
import { Household, Person } from '../../types';
import { getHouseholds, assignPerson } from '../../api';

interface AssignHouseholdDialogProps {
    open: boolean;
    person: Person | null;
    onClose: () => void;
    onAssigned: () => void;
}

export default function AssignHouseholdDialog({
    open, person, onClose, onAssigned,
}: AssignHouseholdDialogProps) {
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
            .then(setHouseholds)
            .catch(() => setError('Haushalte konnten nicht geladen werden'))
            .finally(() => setLoading(false));
    }, [open]);

    async function handleAssign() {
        if (!person || !selected) return;
        setSaving(true);
        setError('');
        try {
            await assignPerson(person.id, selected.id);
            onAssigned();
            onClose();
        } catch {
            setError('Zuordnung fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Haushalt zuordnen</DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {person && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <Typography variant="body2" color="text.secondary">Person:</Typography>
                        <Typography variant="body2" fontWeight="bold">
                            {person.first_name} {person.last_name}
                        </Typography>
                        {person.member_number && <Chip label={person.member_number} size="small" />}
                    </Box>
                )}
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
                        </li>
                    )}
                    renderInput={(params) => (
                        <TextField {...params} autoFocus label="Haushalt" placeholder="Haushalt suchen..." />
                    )}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button variant="contained" onClick={handleAssign} disabled={!selected || saving}>
                    {saving ? 'Speichere...' : 'Zuordnen'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

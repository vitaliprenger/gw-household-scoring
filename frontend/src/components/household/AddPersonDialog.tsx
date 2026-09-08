import { useState, useEffect } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Autocomplete, TextField, Alert, Typography,
} from '@mui/material';
import { Person } from '../../types';
import { getUnassignedPersons, assignPerson } from '../../api';

interface AddPersonDialogProps {
    open: boolean;
    householdId: number | null;
    householdName?: string;
    onClose: () => void;
    onAdded: () => void;
}

function personLabel(p: Person): string {
    const name = `${p.first_name} ${p.last_name}`.trim();
    return p.member_number ? `${name} (${p.member_number})` : name;
}

export default function AddPersonDialog({
    open, householdId, householdName, onClose, onAdded,
}: AddPersonDialogProps) {
    const [persons, setPersons] = useState<Person[]>([]);
    const [selected, setSelected] = useState<Person | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!open) return;
        setSelected(null);
        setError('');
        setLoading(true);
        getUnassignedPersons()
            .then(setPersons)
            .catch(() => setError('Personen konnten nicht geladen werden'))
            .finally(() => setLoading(false));
    }, [open]);

    async function handleAdd() {
        if (!householdId || !selected) return;
        setSaving(true);
        setError('');
        try {
            await assignPerson(selected.id, householdId);
            onAdded();
            onClose();
        } catch {
            setError('Zuordnung fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Person zu „{householdName ?? 'Haushalt'}“ hinzufügen</DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Es können nur Personen ohne Haushaltszuordnung hinzugefügt werden.
                </Typography>
                {!loading && persons.length === 0 ? (
                    <Alert severity="info">Es gibt derzeit keine Personen ohne Haushalt.</Alert>
                ) : (
                    <Autocomplete
                        options={persons}
                        loading={loading}
                        value={selected}
                        onChange={(_, value) => setSelected(value)}
                        getOptionLabel={personLabel}
                        isOptionEqualToValue={(a, b) => a.id === b.id}
                        renderOption={(props, p) => (
                            <li {...props} key={p.id}>{personLabel(p)}</li>
                        )}
                        renderInput={(params) => (
                            <TextField {...params} autoFocus label="Person" placeholder="Person suchen..." />
                        )}
                    />
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button variant="contained" onClick={handleAdd} disabled={!selected || saving}>
                    {saving ? 'Speichere...' : 'Hinzufügen'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

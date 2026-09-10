import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, TextField, Alert,
} from '@mui/material';
import { api } from '../../api';
import { Household } from '../../types';

interface CreateHouseholdDialogProps {
    open: boolean;
    onClose: () => void;
    onCreated: (household: Household) => void;
}

export default function CreateHouseholdDialog({
    open, onClose, onCreated,
}: CreateHouseholdDialogProps) {
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    function handleClose() {
        setName('');
        setError('');
        onClose();
    }

    async function handleCreate() {
        if (!name.trim()) {
            setError('Bitte einen Namen eingeben.');
            return;
        }
        setSaving(true);
        setError('');
        try {
            const response = await api.post<Household>('/households/', {
                name: name.trim(),
                people: [],
            });
            setName('');
            onCreated(response.data);
        } catch {
            setError('Anlegen fehlgeschlagen');
        } finally {
            setSaving(false);
        }
    }

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
            <DialogTitle>Neuen Haushalt anlegen</DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                <TextField
                    autoFocus
                    fullWidth
                    margin="dense"
                    label="Haushaltsname"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Abbrechen</Button>
                <Button variant="contained" onClick={handleCreate} disabled={saving}>
                    {saving ? 'Erstelle...' : 'Anlegen'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

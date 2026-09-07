import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, TextField, Table, TableBody, TableCell, TableContainer,
    TableHead, TableRow, Paper, Typography, Box, Chip,
} from '@mui/material';
import { HouseholdImportPreview } from '../../types';

interface MatchingDialogProps {
    open: boolean;
    household: HouseholdImportPreview;
    onClose: () => void;
    onSelect: (householdId: number | null, householdName?: string) => void;
}

export default function MatchingDialog({ open, household, onClose, onSelect }: MatchingDialogProps) {
    const [search, setSearch] = useState('');

    const candidates = household.match_result.fuzzy_candidates || [];
    const filtered = search
        ? candidates.filter((c) =>
            c.name.toLowerCase().includes(search.toLowerCase()) ||
            c.member_numbers.some((m) => m.includes(search))
        )
        : candidates;

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                Haushalt zuordnen: {household.persons[0]?.name ?? '—'}
            </DialogTitle>
            <DialogContent dividers>
                <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Personen im importierten Haushalt:
                        {household.persons.map((p) => ` ${p.name} (MitglNr: ${p.member_number || '—'})`).join(', ')}
                    </Typography>
                    <TextField
                        label="Suche (Name oder Mitgliedsnummer)"
                        size="small"
                        fullWidth
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </Box>
                <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Haushaltsname</TableCell>
                                <TableCell>Mitgliedsnummern</TableCell>
                                <TableCell align="right">Übereinstimmung</TableCell>
                                <TableCell></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filtered.map((c) => (
                                <TableRow key={c.household_id} hover>
                                    <TableCell>{c.name}</TableCell>
                                    <TableCell>
                                        {c.member_numbers.length > 0
                                            ? c.member_numbers.join(', ')
                                            : '—'}
                                    </TableCell>
                                    <TableCell align="right">
                                        <Chip
                                            label={`${(c.score * 100).toFixed(0)}%`}
                                            size="small"
                                            color={c.score >= 0.8 ? 'success' : c.score >= 0.5 ? 'warning' : 'default'}
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Button size="small" onClick={() => onSelect(c.household_id, c.name)}>
                                            Zuordnen
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {filtered.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={4} align="center">
                                        Keine Treffer
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button onClick={() => onSelect(null)} color="secondary">
                    Neuen Haushalt anlegen
                </Button>
            </DialogActions>
        </Dialog>
    );
}

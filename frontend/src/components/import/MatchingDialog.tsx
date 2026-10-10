import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, TextField, Table, TableBody, TableCell, TableContainer,
    TableHead, TableRow, Paper, Typography, Box, Chip,
} from '@mui/material';
import { FuzzyCandidate } from '../../types';

/** Eintrag, der sich von Hand zuordnen lässt, auch ohne Ähnlichkeit zur Zeile. */
export interface MatchOption {
    id: number;
    name: string;
    member_numbers: string[];
}

interface MatchingDialogProps {
    open: boolean;
    title: string;
    description: string;
    candidates: FuzzyCandidate[];
    /**
     * Alles, was sich zuordnen lässt. Die Suche findet darin auch Einträge,
     * die der Zeile nicht ähnlich sind, etwa einen gerade von Hand
     * angelegten Haushalt.
     */
    allOptions?: MatchOption[];
    onClose: () => void;
    onSelect: (id: number | null, name?: string) => void;
    nameColumnLabel?: string;
    createButtonLabel?: string;
}

export default function MatchingDialog({
    open, title, description, candidates: allCandidates, allOptions = [], onClose, onSelect,
    nameColumnLabel = 'Haushaltsname', createButtonLabel = 'Neuen Haushalt anlegen',
}: MatchingDialogProps) {
    const [search, setSearch] = useState('');

    const matches = (entry: { name: string; member_numbers: string[] }) =>
        entry.name.toLowerCase().includes(search.toLowerCase()) ||
        entry.member_numbers.some((m) => m.includes(search));

    const filtered = search ? allCandidates.filter(matches) : allCandidates;
    const suggested = new Set(allCandidates.map((c) => c.household_id));
    const others = search
        ? allOptions.filter((option) => !suggested.has(option.id) && matches(option))
        : [];

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>{title}</DialogTitle>
            <DialogContent dividers>
                <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {description}
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
                                <TableCell>{nameColumnLabel}</TableCell>
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
                            {others.map((option) => (
                                <TableRow key={`option-${option.id}`} hover>
                                    <TableCell>{option.name}</TableCell>
                                    <TableCell>
                                        {option.member_numbers.length > 0
                                            ? option.member_numbers.join(', ')
                                            : '—'}
                                    </TableCell>
                                    <TableCell align="right">—</TableCell>
                                    <TableCell>
                                        <Button size="small" onClick={() => onSelect(option.id, option.name)}>
                                            Zuordnen
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {filtered.length === 0 && others.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={4} align="center">
                                        {search || allOptions.length === 0
                                            ? 'Keine Treffer'
                                            : 'Keine ähnlichen Einträge. Über die Suche lässt sich jeder Eintrag zuordnen.'}
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
                    {createButtonLabel}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

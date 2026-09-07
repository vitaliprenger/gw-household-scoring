import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Typography, Table, TableBody, TableCell, TableContainer,
    TableHead, TableRow, Paper, Alert,
} from '@mui/material';
import { HouseholdImportPreview } from '../../types';

interface DataChangeDialogProps {
    open: boolean;
    household: HouseholdImportPreview;
    onClose: () => void;
    onConfirm: () => void;
}

export default function DataChangeDialog({ open, household, onClose, onConfirm }: DataChangeDialogProps) {
    const changes = household.existing_data_changes;
    if (!changes) return null;

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>Datenänderungen bestätigen</DialogTitle>
            <DialogContent dividers>
                <Typography variant="body2" sx={{ mb: 2 }}>
                    Beim Aktualisieren von <strong>{household.persons[0]?.name}</strong> werden
                    folgende Änderungen vorgenommen:
                </Typography>

                {changes.fields_to_overwrite.length > 0 && (
                    <>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>Überschriebene Felder:</Typography>
                        <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Feld</TableCell>
                                        <TableCell>Alter Wert</TableCell>
                                        <TableCell>Neuer Wert</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {changes.fields_to_overwrite.map((c, i) => (
                                        <TableRow key={i}>
                                            <TableCell>{c.field}</TableCell>
                                            <TableCell>{c.old_value || '—'}</TableCell>
                                            <TableCell>{c.new_value || '—'}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </>
                )}

                {changes.data_removals.length > 0 && (
                    <>
                        <Alert severity="warning" sx={{ mb: 1 }}>
                            Folgende Daten werden durch den Import <strong>entfernt</strong>:
                        </Alert>
                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Feld</TableCell>
                                        <TableCell>Bisheriger Wert (wird entfernt)</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {changes.data_removals.map((c, i) => (
                                        <TableRow key={i}>
                                            <TableCell>{c.field}</TableCell>
                                            <TableCell>{c.old_value || '—'}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button variant="contained" color="warning" onClick={onConfirm}>
                    Änderungen bestätigen
                </Button>
            </DialogActions>
        </Dialog>
    );
}

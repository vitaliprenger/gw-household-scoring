import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Typography, Box, Alert, CircularProgress,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
} from '@mui/material';
import {
    MemberListFills, MemberNumberConflict, VcfAnalysisResponse, VcfCommitResponse,
} from '../../types';
import { commitVcf } from '../../api';

interface VcfImportWizardProps {
    open: boolean;
    analysis: VcfAnalysisResponse;
    onClose: () => void;
    onComplete: () => void;
}

function formatDate(iso: string): string {
    const parsed = new Date(iso);
    return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleDateString('de-DE');
}

function personWord(count: number): string {
    return count === 1 ? 'Person' : 'Personen';
}

function FillCounts({ fills }: { fills: MemberListFills }) {
    return (
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Typography>Geburtsdatum: <strong>{fills.birth_date}</strong></Typography>
            <Typography>Mitglied seit: <strong>{fills.member_since}</strong></Typography>
            <Typography>Mitgliedsnummer: <strong>{fills.member_number}</strong></Typography>
            <Typography>Geschlecht: <strong>{fills.gender}</strong></Typography>
        </Box>
    );
}

function NumberConflicts({ conflicts, title }: { conflicts: MemberNumberConflict[]; title: string }) {
    if (conflicts.length === 0) return null;
    return (
        <Alert severity="warning" sx={{ mb: 2 }}>
            <strong>{title}</strong>
            <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                {conflicts.map((conflict, i) => (
                    <li key={i}>
                        {conflict.person}: Nummer {conflict.member_number} trägt
                        schon {conflict.holder}
                    </li>
                ))}
            </ul>
        </Alert>
    );
}

/**
 * Die Mitgliederliste füllt nur leere Angaben vorhandener Personen. Es gibt
 * deshalb nichts zu entscheiden: Der Assistent zeigt, was gefüllt würde, und
 * lässt es bestätigen.
 */
export default function VcfImportWizard({ open, analysis, onClose, onComplete }: VcfImportWizardProps) {
    const [committing, setCommitting] = useState(false);
    const [result, setResult] = useState<VcfCommitResponse | null>(null);
    const [error, setError] = useState('');

    async function handleCommit() {
        setCommitting(true);
        setError('');
        try {
            setResult(await commitVcf({ session_id: analysis.session_id }));
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Import fehlgeschlagen');
        } finally {
            setCommitting(false);
        }
    }

    const nothingToFill = analysis.fills.persons === 0;

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>Mitgliederliste – fehlende Angaben ergänzen</DialogTitle>
            <DialogContent dividers>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                {result ? (
                    <>
                        <Alert severity="success" sx={{ mb: 2 }}>
                            Bei <strong>{result.fills.persons}</strong> {personWord(result.fills.persons)}{' '}
                            wurden fehlende Angaben ergänzt.
                            <Box sx={{ mt: 1 }}><FillCounts fills={result.fills} /></Box>
                        </Alert>
                        <NumberConflicts
                            conflicts={result.member_numbers_not_stored}
                            title="Mitgliedsnummer nicht eingetragen, weil sie schon vergeben ist:"
                        />
                    </>
                ) : (
                    <>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            Die Mitgliederliste trägt nur ein, was bei einer vorhandenen Person noch
                            fehlt. Sie überschreibt nichts, legt niemanden an und ändert keine
                            Haushalte.
                        </Typography>

                        <Box sx={{ display: 'flex', gap: 3, mb: 2, flexWrap: 'wrap' }}>
                            <Typography>Karten: <strong>{analysis.total_cards}</strong></Typography>
                            <Typography>
                                Ohne passende Person: <strong>{analysis.unmatched_cards}</strong>
                            </Typography>
                            <Typography>
                                Ohne Änderung: <strong>{analysis.unchanged_cards}</strong>
                            </Typography>
                            {analysis.skipped_no_name > 0 && (
                                <Typography>Ohne Namen: <strong>{analysis.skipped_no_name}</strong></Typography>
                            )}
                        </Box>

                        <Alert severity={nothingToFill ? 'info' : 'success'} sx={{ mb: 2 }}>
                            {nothingToFill ? (
                                'Es fehlen keine Angaben, die die Mitgliederliste füllen könnte.'
                            ) : (
                                <>
                                    Bei <strong>{analysis.fills.persons}</strong>{' '}
                                    {personWord(analysis.fills.persons)} werden fehlende Angaben
                                    ergänzt:
                                    <Box sx={{ mt: 1 }}><FillCounts fills={analysis.fills} /></Box>
                                </>
                            )}
                        </Alert>

                        <NumberConflicts
                            conflicts={analysis.member_numbers_not_stored}
                            title="Mitgliedsnummer wird nicht eingetragen, weil sie schon vergeben ist:"
                        />

                        {analysis.member_since_deviations.length > 0 && (
                            <>
                                <Typography variant="subtitle1" gutterBottom>
                                    „Mitglied seit“ weicht ab
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Diese Werte bleiben, wie sie sind. Stimmt das Datum der
                                    Mitgliederliste, trag es von Hand bei der Person ein.
                                </Typography>
                                <TableContainer component={Paper} variant="outlined">
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Person</TableCell>
                                                <TableCell>Haushalt</TableCell>
                                                <TableCell>Gespeichert</TableCell>
                                                <TableCell>Mitgliederliste</TableCell>
                                                <TableCell align="right">Abweichung</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {analysis.member_since_deviations.map((deviation, i) => (
                                                <TableRow key={i}>
                                                    <TableCell>{deviation.person}</TableCell>
                                                    <TableCell>{deviation.household ?? '—'}</TableCell>
                                                    <TableCell>{formatDate(deviation.stored)}</TableCell>
                                                    <TableCell>{formatDate(deviation.member_list)}</TableCell>
                                                    <TableCell align="right">{deviation.days} Tage</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </>
                        )}
                    </>
                )}
            </DialogContent>
            <DialogActions>
                {result ? (
                    <Button variant="contained" onClick={onComplete}>Schließen</Button>
                ) : (
                    <>
                        <Button onClick={onClose}>{nothingToFill ? 'Schließen' : 'Abbrechen'}</Button>
                        <Button
                            variant="contained"
                            onClick={handleCommit}
                            disabled={committing || nothingToFill}
                        >
                            {committing ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                            Angaben ergänzen
                        </Button>
                    </>
                )}
            </DialogActions>
        </Dialog>
    );
}

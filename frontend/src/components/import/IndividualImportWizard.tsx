import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Stepper, Step, StepLabel, Typography, Box,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Chip, Alert, FormControl, Select, MenuItem, CircularProgress,
    Tooltip,
} from '@mui/material';
import {
    IndividualAnalysisResponse, IndividualImportPreview, IndividualDecision,
    IndividualCommitRequest,
} from '../../types';
import { commitIndividualBogen } from '../../api';
import MatchingDialog from './MatchingDialog';

interface IndividualImportWizardProps {
    open: boolean;
    analysis: IndividualAnalysisResponse;
    onClose: () => void;
    onComplete: () => void;
}

const STEPS = ['Analyse', 'Zuordnung', 'Zusammenfassung'];

export default function IndividualImportWizard({ open, analysis, onClose, onComplete }: IndividualImportWizardProps) {
    const [step, setStep] = useState(0);
    const [decisions, setDecisions] = useState<Record<string, IndividualDecision>>(() => {
        const init: Record<string, IndividualDecision> = {};
        for (const ind of analysis.individuals) {
            const mt = ind.match_result.type;
            const inactive = ind.already_imported || ind.is_older;
            let action: 'update' | 'create' | 'skip';
            if (inactive) {
                action = 'skip';
            } else if (mt === 'exact_member_nr' || mt === 'exact_name_dob' || mt === 'fuzzy') {
                action = 'update';
            } else {
                action = 'create';
            }
            init[ind.temp_id] = {
                temp_id: ind.temp_id,
                action,
                target_person_id: ind.match_result.matched_household_id ?? undefined,
                target_household_id: undefined,
                confirm_data_removals: false,
            };
        }
        return init;
    });
    const [matchingFor, setMatchingFor] = useState<IndividualImportPreview | null>(null);
    const [matchOverrides, setMatchOverrides] = useState<Record<string, string>>({});
    const [committing, setCommitting] = useState(false);
    const [commitResult, setCommitResult] = useState<{ updated: number; created: number; skipped: number } | null>(null);
    const [error, setError] = useState('');

    function updateDecision(tempId: string, patch: Partial<IndividualDecision>) {
        setDecisions((prev) => ({
            ...prev,
            [tempId]: { ...prev[tempId], ...patch },
        }));
    }

    async function handleCommit() {
        setCommitting(true);
        setError('');
        try {
            const request: IndividualCommitRequest = {
                session_id: analysis.session_id,
                decisions: Object.values(decisions),
            };
            const result = await commitIndividualBogen(request);
            setCommitResult(result);
            setStep(2);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Import fehlgeschlagen');
        } finally {
            setCommitting(false);
        }
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>Individualbogen importieren</DialogTitle>
            <DialogContent dividers>
                <Stepper activeStep={step} sx={{ mb: 3 }}>
                    {STEPS.map((label) => <Step key={label}><StepLabel>{label}</StepLabel></Step>)}
                </Stepper>

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                {analysis.hh_import_warning && step === 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Es wurden noch keine Haushaltsdaten importiert. Die Zuordnung der Personen
                        zu Haushalten ist möglicherweise nicht vollständig.
                    </Alert>
                )}

                {step === 0 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Analyse-Ergebnis</Typography>
                        <Box sx={{ display: 'flex', gap: 3, mb: 2 }}>
                            <Typography>Gesamt: <strong>{analysis.total_rows}</strong></Typography>
                            <Typography>Nicht abgesendet: <strong>{analysis.skipped_not_submitted}</strong></Typography>
                            <Typography>Dubletten: <strong>{analysis.skipped_duplicates}</strong></Typography>
                            <Typography>Zu verarbeiten: <strong>{analysis.individuals.length}</strong></Typography>
                        </Box>
                        {analysis.privacy_warnings.length > 0 && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                {analysis.privacy_warnings.length} Einträge ohne Datenschutz-Zustimmung.
                            </Alert>
                        )}
                    </Box>
                )}

                {step === 1 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Zuordnung der Einzelpersonen</Typography>
                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Name</TableCell>
                                        <TableCell>MitglNr.</TableCell>
                                        <TableCell>Geburtsdatum</TableCell>
                                        <TableCell>Match</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Aktion</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {analysis.individuals.map((ind) => {
                                        const dec = decisions[ind.temp_id];
                                        const mt = ind.match_result.type;
                                        const inactive = ind.already_imported || ind.is_older;
                                        const statusLabel = ind.already_imported
                                            ? 'Bereits importiert'
                                            : ind.is_older
                                                ? 'Älter als vorhanden'
                                                : null;
                                        return (
                                            <TableRow
                                                key={ind.temp_id}
                                                sx={inactive ? { opacity: 0.5, bgcolor: 'action.hover' } : undefined}
                                            >
                                                <TableCell>{ind.name}</TableCell>
                                                <TableCell>{ind.member_number || '—'}</TableCell>
                                                <TableCell>{ind.birth_date || '—'}</TableCell>
                                                <TableCell>
                                                    {(() => {
                                                        const overrideName = matchOverrides[ind.temp_id];
                                                        return (
                                                            <Chip
                                                                label={overrideName
                                                                    ? `Zugeordnet: ${overrideName}`
                                                                    : mt === 'none'
                                                                        ? 'Kein Match'
                                                                        : `${ind.match_result.matched_household_name ?? 'Match'}`}
                                                                size="small"
                                                                color={overrideName ? 'info' : mt === 'exact_member_nr' || mt === 'exact_name_dob' ? 'success' : mt === 'fuzzy' ? 'warning' : 'default'}
                                                                onClick={() => setMatchingFor(ind)}
                                                            />
                                                        );
                                                    })()}
                                                </TableCell>
                                                <TableCell>
                                                    {statusLabel && (
                                                        <Tooltip title={ind.already_imported
                                                            ? 'Dieser Datensatz wurde bereits mit demselben Zeitstempel importiert.'
                                                            : 'In der Datenbank existiert ein neuerer Import für diese Person.'
                                                        }>
                                                            <Chip
                                                                label={statusLabel}
                                                                size="small"
                                                                color={ind.already_imported ? 'default' : 'warning'}
                                                                variant="outlined"
                                                            />
                                                        </Tooltip>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <FormControl size="small" sx={{ minWidth: 140 }}>
                                                        <Select
                                                            value={dec?.action ?? 'create'}
                                                            onChange={(e) => updateDecision(ind.temp_id, {
                                                                action: e.target.value as 'update' | 'create' | 'skip',
                                                            })}
                                                        >
                                                            {ind.match_result.matched_household_id && (
                                                                <MenuItem value="update">Aktualisieren</MenuItem>
                                                            )}
                                                            <MenuItem value="create">Neu anlegen</MenuItem>
                                                            <MenuItem value="skip">Überspringen</MenuItem>
                                                        </Select>
                                                    </FormControl>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Box>
                )}

                {step === 2 && commitResult && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Import abgeschlossen</Typography>
                        <Alert severity="success">
                            <strong>{commitResult.updated}</strong> Personen aktualisiert,{' '}
                            <strong>{commitResult.created}</strong> neu angelegt,{' '}
                            <strong>{commitResult.skipped}</strong> übersprungen.
                        </Alert>
                    </Box>
                )}
            </DialogContent>
            <DialogActions>
                {step < 2 && <Button onClick={onClose}>Abbrechen</Button>}
                {step === 0 && (
                    <Button variant="contained" onClick={() => setStep(1)}>
                        Weiter zur Zuordnung
                    </Button>
                )}
                {step === 1 && (
                    <>
                        <Button onClick={() => setStep(0)}>Zurück</Button>
                        <Button variant="contained" onClick={handleCommit} disabled={committing}>
                            {committing ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                            Importieren
                        </Button>
                    </>
                )}
                {step === 2 && (
                    <Button variant="contained" onClick={onComplete}>Schließen</Button>
                )}
            </DialogActions>

            {matchingFor && (
                <MatchingDialog
                    open={!!matchingFor}
                    title={`Person zuordnen: ${matchingFor.name}`}
                    description={`MitglNr: ${matchingFor.member_number || '—'}, Geb.: ${matchingFor.birth_date || '—'}`}
                    candidates={matchingFor.match_result.fuzzy_candidates || []}
                    nameColumnLabel="Person (Haushalt)"
                    createButtonLabel="Neue Person anlegen"
                    onClose={() => setMatchingFor(null)}
                    onSelect={(personId, name) => {
                        if (personId) {
                            updateDecision(matchingFor.temp_id, {
                                action: 'update',
                                target_person_id: personId,
                            });
                            setMatchOverrides((prev) => ({ ...prev, [matchingFor.temp_id]: name || '' }));
                        } else {
                            updateDecision(matchingFor.temp_id, { action: 'create' });
                            setMatchOverrides((prev) => {
                                const next = { ...prev };
                                delete next[matchingFor.temp_id];
                                return next;
                            });
                        }
                        setMatchingFor(null);
                    }}
                />
            )}
        </Dialog>
    );
}

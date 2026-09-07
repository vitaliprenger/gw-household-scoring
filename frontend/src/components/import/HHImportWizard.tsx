import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Stepper, Step, StepLabel, Typography, Box,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Chip, Alert,
    FormControl, Select, MenuItem, CircularProgress,
} from '@mui/material';
import {
    HHAnalysisResponse, HouseholdImportPreview, HouseholdDecision,
    HHCommitRequest,
} from '../../types';
import { commitHHBogen } from '../../api';
import MatchingDialog from './MatchingDialog';
import DataChangeDialog from './DataChangeDialog';

interface HHImportWizardProps {
    open: boolean;
    analysis: HHAnalysisResponse;
    onClose: () => void;
    onComplete: () => void;
}

const STEPS = ['Analyse', 'Zuordnung & Entscheidungen', 'Zusammenfassung'];

function matchTypeLabel(type: string): string {
    switch (type) {
        case 'exact_member_nr': return 'Mitgliedsnr.';
        case 'exact_name_dob': return 'Name+Geb.';
        case 'fuzzy': return 'Vorschlag';
        case 'none': return 'Kein Match';
        default: return type;
    }
}

function matchColor(type: string): 'success' | 'warning' | 'info' | 'default' {
    switch (type) {
        case 'exact_member_nr': return 'success';
        case 'exact_name_dob': return 'success';
        case 'fuzzy': return 'warning';
        default: return 'default';
    }
}

export default function HHImportWizard({ open, analysis, onClose, onComplete }: HHImportWizardProps) {
    const [step, setStep] = useState(0);
    const [decisions, setDecisions] = useState<Record<string, HouseholdDecision>>(() => {
        const init: Record<string, HouseholdDecision> = {};
        for (const hh of analysis.households) {
            const matchType = hh.match_result.type;
            let action: 'create' | 'update' | 'skip' = 'create';
            let targetId: number | undefined;
            if (matchType === 'exact_member_nr' || matchType === 'exact_name_dob') {
                action = 'update';
                targetId = hh.match_result.matched_household_id ?? undefined;
            }
            init[hh.temp_id] = {
                temp_id: hh.temp_id,
                action,
                target_household_id: targetId,
                confirm_data_removals: false,
            };
        }
        return init;
    });
    const [matchingFor, setMatchingFor] = useState<HouseholdImportPreview | null>(null);
    const [dataChangeFor, setDataChangeFor] = useState<HouseholdImportPreview | null>(null);
    const [committing, setCommitting] = useState(false);
    const [commitResult, setCommitResult] = useState<{ imported: number; updated: number; skipped: number } | null>(null);
    const [error, setError] = useState('');

    function updateDecision(tempId: string, patch: Partial<HouseholdDecision>) {
        setDecisions((prev) => ({
            ...prev,
            [tempId]: { ...prev[tempId], ...patch },
        }));
    }

    async function handleCommit() {
        setCommitting(true);
        setError('');
        try {
            const request: HHCommitRequest = {
                session_id: analysis.session_id,
                decisions: Object.values(decisions),
            };
            const result = await commitHHBogen(request);
            setCommitResult(result);
            setStep(2);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Import fehlgeschlagen');
        } finally {
            setCommitting(false);
        }
    }

    const householdsWithRemovals = analysis.households.filter(
        (hh) => hh.existing_data_changes?.data_removals?.length && decisions[hh.temp_id]?.action === 'update'
    );
    const unconfirmedRemovals = householdsWithRemovals.filter((hh) => !decisions[hh.temp_id]?.confirm_data_removals);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>Haushaltsbogen importieren</DialogTitle>
            <DialogContent dividers>
                <Stepper activeStep={step} sx={{ mb: 3 }}>
                    {STEPS.map((label) => <Step key={label}><StepLabel>{label}</StepLabel></Step>)}
                </Stepper>

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                {step === 0 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Analyse-Ergebnis</Typography>
                        <Box sx={{ display: 'flex', gap: 3, mb: 2 }}>
                            <Typography>Gesamt: <strong>{analysis.total_rows}</strong> Zeilen</Typography>
                            <Typography>Übersprungen (nicht abgesendet): <strong>{analysis.skipped_not_submitted}</strong></Typography>
                            <Typography>Dubletten: <strong>{analysis.skipped_duplicates}</strong></Typography>
                            <Typography>Zu importieren: <strong>{analysis.households.length}</strong></Typography>
                        </Box>
                        {analysis.privacy_warnings.length > 0 && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                <strong>{analysis.privacy_warnings.length} Einträge ohne Datenschutz-Zustimmung gefunden.</strong>
                                {' '}Diese Einträge sollten auch in Nextcloud Forms gelöscht werden.
                                <ul>
                                    {analysis.privacy_warnings.map((w, i) => (
                                        <li key={i}>Zeile {w.row}: {w.name}</li>
                                    ))}
                                </ul>
                            </Alert>
                        )}
                        <Typography variant="body2" color="text.secondary">
                            Im nächsten Schritt können Sie für jeden Haushalt entscheiden: Neu anlegen, vorhandenen aktualisieren oder überspringen.
                        </Typography>
                    </Box>
                )}

                {step === 1 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Zuordnung & Entscheidungen</Typography>
                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Person 1</TableCell>
                                        <TableCell>MitglNr.</TableCell>
                                        <TableCell>Mitglieder</TableCell>
                                        <TableCell>Match</TableCell>
                                        <TableCell>Hinweise</TableCell>
                                        <TableCell>Aktion</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {analysis.households.map((hh) => {
                                        const p1 = hh.persons[0];
                                        const dec = decisions[hh.temp_id];
                                        return (
                                            <TableRow key={hh.temp_id}>
                                                <TableCell>{p1?.name ?? '—'}</TableCell>
                                                <TableCell>{p1?.member_number ?? '—'}</TableCell>
                                                <TableCell>
                                                    {hh.persons.length}
                                                    {hh.member_count_mismatch && !hh.already_imported && (
                                                        <Chip label="Abweichung" size="small" color="warning" sx={{ ml: 1 }} />
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={hh.match_result.type === 'none'
                                                            ? 'Kein Match'
                                                            : `${matchTypeLabel(hh.match_result.type)}: ${hh.match_result.matched_household_name ?? ''}`}
                                                        size="small"
                                                        color={matchColor(hh.match_result.type)}
                                                        onClick={hh.match_result.type === 'fuzzy' || hh.match_result.type === 'none'
                                                            ? () => setMatchingFor(hh) : undefined}
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    {hh.existing_data_changes?.data_removals?.length ? (
                                                        <Chip
                                                            label={`${hh.existing_data_changes.data_removals.length} Löschungen`}
                                                            size="small"
                                                            color="error"
                                                            onClick={() => setDataChangeFor(hh)}
                                                        />
                                                    ) : null}
                                                </TableCell>
                                                <TableCell>
                                                    <FormControl size="small" sx={{ minWidth: 140 }}>
                                                        <Select
                                                            value={dec?.action ?? 'create'}
                                                            onChange={(e) => updateDecision(hh.temp_id, {
                                                                action: e.target.value as 'create' | 'update' | 'skip',
                                                                target_household_id: e.target.value === 'update'
                                                                    ? hh.match_result.matched_household_id ?? undefined
                                                                    : undefined,
                                                            })}
                                                        >
                                                            <MenuItem value="create">Neu anlegen</MenuItem>
                                                            {hh.match_result.matched_household_id && (
                                                                <MenuItem value="update">Aktualisieren</MenuItem>
                                                            )}
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

                        {unconfirmedRemovals.length > 0 && (
                            <Alert severity="warning" sx={{ mt: 2 }}>
                                {unconfirmedRemovals.length} Haushalt(e) haben Daten-Löschungen, die noch nicht bestätigt wurden.
                                Klicken Sie auf den roten Chip, um die Änderungen zu bestätigen.
                            </Alert>
                        )}
                    </Box>
                )}

                {step === 2 && commitResult && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Import abgeschlossen</Typography>
                        <Alert severity="success" sx={{ mb: 2 }}>
                            <strong>{commitResult.imported}</strong> Haushalte neu angelegt,{' '}
                            <strong>{commitResult.updated}</strong> aktualisiert,{' '}
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
                        <Button
                            variant="contained"
                            onClick={handleCommit}
                            disabled={committing || unconfirmedRemovals.length > 0}
                        >
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
                    household={matchingFor}
                    onClose={() => setMatchingFor(null)}
                    onSelect={(householdId) => {
                        if (householdId) {
                            updateDecision(matchingFor.temp_id, {
                                action: 'update',
                                target_household_id: householdId,
                            });
                        } else {
                            updateDecision(matchingFor.temp_id, { action: 'create' });
                        }
                        setMatchingFor(null);
                    }}
                />
            )}

            {dataChangeFor && (
                <DataChangeDialog
                    open={!!dataChangeFor}
                    household={dataChangeFor}
                    onClose={() => setDataChangeFor(null)}
                    onConfirm={() => {
                        updateDecision(dataChangeFor.temp_id, { confirm_data_removals: true });
                        setDataChangeFor(null);
                    }}
                />
            )}
        </Dialog>
    );
}

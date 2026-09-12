import { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Stepper, Step, StepLabel, Typography, Box,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Chip, Alert, Tooltip,
    FormControl, Select, MenuItem, CircularProgress,
} from '@mui/material';
import {
    HHAnalysisResponse, HouseholdImportPreview, HouseholdDecision,
    HHCommitRequest, HHCommitResponse,
} from '../../types';
import { commitHHBogen } from '../../api';
import MatchingDialog from './MatchingDialog';
import { isCertainMatch, isUncertainMatch } from './matching';
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
            let action: 'update' | 'skip';
            let targetId: number | undefined;
            if (hh.already_imported) {
                action = 'skip';
            } else if (isCertainMatch(hh.match_result)) {
                action = 'update';
                targetId = hh.match_result.matched_household_id ?? undefined;
            } else {
                // Nur ein eindeutiger Treffer wird automatisch zugeordnet (siehe
                // matching.ts). Der Haushaltsbogen legt nichts an, deshalb ist
                // "Überspringen" hier die unschuldige Vorbelegung: der
                // Vorschlag bleibt sichtbar und auswählbar.
                action = 'skip';
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
    const [matchOverrides, setMatchOverrides] = useState<Record<string, string>>({});
    const [dataChangeFor, setDataChangeFor] = useState<HouseholdImportPreview | null>(null);
    const [committing, setCommitting] = useState(false);
    const [commitResult, setCommitResult] = useState<HHCommitResponse | null>(null);
    const [error, setError] = useState('');

    // Zeilen, deren Treffer nur ein Vorschlag ist und die deshalb nicht
    // vorausgewählt wurden (siehe matching.ts).
    const uncertainCount = analysis.households.filter(
        (hh) => !hh.already_imported && isUncertainMatch(hh.match_result),
    ).length;

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

                {analysis.missing_base_data_warning && step === 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Es sind noch keine Haushalte vorhanden. Bitte zuerst die
                        Mitgliederliste (vCard) importieren — der Haushaltsbogen
                        ergänzt nur bestehende Haushalte.
                    </Alert>
                )}

                {uncertainCount > 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        <strong>{uncertainCount} Zeile(n) mit nur ähnlichem Treffer.</strong>{' '}
                        Nur ein eindeutiger Treffer wird automatisch zugeordnet —
                        Mitgliedsnummer, exakter Name oder Wohnungsnummer. Ein nur ähnlicher
                        Name steht auf „Überspringen"; der Vorschlag lässt sich über den
                        Treffer-Chip prüfen und übernehmen.
                    </Alert>
                )}

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
                            Der Haushaltsbogen <strong>ergänzt bestehende Haushalte</strong> und legt
                            keine neuen an. Im nächsten Schritt entscheiden Sie je Datensatz:
                            vorhandenen Haushalt aktualisieren oder überspringen.
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
                                        <TableCell>Status</TableCell>
                                        <TableCell>Hinweise</TableCell>
                                        <TableCell>Aktion</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {analysis.households.map((hh) => {
                                        const p1 = hh.persons[0];
                                        const dec = decisions[hh.temp_id];
                                        return (
                                            <TableRow
                                                key={hh.temp_id}
                                                sx={hh.already_imported ? { opacity: 0.5, bgcolor: 'action.hover' } : undefined}
                                            >
                                                <TableCell>{p1?.name ?? '—'}</TableCell>
                                                <TableCell>{p1?.member_number ?? '—'}</TableCell>
                                                <TableCell>
                                                    {hh.persons.length}
                                                    {hh.member_count_mismatch && !hh.already_imported && (
                                                        <Chip label="Abweichung" size="small" color="warning" sx={{ ml: 1 }} />
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    {(() => {
                                                        const overrideName = matchOverrides[hh.temp_id];
                                                        return (
                                                            <Chip
                                                                label={overrideName
                                                                    ? `Zugeordnet: ${overrideName}`
                                                                    : hh.match_result.type === 'none'
                                                                        ? 'Kein Match'
                                                                        : `${matchTypeLabel(hh.match_result.type)}: ${hh.match_result.matched_household_name ?? ''}`}
                                                                size="small"
                                                                color={overrideName ? 'info' : matchColor(hh.match_result.type)}
                                                                onClick={() => setMatchingFor(hh)}
                                                            />
                                                        );
                                                    })()}
                                                </TableCell>
                                                <TableCell>
                                                    {hh.already_imported && (
                                                        <Tooltip title="Dieser Datensatz wurde bereits mit demselben Zeitstempel importiert.">
                                                            <Chip
                                                                label="Bereits importiert"
                                                                size="small"
                                                                color="default"
                                                                variant="outlined"
                                                            />
                                                        </Tooltip>
                                                    )}
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
                                                            value={dec?.action ?? 'skip'}
                                                            onChange={(e) => updateDecision(hh.temp_id, {
                                                                action: e.target.value as 'update' | 'skip',
                                                                target_household_id: e.target.value === 'update'
                                                                    ? dec?.target_household_id
                                                                        ?? hh.match_result.matched_household_id ?? undefined
                                                                    : undefined,
                                                            })}
                                                        >
                                                            {(dec?.target_household_id || hh.match_result.matched_household_id) && (
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
                            <strong>{commitResult.updated}</strong> Haushalte ergänzt,{' '}
                            <strong>{commitResult.skipped}</strong> übersprungen.
                        </Alert>
                        {commitResult.skipped_no_match > 0 && (
                            <Alert severity="info">
                                <strong>{commitResult.skipped_no_match}</strong> Datensätze ohne
                                zugeordneten Haushalt wurden nicht übernommen — der Haushaltsbogen
                                legt keine neuen Haushalte an.
                            </Alert>
                        )}
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
                    title={`Haushalt zuordnen: ${matchingFor.persons[0]?.name ?? '—'}`}
                    description={`Personen im importierten Haushalt: ${matchingFor.persons.map((p) => `${p.name} (MitglNr: ${p.member_number || '—'})`).join(', ')}`}
                    candidates={matchingFor.match_result.fuzzy_candidates || []}
                    createButtonLabel="Nicht zuordnen (überspringen)"
                    onClose={() => setMatchingFor(null)}
                    onSelect={(householdId, name) => {
                        if (householdId) {
                            updateDecision(matchingFor.temp_id, {
                                action: 'update',
                                target_household_id: householdId,
                            });
                            setMatchOverrides((prev) => ({ ...prev, [matchingFor.temp_id]: name || '' }));
                        } else {
                            updateDecision(matchingFor.temp_id, {
                                action: 'skip',
                                target_household_id: undefined,
                            });
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

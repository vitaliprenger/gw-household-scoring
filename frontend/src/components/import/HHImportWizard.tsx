import { useEffect, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Stepper, Step, StepLabel, Typography, Box,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Chip, Alert, Tooltip,
    FormControl, Select, MenuItem, CircularProgress,
} from '@mui/material';
import {
    HHAnalysisResponse, HouseholdImportPreview, HouseholdDecision,
    HHCommitRequest, HHCommitResponse, MatchResult,
} from '../../types';
import { commitHHBogen, getHouseholds } from '../../api';
import MatchingDialog, { MatchOption } from './MatchingDialog';
import { isCertainMatch, isUncertainMatch } from './matching';
import DataChangeDialog from './DataChangeDialog';
import BogenPersons, { similarPersonText } from './BogenPersons';

interface HHImportWizardProps {
    open: boolean;
    analysis: HHAnalysisResponse;
    onClose: () => void;
    onComplete: () => void;
}

const STEPS = ['Analyse', 'Zuordnung & Entscheidungen', 'Zusammenfassung'];

const WISH_NOT_APPLIED_HINT =
    'Wunsch nicht übernommen – Bewohner-Haushalt; Wechselwunsch bitte von Hand anlegen';

function matchTypeLabel(type: string): string {
    switch (type) {
        case 'exact_member_nr': return 'Mitgliedsnr.';
        case 'exact_name_dob': return 'Name';
        case 'fuzzy': return 'Vorschlag';
        case 'several_households': return 'Mehrere Haushalte';
        case 'none': return 'Kein Match';
        default: return type;
    }
}

function matchColor(match: MatchResult): 'success' | 'warning' | 'info' | 'default' {
    if (isCertainMatch(match)) return 'success';
    return isUncertainMatch(match) ? 'warning' : 'default';
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
                // matching.ts). "Überspringen" ist die unschuldige Vorbelegung:
                // der Vorschlag bleibt sichtbar, und "Neu anlegen" ist immer
                // eine bewusste Wahl je Zeile (ADR 0011). Eine unentschiedene
                // Zeile bewirkt so nichts, deshalb sperrt der Assistent nicht.
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
    // Alle Haushalte, damit sich eine Zeile auch einem zuordnen lässt, der ihr
    // nicht ähnlich ist. Ohne die Liste bleibt es bei den Vorschlägen.
    const [allHouseholds, setAllHouseholds] = useState<MatchOption[]>([]);
    useEffect(() => {
        getHouseholds()
            .then((households) => setAllHouseholds(households.map((hh) => ({
                id: hh.id,
                name: hh.name,
                member_numbers: hh.people
                    .map((p) => p.member_number)
                    .filter((nr): nr is string => !!nr),
            }))))
            .catch(() => setAllHouseholds([]));
    }, []);
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

                {uncertainCount > 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        <strong>{uncertainCount} Zeile(n) mit unsicherem Treffer.</strong>{' '}
                        Automatisch zugeordnet wird nur bei gleichem Namen oder bei einer
                        Mitgliedsnummer, zu der Name und Geburtsdatum passen, und nur, wenn
                        alle gefundenen Personen im selben Haushalt stehen. Alles andere
                        steht auf „Überspringen"; der Vorschlag lässt sich über den
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
                            Der Haushaltsbogen <strong>ergänzt bestehende Haushalte</strong>. Findet
                            er keinen passenden Haushalt, steht die Zeile auf „Überspringen“; im
                            nächsten Schritt lässt sich je Zeile ein Haushalt zuordnen oder mit
                            „Neu anlegen“ ein neuer Haushalt samt Personen und Wartepool-Bewerbung
                            anlegen.
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
                                        <TableCell>Personen (Vorname | Nachname)</TableCell>
                                        <TableCell>Match</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Hinweise</TableCell>
                                        <TableCell>Aktion</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {analysis.households.map((hh) => {
                                        const dec = decisions[hh.temp_id];
                                        const proposed = hh.match_result.matched_household_id;
                                        // Vorschau und Hinweise gelten für den vorgeschlagenen
                                        // Haushalt; nach der Zuordnung zu einem anderen zählt
                                        // die Zusammenfassung.
                                        const forProposed = (dec?.target_household_id ?? proposed) === proposed;
                                        const creating = dec?.action === 'create';
                                        // Neu angelegt wird nur, wo kein Haushalt sicher passt.
                                        const mayCreate = hh.create_allowed && !hh.already_imported
                                            && !isCertainMatch(hh.match_result);
                                        const cannotCreate = !hh.create_allowed && !hh.already_imported
                                            && !isCertainMatch(hh.match_result);
                                        return (
                                            <TableRow
                                                key={hh.temp_id}
                                                sx={hh.already_imported ? { opacity: 0.5, bgcolor: 'action.hover' } : undefined}
                                            >
                                                <TableCell>
                                                    <BogenPersons
                                                        persons={creating ? hh.persons_if_created : hh.persons}
                                                        showOutcome={!hh.already_imported
                                                            && (creating || (!!proposed && forProposed))}
                                                    />
                                                    {creating && (
                                                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                                                            Neuer Haushalt: „{hh.suggested_household_name}“
                                                        </Typography>
                                                    )}
                                                    {hh.member_count_mismatch && !hh.already_imported && (
                                                        <Tooltip title={`Angegebene Haushaltsgröße: ${hh.declared_member_count}. Der Bogen führt aber ${hh.persons.length} Personen auf.`}>
                                                            <Chip label="weicht von der angegebenen Haushaltsgröße ab" size="small" color="warning" sx={{ mt: 0.5 }} />
                                                        </Tooltip>
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
                                                                color={overrideName ? 'info' : matchColor(hh.match_result)}
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
                                                    {hh.existing_data_changes?.data_removals?.length && !creating ? (
                                                        <Chip
                                                            label={`${hh.existing_data_changes.data_removals.length} Löschungen`}
                                                            size="small"
                                                            color="error"
                                                            onClick={() => setDataChangeFor(hh)}
                                                        />
                                                    ) : null}
                                                    {hh.unparsed_wishes.length > 0 && !hh.already_imported && (
                                                        <Tooltip title={`Nicht erkannt: ${hh.unparsed_wishes.join(', ')}. Bitte den Wunsch in der Bewerbung von Hand nachtragen.`}>
                                                            <Chip
                                                                label="Wunsch nicht erkannt"
                                                                size="small"
                                                                color="warning"
                                                                variant="outlined"
                                                            />
                                                        </Tooltip>
                                                    )}
                                                    {creating && hh.no_member_number && (
                                                        <Tooltip title="Kein Mitglied im Bogen genannt. Vergeben wird nur an Mitglieder.">
                                                            <Chip
                                                                label="keine Mitgliedsnummer angegeben"
                                                                size="small"
                                                                color="warning"
                                                                variant="outlined"
                                                            />
                                                        </Tooltip>
                                                    )}
                                                    {cannotCreate && (
                                                        <Tooltip title="Alle Personen des Bogens stehen schon in anderen Haushalten. Erst die Personen umziehen, dann den Bogen erneut einlesen.">
                                                            <Chip
                                                                label="Neu anlegen nicht möglich"
                                                                size="small"
                                                                variant="outlined"
                                                            />
                                                        </Tooltip>
                                                    )}
                                                    {hh.wish_not_applied && !hh.already_imported && forProposed && !creating && (
                                                        <Tooltip title={WISH_NOT_APPLIED_HINT}>
                                                            <Chip
                                                                label="Wunsch nicht übernommen"
                                                                size="small"
                                                                color="warning"
                                                                variant="outlined"
                                                            />
                                                        </Tooltip>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <FormControl size="small" sx={{ minWidth: 140 }}>
                                                        <Select
                                                            value={dec?.action ?? 'skip'}
                                                            onChange={(e) => {
                                                                const action = e.target.value as HouseholdDecision['action'];
                                                                updateDecision(hh.temp_id, {
                                                                    action,
                                                                    target_household_id: action === 'update'
                                                                        ? dec?.target_household_id
                                                                            ?? hh.match_result.matched_household_id ?? undefined
                                                                        : undefined,
                                                                });
                                                                if (action !== 'update') {
                                                                    // Eine Zuordnung von Hand gilt nicht mehr.
                                                                    setMatchOverrides((prev) => {
                                                                        const next = { ...prev };
                                                                        delete next[hh.temp_id];
                                                                        return next;
                                                                    });
                                                                }
                                                            }}
                                                        >
                                                            {(dec?.target_household_id || hh.match_result.matched_household_id) && (
                                                                <MenuItem value="update">Aktualisieren</MenuItem>
                                                            )}
                                                            {mayCreate && (
                                                                <MenuItem value="create">Neu anlegen</MenuItem>
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
                            <strong>{commitResult.households_created}</strong> Haushalte neu angelegt,{' '}
                            <strong>{commitResult.updated}</strong> ergänzt,{' '}
                            <strong>{commitResult.skipped}</strong> Zeilen übersprungen.{' '}
                            <strong>{commitResult.applications_created}</strong> Wartepool-Bewerbungen angelegt.{' '}
                            <strong>{commitResult.persons_created}</strong> Personen neu angelegt,{' '}
                            <strong>{commitResult.persons_assigned}</strong> aus dem Datenbestand zugeordnet.
                        </Alert>
                        {commitResult.persons_not_taken_over.length > 0 && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                <strong>Nicht übernommen – bitte von Hand umziehen:</strong>
                                <ul>
                                    {commitResult.persons_not_taken_over.map((entry, i) => (
                                        <li key={i}>{entry.person} bleibt im Haushalt „{entry.household}“</li>
                                    ))}
                                </ul>
                            </Alert>
                        )}
                        {commitResult.similar_persons.length > 0 && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                <strong>Neu angelegt, obwohl es eine ähnliche Person im Datenbestand gibt:</strong>
                                <ul>
                                    {commitResult.similar_persons.map((entry, i) => (
                                        <li key={i}>
                                            {entry.person} – {entry.similar.map(similarPersonText).join('; ')}
                                        </li>
                                    ))}
                                </ul>
                            </Alert>
                        )}
                        {commitResult.member_numbers_not_stored.length > 0 && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                <strong>Mitgliedsnummer nicht gespeichert, weil sie schon vergeben ist:</strong>
                                <ul>
                                    {commitResult.member_numbers_not_stored.map((conflict, i) => (
                                        <li key={i}>
                                            {conflict.person}: Nummer {conflict.member_number} trägt
                                            schon {conflict.holder}
                                        </li>
                                    ))}
                                </ul>
                            </Alert>
                        )}
                        {commitResult.skipped_no_match > 0 && (
                            <Alert severity="info" sx={{ mb: 2 }}>
                                <strong>{commitResult.skipped_no_match}</strong> Datensätze ohne
                                zugeordneten Haushalt wurden nicht übernommen.
                            </Alert>
                        )}
                        {commitResult.wishes_not_applied.length > 0 && (
                            <Alert severity="warning">
                                <strong>{WISH_NOT_APPLIED_HINT}:</strong>
                                <ul>
                                    {commitResult.wishes_not_applied.map((name, i) => (
                                        <li key={i}>{name}</li>
                                    ))}
                                </ul>
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
                    allOptions={allHouseholds}
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

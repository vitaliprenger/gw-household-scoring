import { useMemo, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions, Button, Box, Typography,
    Table, TableBody, TableCell, TableHead, TableRow, Chip, Select, MenuItem,
    Alert, TextField, FormControl, InputLabel, OutlinedInput, Checkbox,
    ListItemText, Tooltip, Stack,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
    ApplicationAnalysisResponse, ApplicationCommitResponse, ApplicationDecision,
    ApplicationImportPreview, APPLICATION_KIND_LABELS, APPLICATION_STATUS_LABELS,
} from '../../types';
import { commitApplicationList } from '../../api';
import { wishLabel } from '../applications/wishes';
import {
    isCertainMatch, isUncertainMatch, uncertainMatchHint, UNDECIDED, UNDECIDED_LABEL,
} from './matching';

interface ApplicationImportWizardProps {
    open: boolean;
    analysis: ApplicationAnalysisResponse;
    onClose: () => void;
    onComplete: () => void;
}

type RowDecision = {
    action: string;
    householdName: string;
    personIds: number[];
};

/**
 * Vorbelegung je Zeile.
 *
 * Zugeordnet wird nur bei einem eindeutigen Treffer (siehe matching.ts). Bei einem
 * unsicheren Treffer wäre weder "Bewerbung anlegen" (falscher Haushalt) noch
 * "Haushalt neu anlegen" (Dublette) unschuldig — die Zeile braucht eine
 * ausdrückliche Entscheidung. Ohne jeden Treffer ist "Haushalt neu anlegen"
 * richtig: genau dafür gibt es diesen Import.
 */
function defaultDecision(preview: ApplicationImportPreview): RowDecision {
    let action: string;
    if (isUncertainMatch(preview.match_result)) {
        action = UNDECIDED;
    } else if (isCertainMatch(preview.match_result)) {
        action = preview.existing_application_id ? 'update' : 'create';
    } else {
        action = 'create_household';
    }
    return {
        action,
        householdName: preview.suggested_household_name,
        // Personen ohne Haushalt werden nur bei voller Namensgleichheit
        // vorausgewählt -- auch hier keine Automatik bei nur ähnlichen Namen.
        personIds: preview.person_candidates
            .filter((c) => c.score >= 1)
            .map((c) => c.person_id),
    };
}

export default function ApplicationImportWizard({
    open, analysis, onClose, onComplete,
}: ApplicationImportWizardProps) {
    const [decisions, setDecisions] = useState<Record<string, RowDecision>>(
        () => Object.fromEntries(analysis.households.map((p) => [p.temp_id, defaultDecision(p)])),
    );
    const [result, setResult] = useState<ApplicationCommitResponse | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const warnings = useMemo(() => ({
        unparsed: analysis.households.filter((p) => p.unparsed_wishes.length > 0).length,
        mismatch: analysis.households.filter((p) => p.apartment_mismatch).length,
        unknownApartment: analysis.households.filter((p) => p.unknown_apartment).length,
        newHouseholds: Object.values(decisions).filter((d) => d.action === 'create_household').length,
    }), [analysis, decisions]);

    // Zeilen, über die noch entschieden werden muss.
    const undecided = analysis.households.filter(
        (p) => decisions[p.temp_id]?.action === UNDECIDED,
    );

    function resolveAllUndecided(action: string) {
        setDecisions((prev) => Object.fromEntries(
            Object.entries(prev).map(([id, dec]) => [
                id, dec.action === UNDECIDED ? { ...dec, action } : dec,
            ]),
        ));
    }

    function setDecision(tempId: string, patch: Partial<RowDecision>) {
        setDecisions((prev) => ({ ...prev, [tempId]: { ...prev[tempId], ...patch } }));
    }

    async function handleCommit() {
        setBusy(true);
        setError('');
        const payload: ApplicationDecision[] = analysis.households.map((preview) => {
            const decision = decisions[preview.temp_id];
            return {
                temp_id: preview.temp_id,
                action: decision.action,
                target_household_id: decision.action === 'create' || decision.action === 'update'
                    ? preview.match_result.matched_household_id
                    : undefined,
                household_name: decision.householdName,
                person_ids: decision.action === 'create_household' ? decision.personIds : [],
            };
        });
        try {
            setResult(await commitApplicationList({
                session_id: analysis.session_id, decisions: payload,
            }));
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Übernahme fehlgeschlagen');
        } finally {
            setBusy(false);
        }
    }

    if (result) {
        return (
            <Dialog open={open} onClose={onComplete} maxWidth="sm" fullWidth>
                <DialogTitle>Bewerbungsliste übernommen</DialogTitle>
                <DialogContent>
                    <Stack spacing={1} sx={{ mt: 1 }}>
                        <Typography>{result.applications_created} Bewerbungen angelegt</Typography>
                        <Typography>{result.applications_updated} Bewerbungen aktualisiert</Typography>
                        <Typography>{result.households_created} Haushalte neu angelegt</Typography>
                        <Typography>{result.persons_assigned} Personen zugeordnet</Typography>
                        <Typography color="text.secondary">
                            {result.skipped} übersprungen, {result.skipped_no_match} ohne
                            zuordenbaren Haushalt
                        </Typography>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button variant="contained" onClick={onComplete}>Schließen</Button>
                </DialogActions>
            </Dialog>
        );
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
            <DialogTitle>Bewerbungsliste importieren</DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                <Alert severity="info" sx={{ mb: 2 }}>
                    {analysis.households.length} Zeilen gelesen
                    {analysis.skipped_empty > 0 && `, ${analysis.skipped_empty} leere übersprungen`}.
                    „Aktueller Typ" und „Aktuelle Wohnung" werden nicht gespeichert — sie ergeben
                    sich aus der Wohnungszuordnung und dienen hier nur dem Abgleich.
                </Alert>
                {undecided.length > 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        <strong>{undecided.length} Zeile(n) mit nur ähnlichem Treffer.</strong>{' '}
                        Automatisch zugeordnet wird nur bei Mitgliedsnummer, exaktem Namen
                        oder Wohnungsnummer — hier passt der Name nur ungefähr, und
                        „Haushalt neu anlegen" würde hier eine Dublette erzeugen. Bitte je Zeile
                        entscheiden; die Übernahme bleibt bis dahin gesperrt.
                        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                            <Button size="small" variant="outlined"
                                onClick={() => resolveAllUndecided('create_household')}>
                                Alle neu anlegen
                            </Button>
                            <Button size="small" variant="outlined"
                                onClick={() => resolveAllUndecided('skip')}>
                                Alle überspringen
                            </Button>
                        </Box>
                    </Alert>
                )}
                {warnings.unparsed > 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Bei {warnings.unparsed} Zeile(n) konnte ein Teil der Wunsch-Angabe nicht
                        aufgelöst werden. Diese Teile werden <strong>nicht</strong> übernommen;
                        der Wunsch lässt sich nach dem Import im Bewerbungen-Tab ergänzen.
                    </Alert>
                )}
                {warnings.mismatch > 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Bei {warnings.mismatch} Zeile(n) weicht die Wohnung der Liste von der
                        Wohnungszuordnung im Tool ab.
                    </Alert>
                )}
                {warnings.newHouseholds > 0 && (
                    <Alert severity="info" sx={{ mb: 2 }}>
                        {warnings.newHouseholds} Haushalt(e) werden neu angelegt. Wähle je Zeile die
                        bereits vorhandenen Personen ohne Haushalt aus, damit keine Dubletten zu den
                        Personen aus der vCard entstehen.
                    </Alert>
                )}

                <Box sx={{ overflowX: 'auto' }}>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Zeile</TableCell>
                                <TableCell>Haushalt (Liste)</TableCell>
                                <TableCell>Typ</TableCell>
                                <TableCell>Wunsch</TableCell>
                                <TableCell>Seit</TableCell>
                                <TableCell>Status</TableCell>
                                <TableCell>Wohnung</TableCell>
                                <TableCell>Treffer im Tool</TableCell>
                                <TableCell>Aktion</TableCell>
                                <TableCell>Personen / Name</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {analysis.households.map((preview) => {
                                const decision = decisions[preview.temp_id];
                                const matched = preview.match_result.matched_household_id;
                                return (
                                    <TableRow key={preview.temp_id} hover>
                                        <TableCell>{preview.row}</TableCell>
                                        <TableCell>{preview.raw_household}</TableCell>
                                        <TableCell>
                                            <Chip size="small" label={APPLICATION_KIND_LABELS[preview.kind]} />
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                                {preview.wishes.map((w, i) => (
                                                    <Chip key={i} size="small" variant="outlined" label={wishLabel(w)} />
                                                ))}
                                                {preview.unparsed_wishes.map((raw) => (
                                                    <Tooltip key={raw} title="Nicht erkannt — wird nicht übernommen">
                                                        <Chip size="small" color="warning" label={raw} />
                                                    </Tooltip>
                                                ))}
                                            </Box>
                                        </TableCell>
                                        <TableCell>{preview.requested_at ?? '—'}</TableCell>
                                        <TableCell>
                                            {APPLICATION_STATUS_LABELS[preview.status]}
                                        </TableCell>
                                        <TableCell>
                                            {preview.raw_current_unit ?? '—'}
                                            {preview.raw_new_unit && ` → ${preview.raw_new_unit}`}
                                            {(preview.apartment_mismatch || preview.unknown_apartment) && (
                                                <Tooltip title={preview.unknown_apartment
                                                    ? 'Wohnungsnummer existiert nicht in den Stammdaten'
                                                    : 'Weicht von der Wohnungszuordnung im Tool ab'}>
                                                    <WarningAmberIcon
                                                        color="warning" fontSize="small"
                                                        sx={{ verticalAlign: 'middle', ml: 0.5 }}
                                                    />
                                                </Tooltip>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            {matched ? (
                                                <Tooltip title={isCertainMatch(preview.match_result)
                                                    ? 'Eindeutiger Treffer'
                                                    : uncertainMatchHint(preview.match_result)}>
                                                    <Chip
                                                        size="small"
                                                        label={preview.match_result.matched_household_name ?? 'Treffer'}
                                                        color={isCertainMatch(preview.match_result)
                                                            ? 'success' : 'warning'}
                                                    />
                                                </Tooltip>
                                            ) : '—'}
                                            {preview.existing_application_id && (
                                                <Tooltip title={'Diese Zeile ist bereits als Bewerbung '
                                                    + 'vorhanden (gleiche Art, gleicher Zeitpunkt) und '
                                                    + 'wird aktualisiert statt doppelt angelegt.'}>
                                                    <Chip
                                                        size="small" sx={{ ml: 0.5 }}
                                                        label="vorhandene Bewerbung"
                                                    />
                                                </Tooltip>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Select
                                                size="small"
                                                value={decision.action}
                                                error={decision.action === UNDECIDED}
                                                onChange={(e) => setDecision(preview.temp_id, {
                                                    action: e.target.value,
                                                })}
                                                sx={{ minWidth: 190 }}
                                            >
                                                {decision.action === UNDECIDED && (
                                                    <MenuItem value={UNDECIDED}>{UNDECIDED_LABEL}</MenuItem>
                                                )}
                                                <MenuItem value="update" disabled={!preview.existing_application_id}>
                                                    Bewerbung aktualisieren
                                                </MenuItem>
                                                <MenuItem value="create" disabled={!matched}>
                                                    Bewerbung anlegen
                                                </MenuItem>
                                                <MenuItem value="create_household">
                                                    Haushalt neu anlegen
                                                </MenuItem>
                                                <MenuItem value="skip">Überspringen</MenuItem>
                                            </Select>
                                        </TableCell>
                                        <TableCell>
                                            {decision.action === 'create_household' ? (
                                                <Stack spacing={1} sx={{ minWidth: 260 }}>
                                                    <TextField
                                                        size="small" label="Haushaltsname"
                                                        value={decision.householdName}
                                                        onChange={(e) => setDecision(preview.temp_id, {
                                                            householdName: e.target.value,
                                                        })}
                                                    />
                                                    <FormControl size="small" fullWidth>
                                                        <InputLabel id={`p-${preview.temp_id}`}>
                                                            Personen ohne Haushalt
                                                        </InputLabel>
                                                        <Select
                                                            labelId={`p-${preview.temp_id}`}
                                                            multiple
                                                            value={decision.personIds}
                                                            input={<OutlinedInput label="Personen ohne Haushalt" />}
                                                            onChange={(e) => setDecision(preview.temp_id, {
                                                                personIds: e.target.value as number[],
                                                            })}
                                                            renderValue={(selected) =>
                                                                preview.person_candidates
                                                                    .filter((c) => (selected as number[]).includes(c.person_id))
                                                                    .map((c) => c.name).join(', ')}
                                                        >
                                                            {preview.person_candidates.length === 0 && (
                                                                <MenuItem disabled value={-1}>
                                                                    Keine passende Person gefunden
                                                                </MenuItem>
                                                            )}
                                                            {preview.person_candidates.map((candidate) => (
                                                                <MenuItem key={candidate.person_id} value={candidate.person_id}>
                                                                    <Checkbox
                                                                        checked={decision.personIds.includes(candidate.person_id)}
                                                                    />
                                                                    <ListItemText
                                                                        primary={candidate.name}
                                                                        secondary={candidate.member_number
                                                                            ? `Nr. ${candidate.member_number}`
                                                                            : undefined}
                                                                    />
                                                                </MenuItem>
                                                            ))}
                                                        </Select>
                                                    </FormControl>
                                                </Stack>
                                            ) : (
                                                <Typography variant="body2" color="text.secondary">—</Typography>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </Box>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button
                    variant="contained" onClick={handleCommit}
                    disabled={busy || undecided.length > 0}
                >
                    {busy ? 'Übernehme...'
                        : undecided.length > 0
                            ? `${undecided.length} Zuordnung(en) offen`
                            : 'Übernehmen'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

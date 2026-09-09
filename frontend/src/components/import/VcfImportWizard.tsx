import { useMemo, useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Stepper, Step, StepLabel, Typography, Box,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Chip, Alert, FormControl, Select, MenuItem, CircularProgress,
    IconButton, Collapse, Checkbox, Tooltip, TextField, FormControlLabel,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRightIcon from '@mui/icons-material/KeyboardArrowRight';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
    VcfAnalysisResponse, VcfHouseholdPreview, VcfDecision, VcfCommitRequest, VcfCommitResponse,
} from '../../types';
import { commitVcf } from '../../api';
import MatchingDialog from './MatchingDialog';

interface VcfImportWizardProps {
    open: boolean;
    analysis: VcfAnalysisResponse;
    onClose: () => void;
    onComplete: () => void;
}

const STEPS = ['Analyse', 'Zuordnung', 'Zusammenfassung'];

const ROLE_LABELS: Record<string, string> = {
    member: 'Mitglied',
    partner: 'Partner*in',
    child: 'Kind',
};

function formatDate(value?: string): string {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('de-DE');
}

export default function VcfImportWizard({ open, analysis, onClose, onComplete }: VcfImportWizardProps) {
    const [step, setStep] = useState(0);
    const [decisions, setDecisions] = useState<Record<string, VcfDecision>>(() => {
        const init: Record<string, VcfDecision> = {};
        for (const hh of analysis.households) {
            init[hh.temp_id] = {
                temp_id: hh.temp_id,
                action: hh.already_imported
                    ? 'skip'
                    : hh.match_result.matched_household_id
                        ? 'update'
                        : hh.apartment_unit ? 'create' : 'skip',
                target_household_id: hh.match_result.matched_household_id ?? undefined,
                excluded_person_temp_ids: [],
            };
        }
        return init;
    });
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const [matchingFor, setMatchingFor] = useState<VcfHouseholdPreview | null>(null);
    const [matchOverrides, setMatchOverrides] = useState<Record<string, string>>({});
    const [search, setSearch] = useState('');
    const [onlyProblems, setOnlyProblems] = useState(false);
    const [committing, setCommitting] = useState(false);
    const [commitResult, setCommitResult] = useState<VcfCommitResponse | null>(null);
    const [error, setError] = useState('');

    const visibleHouseholds = useMemo(() => {
        const term = search.trim().toLowerCase();
        return analysis.households.filter((hh) => {
            if (onlyProblems && hh.warnings.length === 0) return false;
            if (!term) return true;
            if (hh.name.toLowerCase().includes(term)) return true;
            if ((hh.apartment_unit || '').toLowerCase().includes(term)) return true;
            return hh.persons.some((p) =>
                p.name.toLowerCase().includes(term) ||
                (p.member_number || '').includes(term)
            );
        });
    }, [analysis.households, search, onlyProblems]);

    const counts = useMemo(() => {
        const values = Object.values(decisions);
        return {
            create: values.filter((d) => d.action === 'create').length,
            update: values.filter((d) => d.action === 'update').length,
            skip: values.filter((d) => d.action === 'skip').length,
        };
    }, [decisions]);

    function updateDecision(tempId: string, patch: Partial<VcfDecision>) {
        setDecisions((prev) => ({ ...prev, [tempId]: { ...prev[tempId], ...patch } }));
    }

    function togglePerson(tempId: string, personTempId: string) {
        const current = decisions[tempId]?.excluded_person_temp_ids ?? [];
        const next = current.includes(personTempId)
            ? current.filter((id) => id !== personTempId)
            : [...current, personTempId];
        updateDecision(tempId, { excluded_person_temp_ids: next });
    }

    async function handleCommit() {
        setCommitting(true);
        setError('');
        try {
            const request: VcfCommitRequest = {
                session_id: analysis.session_id,
                decisions: Object.values(decisions),
            };
            setCommitResult(await commitVcf(request));
            setStep(2);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Import fehlgeschlagen');
        } finally {
            setCommitting(false);
        }
    }

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>Mitgliederliste (vCard) importieren</DialogTitle>
            <DialogContent dividers>
                <Stepper activeStep={step} sx={{ mb: 3 }}>
                    {STEPS.map((label) => <Step key={label}><StepLabel>{label}</StepLabel></Step>)}
                </Stepper>

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                {step === 0 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Analyse-Ergebnis</Typography>
                        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 2 }}>
                            <Typography>Kontakte: <strong>{analysis.total_cards}</strong></Typography>
                            <Typography>Personen gesamt: <strong>{analysis.total_persons}</strong></Typography>
                            <Typography>Haushalte: <strong>{analysis.households.length}</strong></Typography>
                            <Typography>davon Bewohner: <strong>{analysis.resident_households}</strong></Typography>
                        </Box>
                        {analysis.skipped_no_name > 0 && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                {analysis.skipped_no_name} Kontakte ohne Namen wurden übersprungen.
                            </Alert>
                        )}
                        <Alert severity="info">
                            Haushalte werden über die <strong>Wohnungsnummer</strong> aus der Adresse
                            gebildet — alle Personen derselben Wohnung gelten als ein Haushalt und
                            werden als <strong>aktuelle Bewohner</strong> markiert. Für Personen ohne
                            Wohnungsnummer werden die im Notizfeld genannten Partnerschaften genutzt.
                            Partner*innen und Kinder aus dem Notizfeld sind Schätzungen aus Freitext —
                            bitte im nächsten Schritt prüfen und ggf. abwählen.
                        </Alert>
                    </Box>
                )}

                {step === 1 && (
                    <Box>
                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
                            <TextField
                                label="Suche (Name, Wohnung, Mitgliedsnummer)"
                                size="small"
                                sx={{ minWidth: 320 }}
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                            />
                            <FormControlLabel
                                control={<Checkbox
                                    checked={onlyProblems}
                                    onChange={(e) => setOnlyProblems(e.target.checked)}
                                />}
                                label="Nur mit Hinweisen"
                            />
                            <Box sx={{ flexGrow: 1 }} />
                            <Typography variant="body2" color="text.secondary">
                                {counts.create} neu · {counts.update} aktualisieren · {counts.skip} überspringen
                            </Typography>
                        </Box>

                        <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 460 }}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{ width: 40 }} />
                                        <TableCell>Haushalt</TableCell>
                                        <TableCell>Wohnung</TableCell>
                                        <TableCell align="right">Personen</TableCell>
                                        <TableCell>Match</TableCell>
                                        <TableCell>Aktion</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {visibleHouseholds.map((hh) => {
                                        const dec = decisions[hh.temp_id];
                                        const excluded = dec?.excluded_person_temp_ids ?? [];
                                        const isOpen = !!expanded[hh.temp_id];
                                        const overrideName = matchOverrides[hh.temp_id];
                                        const mt = hh.match_result.type;
                                        return [
                                            <TableRow
                                                key={hh.temp_id}
                                                sx={hh.already_imported ? { opacity: 0.5, bgcolor: 'action.hover' } : undefined}
                                            >
                                                <TableCell>
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => setExpanded((prev) => ({
                                                            ...prev, [hh.temp_id]: !prev[hh.temp_id],
                                                        }))}
                                                    >
                                                        {isOpen ? <KeyboardArrowDownIcon /> : <KeyboardArrowRightIcon />}
                                                    </IconButton>
                                                </TableCell>
                                                <TableCell>
                                                    {hh.name}
                                                    {hh.warnings.length > 0 && (
                                                        <Tooltip title={hh.warnings.join(' · ')}>
                                                            <WarningAmberIcon
                                                                color="warning"
                                                                fontSize="small"
                                                                sx={{ ml: 1, verticalAlign: 'middle' }}
                                                            />
                                                        </Tooltip>
                                                    )}
                                                    {hh.already_imported && (
                                                        <Chip
                                                            label="Bereits importiert"
                                                            size="small"
                                                            variant="outlined"
                                                            sx={{ ml: 1 }}
                                                        />
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    {hh.apartment_unit
                                                        ? <Chip label={hh.apartment_unit} size="small" color="success" />
                                                        : <Typography variant="body2" color="text.secondary">kein Bewohner</Typography>}
                                                </TableCell>
                                                <TableCell align="right">
                                                    {hh.persons.length - excluded.length}
                                                </TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={overrideName
                                                            ? `Zugeordnet: ${overrideName}`
                                                            : mt === 'none'
                                                                ? 'Kein Match'
                                                                : hh.match_result.matched_household_name ?? 'Match'}
                                                        size="small"
                                                        color={overrideName ? 'info'
                                                            : mt === 'exact_member_nr' || mt === 'exact_name_dob' ? 'success'
                                                                : mt === 'fuzzy' ? 'warning' : 'default'}
                                                        onClick={() => setMatchingFor(hh)}
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <FormControl size="small" sx={{ minWidth: 140 }}>
                                                        <Select
                                                            value={dec?.action ?? 'create'}
                                                            onChange={(e) => updateDecision(hh.temp_id, {
                                                                action: e.target.value as VcfDecision['action'],
                                                            })}
                                                        >
                                                            {dec?.target_household_id && (
                                                                <MenuItem value="update">Aktualisieren</MenuItem>
                                                            )}
                                                            {hh.apartment_unit && (
                                                                <MenuItem value="create">Neu anlegen</MenuItem>
                                                            )}
                                                            <MenuItem value="skip">Überspringen</MenuItem>
                                                        </Select>
                                                    </FormControl>
                                                </TableCell>
                                            </TableRow>,
                                            <TableRow key={`${hh.temp_id}-detail`}>
                                                <TableCell colSpan={6} sx={{ py: 0, borderBottom: isOpen ? undefined : 'none' }}>
                                                    <Collapse in={isOpen} unmountOnExit>
                                                        <Box sx={{ my: 2 }}>
                                                            {hh.warnings.map((w) => (
                                                                <Alert key={w} severity="warning" sx={{ mb: 1 }}>{w}</Alert>
                                                            ))}
                                                            {hh.address && (
                                                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                                                    Adresse: {hh.address}
                                                                </Typography>
                                                            )}
                                                            <Table size="small">
                                                                <TableHead>
                                                                    <TableRow>
                                                                        <TableCell sx={{ width: 60 }}>Import</TableCell>
                                                                        <TableCell>Name</TableCell>
                                                                        <TableCell>Rolle</TableCell>
                                                                        <TableCell>Geburtsdatum</TableCell>
                                                                        <TableCell>Geschlecht</TableCell>
                                                                        <TableCell>MitglNr.</TableCell>
                                                                        <TableCell>Mitglied seit</TableCell>
                                                                        <TableCell>Quelle</TableCell>
                                                                    </TableRow>
                                                                </TableHead>
                                                                <TableBody>
                                                                    {hh.persons.map((p) => (
                                                                        <TableRow key={p.temp_id}>
                                                                            <TableCell>
                                                                                <Checkbox
                                                                                    size="small"
                                                                                    checked={!excluded.includes(p.temp_id)}
                                                                                    onChange={() => togglePerson(hh.temp_id, p.temp_id)}
                                                                                />
                                                                            </TableCell>
                                                                            <TableCell>{p.name}</TableCell>
                                                                            <TableCell>
                                                                                <Chip
                                                                                    label={ROLE_LABELS[p.role] ?? p.role}
                                                                                    size="small"
                                                                                    color={p.role === 'member' ? 'primary' : 'default'}
                                                                                    variant={p.role === 'member' ? 'filled' : 'outlined'}
                                                                                />
                                                                            </TableCell>
                                                                            <TableCell>{formatDate(p.birth_date)}</TableCell>
                                                                            <TableCell>{p.gender ?? '—'}</TableCell>
                                                                            <TableCell>{p.member_number ?? '—'}</TableCell>
                                                                            <TableCell>{formatDate(p.member_since)}</TableCell>
                                                                            <TableCell>
                                                                                {p.source === 'vcard'
                                                                                    ? 'Kontakt'
                                                                                    : `Notiz von ${p.mentioned_by ?? '—'}`}
                                                                            </TableCell>
                                                                        </TableRow>
                                                                    ))}
                                                                </TableBody>
                                                            </Table>

                                                            {hh.existing_data_changes && (
                                                                <Box sx={{ mt: 2 }}>
                                                                    <Typography variant="subtitle2" gutterBottom>
                                                                        Änderungen am bestehenden Haushalt
                                                                    </Typography>
                                                                    <Table size="small">
                                                                        <TableHead>
                                                                            <TableRow>
                                                                                <TableCell>Feld</TableCell>
                                                                                <TableCell>Bisher</TableCell>
                                                                                <TableCell>Neu</TableCell>
                                                                            </TableRow>
                                                                        </TableHead>
                                                                        <TableBody>
                                                                            {hh.existing_data_changes.fields_to_overwrite.map((c, i) => (
                                                                                <TableRow key={`${c.field}-${i}`}>
                                                                                    <TableCell>{c.field}</TableCell>
                                                                                    <TableCell>{c.old_value ?? '—'}</TableCell>
                                                                                    <TableCell>{c.new_value ?? '—'}</TableCell>
                                                                                </TableRow>
                                                                            ))}
                                                                        </TableBody>
                                                                    </Table>
                                                                </Box>
                                                            )}
                                                        </Box>
                                                    </Collapse>
                                                </TableCell>
                                            </TableRow>,
                                        ];
                                    })}
                                    {visibleHouseholds.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={6} align="center">Keine Treffer</TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Box>
                )}

                {step === 2 && commitResult && (
                    <Box>
                        <Typography variant="h6" gutterBottom>Import abgeschlossen</Typography>
                        <Alert severity="success">
                            <strong>{commitResult.households_created}</strong> Haushalte neu angelegt,{' '}
                            <strong>{commitResult.households_updated}</strong> aktualisiert,{' '}
                            <strong>{commitResult.households_skipped}</strong> übersprungen.<br />
                            <strong>{commitResult.persons_created}</strong> Personen neu angelegt,{' '}
                            <strong>{commitResult.persons_updated}</strong> aktualisiert,{' '}
                            <strong>{commitResult.persons_assigned}</strong> einem Haushalt zugeordnet.
                        </Alert>
                        <Alert severity="info" sx={{ mt: 2 }}>
                            Das Scoring wurde nicht neu berechnet. Bitte im Actions-Tab
                            „Score berechnen" ausführen.
                        </Alert>
                    </Box>
                )}
            </DialogContent>
            <DialogActions>
                {step < 2 && <Button onClick={onClose}>Abbrechen</Button>}
                {step === 0 && (
                    <Button variant="contained" onClick={() => setStep(1)}>Weiter zur Zuordnung</Button>
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
                {step === 2 && <Button variant="contained" onClick={onComplete}>Schließen</Button>}
            </DialogActions>

            {matchingFor && (
                <MatchingDialog
                    open={!!matchingFor}
                    title={`Haushalt zuordnen: ${matchingFor.name}`}
                    description={
                        `Wohnung: ${matchingFor.apartment_unit || '—'}, `
                        + `Personen: ${matchingFor.persons.map((p) => p.name).join(', ')}`
                    }
                    candidates={matchingFor.match_result.fuzzy_candidates || []}
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
                                action: 'create',
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
        </Dialog>
    );
}

import { useState } from 'react';
import {
    Box, Typography, Paper, Button, Alert, CircularProgress,
} from '@mui/material';
import { analyzeHHBogen, analyzeIndividualBogen, analyzeVcf } from '../../api';
import {
    HHAnalysisResponse, IndividualAnalysisResponse, VcfAnalysisResponse,
} from '../../types';
import HHImportWizard from './HHImportWizard';
import IndividualImportWizard from './IndividualImportWizard';
import VcfImportWizard from './VcfImportWizard';

interface ImportTabProps {
    onImportComplete: () => void;
}

export default function ImportTab({ onImportComplete }: ImportTabProps) {
    const [hhAnalysis, setHHAnalysis] = useState<HHAnalysisResponse | null>(null);
    const [hhWizardOpen, setHHWizardOpen] = useState(false);
    const [hhLoading, setHHLoading] = useState(false);

    const [indAnalysis, setIndAnalysis] = useState<IndividualAnalysisResponse | null>(null);
    const [indWizardOpen, setIndWizardOpen] = useState(false);
    const [indLoading, setIndLoading] = useState(false);

    const [vcfAnalysis, setVcfAnalysis] = useState<VcfAnalysisResponse | null>(null);
    const [vcfWizardOpen, setVcfWizardOpen] = useState(false);
    const [vcfLoading, setVcfLoading] = useState(false);

    const [error, setError] = useState('');

    async function handleHHUpload(event: React.ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];
        if (!file) return;
        setHHLoading(true);
        setError('');
        try {
            const result = await analyzeHHBogen(file);
            setHHAnalysis(result);
            setHHWizardOpen(true);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Analyse fehlgeschlagen');
        } finally {
            setHHLoading(false);
            event.target.value = '';
        }
    }

    async function handleIndUpload(event: React.ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];
        if (!file) return;
        setIndLoading(true);
        setError('');
        try {
            const result = await analyzeIndividualBogen(file);
            setIndAnalysis(result);
            setIndWizardOpen(true);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Analyse fehlgeschlagen');
        } finally {
            setIndLoading(false);
            event.target.value = '';
        }
    }

    async function handleVcfUpload(event: React.ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];
        if (!file) return;
        setVcfLoading(true);
        setError('');
        try {
            const result = await analyzeVcf(file);
            setVcfAnalysis(result);
            setVcfWizardOpen(true);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Analyse fehlgeschlagen');
        } finally {
            setVcfLoading(false);
            event.target.value = '';
        }
    }

    return (
        <Box>
            <Typography variant="h5" gutterBottom>Datenimport</Typography>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <Alert severity="info" sx={{ mb: 3 }}>
                Im Regelbetrieb lesen wir zwei Fragebögen ein, in dieser Reihenfolge: erst den{' '}
                <strong>Haushaltsbogen</strong>, dann den <strong>Individualbogen</strong>. Der
                Haushaltsbogen legt bei Bedarf neue Haushalte mit ihren Personen an, der
                Individualbogen ergänzt die Angaben dieser Personen.
            </Alert>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>1. Haushaltsbogen importieren</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Ergänzt bestehende Haushalte um die Angaben aus dem Haushaltsbogen
                    (Excel .xlsx): WBS-Status, Wunsch, Haustiere und finanzielle
                    Rahmenbedingungen. Für Bögen ohne passenden Haushalt lässt sich im
                    Assistenten je Zeile ein neuer Haushalt mit Personen und
                    Wartepool-Bewerbung anlegen. Erkennt automatisch das alte (LimeSurvey) und
                    das neue (Nextcloud Forms) Format.
                </Typography>
                <Button variant="contained" component="label" disabled={hhLoading}>
                    {hhLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    Haushaltsbogen hochladen
                    <input type="file" hidden onChange={handleHHUpload} accept=".xlsx" />
                </Button>
            </Paper>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>2. Individualbogen importieren</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Ergänzt bei vorhandenen Personen Geschlecht, Haupttätigkeit,
                    Bildungsabschluss, kulturelle Vielfalt und besondere Lebenslagen und trägt
                    fehlende Angaben wie „Mitglied seit“ nach. Neue Personen werden nicht
                    angelegt; wer noch keinen Haushaltsbogen hat, erscheint beim nächsten
                    Einlesen wieder.
                </Typography>
                <Button variant="contained" component="label" disabled={indLoading}>
                    {indLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    Individualbogen hochladen
                    <input type="file" hidden onChange={handleIndUpload} accept=".xlsx" />
                </Button>
            </Paper>

            <Typography variant="overline" color="text.secondary" display="block" sx={{ mt: 4, mb: 1 }}>
                Nebenfunktion
            </Typography>
            <Paper variant="outlined" sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>Mitgliederliste – fehlende Angaben ergänzen</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Liest die Mitgliederliste (vCard, .vcf) und trägt bei vorhandenen Personen
                    nach, was noch fehlt: Geburtsdatum, Mitglied seit, Mitgliedsnummer und
                    Geschlecht. Sie überschreibt nichts, legt niemanden an und ändert keine
                    Haushalte. Du kannst sie jederzeit einlesen, unabhängig von den Fragebögen.
                </Typography>
                <Button variant="outlined" component="label" disabled={vcfLoading}>
                    {vcfLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    Mitgliederliste hochladen
                    <input type="file" hidden onChange={handleVcfUpload} accept=".vcf,.vcard" />
                </Button>
            </Paper>

            {hhWizardOpen && hhAnalysis && (
                <HHImportWizard
                    open={hhWizardOpen}
                    analysis={hhAnalysis}
                    onClose={() => setHHWizardOpen(false)}
                    onComplete={() => { setHHWizardOpen(false); onImportComplete(); }}
                />
            )}

            {indWizardOpen && indAnalysis && (
                <IndividualImportWizard
                    open={indWizardOpen}
                    analysis={indAnalysis}
                    onClose={() => setIndWizardOpen(false)}
                    onComplete={() => { setIndWizardOpen(false); onImportComplete(); }}
                />
            )}
            {vcfWizardOpen && vcfAnalysis && (
                <VcfImportWizard
                    open={vcfWizardOpen}
                    analysis={vcfAnalysis}
                    onClose={() => setVcfWizardOpen(false)}
                    onComplete={() => { setVcfWizardOpen(false); onImportComplete(); }}
                />
            )}
        </Box>
    );
}

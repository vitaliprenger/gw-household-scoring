import { useState } from 'react';
import {
    Box, Typography, Paper, Button, Alert, CircularProgress,
} from '@mui/material';
import { analyzeHHBogen, analyzeIndividualBogen } from '../../api';
import { HHAnalysisResponse, IndividualAnalysisResponse } from '../../types';
import HHImportWizard from './HHImportWizard';
import IndividualImportWizard from './IndividualImportWizard';

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

    return (
        <Box>
            <Typography variant="h5" gutterBottom>Datenimport</Typography>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>1. Haushaltsbogen importieren</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Importiert Haushaltsdaten aus dem Haushaltsbogen-Fragebogen (Excel .xlsx).
                    Erkennt automatisch das alte (LimeSurvey) und neue (Nextcloud Forms) Format.
                </Typography>
                <Button variant="contained" component="label" disabled={hhLoading}>
                    {hhLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    HH-Fragebogen hochladen
                    <input type="file" hidden onChange={handleHHUpload} accept=".xlsx" />
                </Button>
            </Paper>

            <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>2. Individualbogen importieren</Typography>
                <Alert severity="info" sx={{ mb: 2 }}>
                    Bitte importieren Sie zuerst den Haushaltsbogen, damit die Zuordnung
                    der Einzelpersonen zu Haushalten möglich ist.
                </Alert>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Importiert individuelle Personeninformationen (Geschlecht, Beruf, Bildung etc.)
                    und ordnet sie den bestehenden Haushalten zu.
                </Typography>
                <Button variant="contained" component="label" disabled={indLoading}>
                    {indLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    Individual-Fragebogen hochladen
                    <input type="file" hidden onChange={handleIndUpload} accept=".xlsx" />
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
        </Box>
    );
}

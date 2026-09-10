import { useState } from 'react';
import {
    Box, Typography, Paper, Button, Alert, CircularProgress,
} from '@mui/material';
import { analyzeHHBogen, analyzeIndividualBogen, analyzeVcf } from '../../api';
import { HHAnalysisResponse, IndividualAnalysisResponse, VcfAnalysisResponse } from '../../types';
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
                Die Reihenfolge ist verbindlich: Die <strong>Mitgliederliste (vCard)</strong> legt
                Personen und — bei erkannter Wohnungszuordnung — Haushalte an. Die beiden
                Fragebögen <strong>ergänzen anschließend nur noch</strong> vorhandene Personen
                bzw. Haushalte; sie legen selbst nichts Neues an.
            </Alert>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>1. Mitgliederliste (vCard) importieren</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Grundlage für alle weiteren Importe. Legt aus dem Adressbuch-Export (.vcf) alle
                    enthaltenen Personen an — inklusive der im Notizfeld genannten Partner*innen und
                    Kinder (Name + Geburtsdatum) — und übernimmt Mitgliedsnummer, Geburtsdatum,
                    Geschlecht sowie das Datum des Aufnahmegesprächs als Beginn der Mitgliedschaft.
                    Vorhandene Personen werden mit den vCard-Daten überschrieben; leere Felder
                    überschreiben nichts. Ein Haushalt entsteht nur bei erkannter Wohnungsnummer:
                    alle Personen derselben Wohnung bilden einen Haushalt und gelten als aktuelle
                    Bewohner. Alle übrigen Personen bleiben ohne Haushalt.
                </Typography>
                <Button variant="contained" component="label" disabled={vcfLoading}>
                    {vcfLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    vCard-Datei hochladen
                    <input type="file" hidden onChange={handleVcfUpload} accept=".vcf,.vcard" />
                </Button>
            </Paper>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>2. Individualbogen importieren</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Ergänzt individuelle Personeninformationen (Geschlecht, Beruf, Bildung etc.)
                    bei Personen, die vorhanden sind und zugeordnet werden können — auch bei
                    Personen ohne Haushalt. Neue Personen werden nicht angelegt.
                </Typography>
                <Button variant="contained" component="label" disabled={indLoading}>
                    {indLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    Individual-Fragebogen hochladen
                    <input type="file" hidden onChange={handleIndUpload} accept=".xlsx" />
                </Button>
            </Paper>

            <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>3. Haushaltsbogen importieren</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Ergänzt bestehende Haushalte um die Angaben aus dem Haushaltsbogen-Fragebogen
                    (Excel .xlsx): WBS-Status, Wohnungswunsch, Haustiere und finanzielle
                    Rahmenbedingungen. Erkennt automatisch das alte (LimeSurvey) und neue
                    (Nextcloud Forms) Format. Neue Haushalte werden nicht angelegt.
                </Typography>
                <Button variant="contained" component="label" disabled={hhLoading}>
                    {hhLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                    HH-Fragebogen hochladen
                    <input type="file" hidden onChange={handleHHUpload} accept=".xlsx" />
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

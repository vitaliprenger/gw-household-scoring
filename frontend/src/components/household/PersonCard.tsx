import {
    Card, CardContent, Typography, Grid, TextField, Chip, Box,
    FormControl, InputLabel, Select, MenuItem, IconButton, Tooltip,
} from '@mui/material';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import { Person } from '../../types';

interface PersonCardProps {
    person: Person;
    editing: boolean;
    onChange: (id: number, field: string, value: string | boolean) => void;
    onRemove?: (person: Person) => void;
}

const FIELD_LABELS: Record<string, string> = {
    first_name: 'Vorname',
    last_name: 'Nachname',
    birth_date: 'Geburtsdatum',
    gender: 'Geschlecht',
    occupation_type: 'Beruf',
    education_level: 'Bildungsabschluss',
    cultural_background: 'Kultureller Hintergrund',
    special_needs: 'Besondere Lebenslage',
    member_number: 'Mitgliedsnummer',
    member_since: 'Mitglied seit',
};

const OCCUPATION_OPTIONS: { value: string; label: string }[] = [
    { value: '', label: '—' },
    { value: '1', label: 'Organisation, Verwaltung, Recht, Buchhaltung' },
    { value: '2', label: 'Pädagogik, Psychologie, Soziales, Gesundheit, Lehre' },
    { value: '3', label: 'Geistes-, Gesellschafts-, Wirtschaftswissenschaft' },
    { value: '4', label: 'Handwerk' },
    { value: '5', label: 'Dienstleistung' },
    { value: '6', label: 'Kunst und Kultur, Unterhaltung, Medien' },
    { value: '7', label: 'Landwirtschaft, Gartenbau, Tier-, Forstwirtschaft' },
    { value: '8', label: 'Architektur, Bauplanung' },
    { value: '9', label: 'Naturwissenschaft, Geographie, Informatik, Technik' },
    { value: '10', label: 'Verkehr, Logistik, Schutz, Sicherheit' },
    { value: '11', label: 'Schüler*in, (noch) keine Zuordnung möglich' },
    { value: '0', label: 'Keine Antwort' },
];

const OCCUPATION_LABEL_MAP: Record<string, string> = Object.fromEntries(
    OCCUPATION_OPTIONS.filter(o => o.value).map(o => [o.value, o.label])
);

const EDUCATION_OPTIONS: { value: string; label: string }[] = [
    { value: '', label: '—' },
    { value: '1', label: 'Berufsausbildungsvorbereitung' },
    { value: '2', label: 'Hauptschulabschluss' },
    { value: '3', label: 'Zweij. Berufsausbildung, Mittlerer Schulabschluss' },
    { value: '4', label: 'Dreij. Berufsausbildung, Hochschulreife (inkl. Fachabitur)' },
    { value: '5', label: 'Erste berufliche Fortbildungsqualifikation' },
    { value: '6', label: 'Bachelor, FH-Diplom, Meister, Fachschule u.a.' },
    { value: '7', label: 'Master, Uni-Diplom, Magister u.a.' },
    { value: '8', label: 'Promotion' },
    { value: '0', label: 'Keine Antwort' },
];

const EDUCATION_LABEL_MAP: Record<string, string> = Object.fromEntries(
    EDUCATION_OPTIONS.filter(o => o.value).map(o => [o.value, o.label])
);

function formatDate(val?: string): string {
    if (!val) return '—';
    try {
        return new Date(val).toLocaleDateString('de-DE');
    } catch {
        return val;
    }
}

function formatDateTime(val?: string): string {
    if (!val) return '—';
    try {
        const d = new Date(val);
        return d.toLocaleDateString('de-DE') + ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    } catch {
        return val;
    }
}

export default function PersonCard({ person, editing, onChange, onRemove }: PersonCardProps) {
    const displayFields: { key: keyof Person; label: string }[] = [
        { key: 'member_number', label: FIELD_LABELS.member_number },
        { key: 'member_since', label: FIELD_LABELS.member_since },
        { key: 'birth_date', label: FIELD_LABELS.birth_date },
        { key: 'gender', label: FIELD_LABELS.gender },
        { key: 'occupation_type', label: FIELD_LABELS.occupation_type },
        { key: 'education_level', label: FIELD_LABELS.education_level },
        { key: 'cultural_background', label: FIELD_LABELS.cultural_background },
        { key: 'special_needs', label: FIELD_LABELS.special_needs },
    ];

    return (
        <Card variant="outlined" sx={{ mb: 1 }}>
            <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="subtitle1" fontWeight="bold">
                        {person.first_name} {person.last_name}
                    </Typography>
                    {person.special_needs && (
                        <Chip label="Bes. Lebenslage" size="small" color="info" />
                    )}
                    {onRemove && (
                        <Tooltip title="Aus Haushalt entfernen">
                            <IconButton size="small" sx={{ ml: 'auto' }} onClick={() => onRemove(person)}>
                                <LinkOffIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    )}
                </Box>
                <Grid container spacing={1}>
                    {displayFields.map(({ key, label }) => (
                        <Grid size={{ xs: 6, sm: 4 }} key={key}>
                            {editing && (key === 'education_level' || key === 'occupation_type') ? (
                                <FormControl size="small" fullWidth>
                                    <InputLabel>{label}</InputLabel>
                                    <Select
                                        value={(person[key] as string) ?? ''}
                                        label={label}
                                        onChange={(e) => onChange(person.id, key, e.target.value)}
                                    >
                                        {(key === 'occupation_type' ? OCCUPATION_OPTIONS : EDUCATION_OPTIONS).map((o) => (
                                            <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            ) : editing ? (
                                <TextField
                                    label={label}
                                    size="small"
                                    fullWidth
                                    value={(person[key] as string) ?? ''}
                                    onChange={(e) => onChange(person.id, key, e.target.value)}
                                />
                            ) : (
                                <>
                                    <Typography variant="caption" color="text.secondary">
                                        {label}
                                    </Typography>
                                    <Typography variant="body2">
                                        {key === 'birth_date' || key === 'member_since'
                                            ? formatDate(person[key] as string)
                                            : key === 'education_level'
                                            ? EDUCATION_LABEL_MAP[(person[key] as string)] || (person[key] as string) || '—'
                                            : key === 'occupation_type'
                                            ? OCCUPATION_LABEL_MAP[(person[key] as string)] || (person[key] as string) || '—'
                                            : (person[key] as string) || '—'}
                                    </Typography>
                                </>
                            )}
                        </Grid>
                    ))}
                </Grid>
                {(person.individual_import_timestamp || person.updated_at) && (
                    <Box sx={{ display: 'flex', gap: 3, mt: 1.5, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                        {person.individual_import_timestamp && (
                            <Box>
                                <Typography variant="caption" color="text.secondary">Letzter Import</Typography>
                                <Typography variant="body2">{formatDateTime(person.individual_import_timestamp)}</Typography>
                            </Box>
                        )}
                        {person.updated_at && (
                            <Box>
                                <Typography variant="caption" color="text.secondary">Letzte Bearbeitung</Typography>
                                <Typography variant="body2">{formatDateTime(person.updated_at)}</Typography>
                            </Box>
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
}

import { Box, Chip, Tooltip, Typography } from '@mui/material';
import { ImportPersonPreview, SimilarPerson } from '../../types';

const SIMILAR_REASON: Record<SimilarPerson['reason'], string> = {
    member_number: 'trägt die Mitgliedsnummer',
    same_name: 'gleicher Name',
    birth_date: 'gleiches Geburtsdatum',
};

/** „Agathe Kern (Haushalt Kern): trägt die Mitgliedsnummer“ */
export function similarPersonText(similar: SimilarPerson): string {
    const household = similar.household ? ` (Haushalt ${similar.household})` : ' (ohne Haushalt)';
    return `${similar.name}${household}: ${SIMILAR_REASON[similar.reason]}`;
}

function StatusChip({ person }: { person: ImportPersonPreview }) {
    switch (person.status) {
        case 'in_household':
            return <Chip label="im Haushalt" size="small" variant="outlined" />;
        case 'assign':
            return (
                <Tooltip title="Steht ohne Haushalt im Datenbestand und wird dem Haushalt zugeordnet.">
                    <Chip label="wird zugeordnet" size="small" color="info" variant="outlined" />
                </Tooltip>
            );
        case 'other_household':
            return (
                <Tooltip title="Wird nicht übernommen – bitte von Hand umziehen.">
                    <Chip
                        label={`bleibt in „${person.other_household ?? '?'}“`}
                        size="small" color="warning" variant="outlined"
                    />
                </Tooltip>
            );
        default:
            return <Chip label="neu" size="small" color="success" variant="outlined" />;
    }
}

interface BogenPersonsProps {
    persons: ImportPersonPreview[];
    /**
     * Die Kennzeichnungen gelten für den vorgeschlagenen Haushalt. Nach der
     * Zuordnung zu einem anderen zählt die Zusammenfassung.
     */
    showOutcome: boolean;
}

/** Personen eines Haushaltsbogens mit dem, was beim Übernehmen mit ihnen geschieht. */
export default function BogenPersons({ persons, showOutcome }: BogenPersonsProps) {
    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            {persons.map((person, index) => (
                <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                    <Typography variant="body2">
                        {person.first_name || '—'}
                        <Typography component="span" variant="body2" color="text.secondary"> | </Typography>
                        {person.last_name || '—'}
                    </Typography>
                    {person.member_number && (
                        <Typography variant="caption" color="text.secondary">
                            Nr. {person.member_number}
                        </Typography>
                    )}
                    {showOutcome && <StatusChip person={person} />}
                    {showOutcome && person.similar.length > 0 && (
                        <Tooltip title={
                            <>
                                Ähnliche Person im Datenbestand:
                                {person.similar.map((s, i) => <div key={i}>{similarPersonText(s)}</div>)}
                            </>
                        }>
                            <Chip label="ähnliche Person im Datenbestand" size="small" color="warning" />
                        </Tooltip>
                    )}
                    {showOutcome && person.member_number_holder && (
                        <Tooltip title={`Diese Mitgliedsnummer trägt schon ${person.member_number_holder}. Sie wird hier nicht gespeichert.`}>
                            <Chip label="Nummer vergeben" size="small" color="warning" variant="outlined" />
                        </Tooltip>
                    )}
                </Box>
            ))}
        </Box>
    );
}

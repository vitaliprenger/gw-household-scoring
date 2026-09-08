import React, { useState, useEffect } from 'react';
import {
  AppBar, Toolbar, Typography, Container, Box, Tabs, Tab,
  Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Button, TextField, Grid, Card, CardContent, Alert, Snackbar, Chip,
  FormControl, InputLabel, Select, MenuItem, FormControlLabel, Switch
} from '@mui/material';
import { getHouseholds, getScoringConfig, updateScoringConfig, calculateScores, uploadHouseholds, login, getRanking } from './api';
import { Household, ScoringConfig, RankingGroup } from './types';
import HouseholdDetailDialog from './components/household/HouseholdDetailDialog';
import ImportTab from './components/import/ImportTab';
import PersonsTab from './components/persons/PersonsTab';

const CONFIG_LABELS: Record<string, string> = {
  weight_diversity_age:            'Altersstruktur',
  weight_diversity_gender:         'Geschlechterverhältnis',
  weight_diversity_cultural:       'Kulturelle Vielfalt',
  weight_diversity_occupation:     'Berufliche Tätigkeiten',
  weight_diversity_education:      'Bildungsabschlüsse',
  weight_diversity_special_needs:  'Besondere Lebenslagen',
  weight_membership:               'Mitgliedsdauer',
  weight_engagement:               'Engagement',
  weight_occupancy:                'Wohnraumausnutzung',
  target_occupation_1:             '1 – Organisation, Verwaltung, Recht',
  target_occupation_2:             '2 – Pädagogik, Psychologie, Soziales',
  target_occupation_3:             '3 – Geistes-/Gesellschafts-/Wirtschaftswiss.',
  target_occupation_4:             '4 – Handwerk',
  target_occupation_5:             '5 – Dienstleistung',
  target_occupation_6:             '6 – Kunst und Kultur, Unterhaltung',
  target_occupation_7:             '7 – Landwirtschaft, Gartenbau, Tierpflege',
  target_occupation_8:             '8 – Architektur, Bauplanung',
  target_occupation_9:             '9 – Naturwissenschaft, Geographie',
  target_occupation_10:            '10 – Verkehr, Logistik, Schutz, Sicherheit',
  target_education_1:              '1 – Berufsausbildungsvorbereitung',
  target_education_2:              '2 – Hauptschulabschluss',
  target_education_3:              '3 – Zweij. Berufsausbildung, Mittlerer Schulabschluss',
  target_education_4:              '4 – Dreij. Berufsausbildung, Hochschulreife',
  target_education_5:              '5 – Erste berufl. Fortbildungsqualifikation',
  target_education_6:              '6 – Bachelor, FH-Diplom, Meister u.a.',
  target_education_7:              '7 – Master, Uni-Diplom, Magister u.a.',
  target_education_8:              '8 – Promotion',
  target_age_20_29:                '20 bis 29',
  target_age_30_39:                '30 bis 39',
  target_age_40_49:                '40 bis 49',
  target_age_50_59:                '50 bis 59',
  target_age_60_69:                '60 bis 69',
  target_age_70_79:                '70 bis 79',
  target_age_80_89:                '80 bis 89',
  target_age_over_89:              'über 89',
  target_gender_f:                 'Geschlecht: weiblich',
  target_gender_m:                 'Geschlecht: männlich',
  target_gender_d:                 'Geschlecht: divers',
};

function App() {
  const [tabValue, setTabValue] = useState(0);
  const [households, setHouseholds] = useState<Household[]>([]);
  const [configs, setConfigs] = useState<ScoringConfig[]>([]);
  const [rankingGroups, setRankingGroups] = useState<RankingGroup[]>([]);
  const [selectedSize, setSelectedSize] = useState<string>('');
  const [selectedFunding, setSelectedFunding] = useState<string>('');
  const [message, setMessage] = useState<{text: string, type: 'success'|'error'} | null>(null);

  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  const [password, setPassword] = useState("");

  const [detailHouseholdId, setDetailHouseholdId] = useState<number | null>(null);
  const [showArchivedHH, setShowArchivedHH] = useState(false);

  useEffect(() => {
    if (isLoggedIn) {
      loadData();
    }
  }, [isLoggedIn, showArchivedHH]);

  const loadData = async () => {
    try {
      const hh = await getHouseholds(showArchivedHH);
      setHouseholds(hh.sort((a, b) => b.total_score - a.total_score));

      try {
        const groups = await getRanking();
        setRankingGroups(groups);
        if (groups.length > 0 && !selectedSize && !selectedFunding) {
          setSelectedSize(String(groups[0].size_rooms));
          setSelectedFunding(groups[0].funding_type);
        }
      } catch (e) {
        console.log("Could not load ranking");
      }

      try {
        const conf = await getScoringConfig();
        setConfigs(conf);
      } catch (e) {
        console.log("Could not load config");
      }
    } catch (error) {
      console.error("Failed to load data", error);
      localStorage.removeItem('token');
      setIsLoggedIn(false);
    }
  };

  const handleLogin = async () => {
    try {
      const data = await login(password);
      localStorage.setItem('token', data.access_token);
      setIsLoggedIn(true);
      setPassword("");
      setMessage({ text: "Erfolgreich angemeldet!", type: 'success' });
    } catch (error) {
      setMessage({ text: "Falsches Passwort.", type: 'error' });
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
    setTabValue(0);
    setHouseholds([]);
    setConfigs([]);
    setMessage({ text: "Abgemeldet.", type: 'success' });
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleCalculate = async () => {
    try {
      await calculateScores();
      setMessage({ text: "Scores erfolgreich neu berechnet!", type: 'success' });
      loadData();
    } catch (error) {
      setMessage({ text: "Berechnung fehlgeschlagen.", type: 'error' });
    }
  };

  const handleConfigChange = (key: string, value: string) => {
    setConfigs(configs.map(c => c.key === key ? { ...c, value: parseFloat(value) || 0 } : c));
  };

  const handleSaveConfig = async () => {
    try {
      await updateScoringConfig(configs);
      setMessage({ text: "Konfiguration gespeichert!", type: 'success' });
    } catch (error) {
      setMessage({ text: "Speichern fehlgeschlagen.", type: 'error' });
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      try {
        await uploadHouseholds(event.target.files[0]);
        setMessage({ text: "Datei erfolgreich hochgeladen!", type: 'success' });
        loadData();
      } catch (error) {
        setMessage({ text: "Upload fehlgeschlagen.", type: 'error' });
      }
    }
  };

  const formatDateTime = (val?: string): string => {
    if (!val) return '—';
    try {
      const d = new Date(val);
      return d.toLocaleDateString('de-DE') + ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return val;
    }
  };

  if (!isLoggedIn) {
    return (
      <Box sx={{ flexGrow: 1 }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              GW Household Scoring
            </Typography>
          </Toolbar>
        </AppBar>
        <Container maxWidth="xs" sx={{ mt: 8 }}>
          <Paper sx={{ p: 4 }}>
            <Typography variant="h5" gutterBottom align="center">
              Anmeldung
            </Typography>
            <TextField
              autoFocus
              fullWidth
              margin="normal"
              label="Passwort"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            />
            <Button
              fullWidth
              variant="contained"
              sx={{ mt: 2 }}
              onClick={handleLogin}
            >
              Anmelden
            </Button>
          </Paper>
        </Container>
        <Snackbar open={!!message} autoHideDuration={6000} onClose={() => setMessage(null)}>
          <Alert onClose={() => setMessage(null)} severity={message?.type} sx={{ width: '100%' }}>
            {message?.text}
          </Alert>
        </Snackbar>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            GW Household Scoring
          </Typography>
          <Button color="inherit" onClick={handleLogout}>Abmelden</Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Rangliste" />
            <Tab label="Alle Haushalte" />
            <Tab label="Personen" />
            <Tab label="Bewertungskonfiguration" />
            <Tab label="Datenimport" />
            <Tab label="Aktionen" />
          </Tabs>
        </Box>

        {tabValue === 0 && (() => {
          const sizes = [...new Set(rankingGroups.map(g => g.size_rooms))].sort((a, b) => a - b);
          const fundingTypes = [...new Set(rankingGroups.map(g => g.funding_type))].sort();
          const activeGroup = rankingGroups.find(
            g => String(g.size_rooms) === selectedSize && g.funding_type === selectedFunding
          );

          return (
            <Box>
              <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                <FormControl sx={{ minWidth: 200 }}>
                  <InputLabel>Wohnungsgröße</InputLabel>
                  <Select
                    value={selectedSize}
                    label="Wohnungsgröße"
                    onChange={(e) => setSelectedSize(e.target.value)}
                  >
                    {sizes.map(s => (
                      <MenuItem key={s} value={String(s)}>{s} Zimmer</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl sx={{ minWidth: 200 }}>
                  <InputLabel>Wohnungsart</InputLabel>
                  <Select
                    value={selectedFunding}
                    label="Wohnungsart"
                    onChange={(e) => setSelectedFunding(e.target.value)}
                  >
                    {fundingTypes.map(f => (
                      <MenuItem key={f} value={f}>{f}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>

              {activeGroup ? (
                <TableContainer component={Paper}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Rang</TableCell>
                        <TableCell>Haushaltsname</TableCell>
                        <TableCell>Mitglieder</TableCell>
                        <TableCell align="right">Engagement</TableCell>
                        <TableCell align="right">Gesamtpunktzahl</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {activeGroup.households.map((row) => (
                        <TableRow key={row.id}>
                          <TableCell>{row.rank}</TableCell>
                          <TableCell>{row.name}</TableCell>
                          <TableCell>{row.member_count}</TableCell>
                          <TableCell align="right">{row.engagement_score}</TableCell>
                          <TableCell align="right"><strong>{row.total_score.toFixed(2)}</strong></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Paper sx={{ p: 3, textAlign: 'center' }}>
                  <Typography color="textSecondary">
                    {rankingGroups.length === 0
                      ? 'Keine Bewerbungen vorhanden. Bitte erst Wohnungen anlegen und Haushalte zuordnen.'
                      : 'Keine Ergebnisse für diese Kombination.'}
                  </Typography>
                </Paper>
              )}
            </Box>
          );
        })()}

        {tabValue === 1 && (
          <Box>
          <Box sx={{ display: 'flex', mb: 2, alignItems: 'center' }}>
            <FormControlLabel
              control={
                <Switch
                  checked={showArchivedHH}
                  onChange={(_, checked) => setShowArchivedHH(checked)}
                />
              }
              label="Archivierte anzeigen"
            />
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Haushaltsname</TableCell>
                  <TableCell align="right">Mitglieder</TableCell>
                  <TableCell>WBS</TableCell>
                  <TableCell>Mitglied seit</TableCell>
                  <TableCell align="right">Engagement</TableCell>
                  <TableCell>Bewohner</TableCell>
                  <TableCell>Letzter Import</TableCell>
                  <TableCell>Letzte Bearbeitung</TableCell>
                  <TableCell align="right">Gesamtpunktzahl</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {households.map((hh) => (
                  <TableRow
                    key={hh.id}
                    hover
                    sx={{ cursor: 'pointer', opacity: hh.archived ? 0.5 : 1 }}
                    onClick={() => setDetailHouseholdId(hh.id)}
                  >
                    <TableCell>
                      {hh.name}
                      {hh.archived && <Chip label="Archiviert" size="small" sx={{ ml: 1 }} color="default" />}
                    </TableCell>
                    <TableCell align="right">{hh.people.length}</TableCell>
                    <TableCell>
                      {hh.wbs_status ? <Chip label={hh.wbs_status} size="small" /> : '–'}
                    </TableCell>
                    <TableCell>{(() => {
                      const dates = hh.people.map(p => p.member_since).filter(Boolean) as string[];
                      if (dates.length === 0) return '–';
                      const earliest = dates.reduce((a, b) => a < b ? a : b);
                      return new Date(earliest).toLocaleDateString('de-DE');
                    })()}</TableCell>
                    <TableCell align="right">{hh.engagement_score}</TableCell>
                    <TableCell>{hh.is_resident ? 'Ja' : 'Nein'}</TableCell>
                    <TableCell>{formatDateTime(hh.import_timestamp)}</TableCell>
                    <TableCell>{formatDateTime(hh.updated_at)}</TableCell>
                    <TableCell align="right"><strong>{hh.total_score.toFixed(2)}</strong></TableCell>
                  </TableRow>
                ))}
                {households.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} align="center">Keine Haushalte vorhanden.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
          </Box>
        )}

        {tabValue === 2 && (
          <PersonsTab onShowHousehold={(id) => setDetailHouseholdId(id)} />
        )}

        {tabValue === 3 && (() => {
          const diversityWeights = configs.filter(c => c.key.startsWith('weight_diversity_'));
          const otherWeights = configs.filter(c => c.key.startsWith('weight_') && !c.key.startsWith('weight_diversity_'));
          const naturalSort = (a: ScoringConfig, b: ScoringConfig) =>
            a.key.localeCompare(b.key, undefined, { numeric: true });
          const targetAge = configs.filter(c => c.key.startsWith('target_age_')).sort(naturalSort);
          const targetGender = configs.filter(c => c.key.startsWith('target_gender_')).sort(naturalSort);
          const targetOccupation = configs.filter(c => c.key.startsWith('target_occupation_')).sort(naturalSort);
          const targetEducation = configs.filter(c => c.key.startsWith('target_education_')).sort(naturalSort);
          const targetOther = configs.filter(c =>
            c.key.startsWith('target_') &&
            !c.key.startsWith('target_age_') &&
            !c.key.startsWith('target_gender_') &&
            !c.key.startsWith('target_occupation_') &&
            !c.key.startsWith('target_education_')
          );
          const bonuses = configs.filter(c => !c.key.startsWith('weight_') && !c.key.startsWith('target_'));

          const renderConfigGroup = (title: string, items: ScoringConfig[]) => (
            <Box sx={{ mb: 4 }}>
              <Typography variant="h6" sx={{ mb: 2 }}>{title}</Typography>
              <Grid container spacing={2}>
                {items.map((conf) => (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }} key={conf.key}>
                    <Card>
                      <CardContent>
                        <Typography color="textSecondary" gutterBottom>
                          {CONFIG_LABELS[conf.key] || conf.description || conf.key}
                        </Typography>
                        <TextField
                          fullWidth
                          type="number"
                          value={conf.value}
                          onChange={(e) => handleConfigChange(conf.key, e.target.value)}
                        />
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Box>
          );

          return (
            <Box>
              <Typography variant="h5" sx={{ mb: 2 }}>Gewichte</Typography>
              {renderConfigGroup('Durchmischung', diversityWeights)}
              {renderConfigGroup('Weitere Gewichte', otherWeights)}
              <Typography variant="h5" sx={{ mb: 2, mt: 4 }}>Zielwerte</Typography>
              {targetAge.length > 0 && renderConfigGroup('Altersgruppen', targetAge)}
              {targetGender.length > 0 && renderConfigGroup('Geschlecht', targetGender)}
              {targetOccupation.length > 0 && renderConfigGroup('Haupttätigkeit', targetOccupation)}
              {targetEducation.length > 0 && renderConfigGroup('Bildungsabschlüsse', targetEducation)}
              {targetOther.length > 0 && renderConfigGroup('Sonstige Zielwerte', targetOther)}
              {bonuses.length > 0 && renderConfigGroup('Bonuspunkte', bonuses)}
              <Button variant="contained" color="primary" onClick={handleSaveConfig}>
                Konfiguration speichern
              </Button>
            </Box>
          );
        })()}

        {tabValue === 4 && (
          <ImportTab onImportComplete={loadData} />
        )}

        {tabValue === 5 && (
          <Box>
            <Grid container spacing={2}>
              <Grid>
                <Button variant="contained" color="secondary" onClick={handleCalculate}>
                  Punkte neu berechnen
                </Button>
              </Grid>
              <Grid>
                <Button variant="contained" component="label">
                  Excel-Daten hochladen (alt)
                  <input type="file" hidden onChange={handleFileUpload} accept=".xlsx" />
                </Button>
              </Grid>
            </Grid>
          </Box>
        )}
      </Container>

      <HouseholdDetailDialog
        open={detailHouseholdId !== null}
        householdId={detailHouseholdId}
        onClose={() => setDetailHouseholdId(null)}
        onSaved={loadData}
      />

      <Snackbar open={!!message} autoHideDuration={6000} onClose={() => setMessage(null)}>
        <Alert onClose={() => setMessage(null)} severity={message?.type} sx={{ width: '100%' }}>
          {message?.text}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default App;

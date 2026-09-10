import React, { useState, useEffect } from 'react';
import {
  AppBar, Toolbar, Typography, Container, Box, Tabs, Tab,
  Paper, Button, TextField, Grid, Card, CardContent, Alert, Snackbar, Chip,
  FormControl, InputLabel, Select, MenuItem, FormControlLabel, Switch, InputAdornment
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { deDE } from '@mui/x-data-grid/locales';
import { getHouseholds, getScoringConfig, updateScoringConfig, calculateScores, uploadHouseholds, login, getRanking } from './api';
import { Household, ScoringConfig, RankingGroup, RankedHousehold } from './types';
import HouseholdDetailDialog from './components/household/HouseholdDetailDialog';
import ImportTab from './components/import/ImportTab';
import PersonsTab from './components/persons/PersonsTab';
import ApartmentsTab from './components/apartments/ApartmentsTab';
import CreateHouseholdDialog from './components/household/CreateHouseholdDialog';

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

const SIZE_NONE = '__none__';
/** Filterwert "Alle": der Filter schränkt die Rangliste nicht ein. */
const FILTER_ALL = '__all__';

const sizeKey = (value: number | null): string =>
  value === null || value === undefined ? SIZE_NONE : String(value);

const sizeLabel = (value: number | null): string =>
  value === null || value === undefined ? 'ohne Zimmerangabe' : `${value} Zimmer`;

function App() {
  const [tabValue, setTabValue] = useState(0);
  const [households, setHouseholds] = useState<Household[]>([]);
  const [configs, setConfigs] = useState<ScoringConfig[]>([]);
  const [rankingGroups, setRankingGroups] = useState<RankingGroup[]>([]);
  const [selectedSize, setSelectedSize] = useState<string>(FILTER_ALL);
  const [selectedFunding, setSelectedFunding] = useState<string>(FILTER_ALL);
  const [message, setMessage] = useState<{text: string, type: 'success'|'error'} | null>(null);

  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  const [password, setPassword] = useState("");

  const [detailHouseholdId, setDetailHouseholdId] = useState<number | null>(null);
  const [showArchivedHH, setShowArchivedHH] = useState(false);
  const [filterNoApartment, setFilterNoApartment] = useState(false);
  const [createHHOpen, setCreateHHOpen] = useState(false);
  const [householdSearch, setHouseholdSearch] = useState('');

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
              GW Haushalts-Scoring
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
            GW Haushalts-Scoring
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
            <Tab label="Wohnungen" />
            <Tab label="Bewertungskonfiguration" />
            <Tab label="Datenimport" />
            <Tab label="Aktionen" />
          </Tabs>
        </Box>

        {tabValue === 0 && (() => {
          const sizes = [...new Set(rankingGroups.map(g => g.size_rooms))]
            .sort((a, b) => (a ?? Infinity) - (b ?? Infinity));
          const fundingTypes = [...new Set(rankingGroups.map(g => g.funding_type))].sort();

          // Ein Filter auf "Alle" schränkt nicht ein. Stehen beide Filter auf
          // "Alle", zeigt die Rangliste jeden nicht archivierten Haushalt --
          // auch solche, die für keine Wohnungskategorie in Frage kommen.
          const unfiltered = selectedSize === FILTER_ALL && selectedFunding === FILTER_ALL;
          const matchingGroups = rankingGroups.filter(
            g => (selectedSize === FILTER_ALL || sizeKey(g.size_rooms) === selectedSize)
              && (selectedFunding === FILTER_ALL || g.funding_type === selectedFunding)
          );
          // Ein Haushalt kommt für mehrere Kategorien in Frage: über die id
          // entdoppeln und den Rang für die aktuelle Auswahl neu vergeben.
          // Die Wohnraumausnutzung haengt an der Zimmerzahl: derselbe Haushalt hat
          // je Kategorie einen anderen Gesamtscore. Beim Entdoppeln zaehlt deshalb
          // die Kategorie, in der er am besten abschneidet.
          const selectedRanked: RankedHousehold[] = unfiltered
            ? households.filter(h => !h.archived).map(h => ({
                rank: 0,
                id: h.id,
                name: h.name,
                member_count: h.people.filter(p => !p.archived).length,
                engagement_score: h.engagement_score,
                base_score: h.total_score,
                occupancy_score: null,
                total_score: h.total_score,
              }))
            : [...matchingGroups
                .flatMap(g => g.households)
                .reduce((best, h) => {
                  const prev = best.get(h.id);
                  if (!prev || h.total_score > prev.total_score) best.set(h.id, h);
                  return best;
                }, new Map<number, RankedHousehold>())
                .values()];
          const rankingRows: RankedHousehold[] = [...selectedRanked]
            .sort((a, b) => b.total_score - a.total_score)
            .map((h, index) => ({ ...h, rank: index + 1 }));

          const rankingColumns: GridColDef<RankedHousehold>[] = [
            { field: 'rank', headerName: 'Rang', width: 80, type: 'number' },
            { field: 'name', headerName: 'Haushaltsname', flex: 1, minWidth: 180 },
            { field: 'member_count', headerName: 'Mitglieder', width: 100, type: 'number' },
            {
              field: 'base_score', headerName: 'Grundpunktzahl', width: 140, type: 'number',
              valueFormatter: (value: number | undefined) => value?.toFixed(2) ?? '—',
            },
            {
              field: 'occupancy_score', headerName: 'Wohnraumausnutzung', width: 170, type: 'number',
              description: 'Punkte dafür, dass der Haushalt die Wohnung mit seinen Mitgliedern ausfüllt (Mitglieder ≥ Zimmer).',
              valueFormatter: (value: number | null | undefined) =>
                value === null || value === undefined ? '—' : value.toFixed(2),
            },
            {
              field: 'total_score', headerName: 'Gesamtpunktzahl', width: 140, type: 'number',
              renderCell: (params: GridRenderCellParams<RankedHousehold>) => <strong>{params.value?.toFixed(2)}</strong>,
            },
          ];

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
                    <MenuItem value={FILTER_ALL}>Alle</MenuItem>
                    {sizes.map(s => (
                      <MenuItem key={sizeKey(s)} value={sizeKey(s)}>{sizeLabel(s)}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl sx={{ minWidth: 200 }}>
                  <InputLabel>Förderungsart</InputLabel>
                  <Select
                    value={selectedFunding}
                    label="Förderungsart"
                    onChange={(e) => setSelectedFunding(e.target.value)}
                  >
                    <MenuItem value={FILTER_ALL}>Alle</MenuItem>
                    {fundingTypes.map(f => (
                      <MenuItem key={f} value={f}>{f}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>

              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                {unfiltered
                  ? 'Ohne Filter wird nur die Grundpunktzahl gezeigt: die Wohnraumausnutzung ergibt sich erst aus der Zimmerzahl der Wohnung.'
                  : 'Die Wohnraumausnutzung gilt je Wohnungsgröße — ein Haushalt, der die Wohnung ausfüllt (Mitglieder ≥ Zimmer), erhält hier volle Punkte, sonst 0.'}
              </Typography>

              {rankingRows.length > 0 ? (
                <DataGrid
                  rows={rankingRows}
                  columns={rankingColumns}
                  autoHeight
                  density="compact"
                  disableRowSelectionOnClick
                  initialState={{
                    sorting: { sortModel: [{ field: 'rank', sort: 'asc' }] },
                    pagination: { paginationModel: { pageSize: 100 } },
                  }}
                  pageSizeOptions={[10, 25, 50, 100]}
                  localeText={deDE.components.MuiDataGrid.defaultProps.localeText}
                />
              ) : (
                <Paper sx={{ p: 3, textAlign: 'center' }}>
                  <Typography color="textSecondary">
                    {unfiltered
                      ? 'Keine Haushalte vorhanden.'
                      : 'Kein Haushalt kommt für diese Wohnungskategorie in Frage.'}
                  </Typography>
                </Paper>
              )}
            </Box>
          );
        })()}

        {tabValue === 1 && (() => {
          const householdColumns: GridColDef<Household>[] = [
            {
              field: 'name', headerName: 'Haushaltsname', flex: 1, minWidth: 180,
              renderCell: (params: GridRenderCellParams<Household>) => (
                <>
                  {params.value}
                  {params.row.archived && <Chip label="Archiviert" size="small" sx={{ ml: 1 }} color="default" />}
                </>
              ),
            },
            {
              field: 'people_count', headerName: 'Mitglieder', width: 100, type: 'number',
              valueGetter: (_value: unknown, row: Household) => row.people.length,
            },
            {
              field: 'wbs_status', headerName: 'WBS', width: 100,
              renderCell: (params: GridRenderCellParams<Household>) =>
                params.value ? <Chip label={params.value} size="small" /> : <>–</>,
            },
            {
              field: 'assigned_apartment_unit', headerName: 'Wohnung', width: 110,
              valueFormatter: (value: string | undefined) => value || '—',
            },
            {
              field: 'import_timestamp', headerName: 'Letzter Import', width: 160,
              valueFormatter: (value: string | undefined) => formatDateTime(value),
            },
            {
              field: 'updated_at', headerName: 'Letzte Bearbeitung', width: 160,
              valueFormatter: (value: string | undefined) => formatDateTime(value),
            },
            {
              field: 'total_score', headerName: 'Grundpunktzahl', width: 140, type: 'number',
              description: 'Ohne Wohnraumausnutzung — die kommt je Wohnungsgröße in der Rangliste hinzu.',
              renderCell: (params: GridRenderCellParams<Household>) => <strong>{params.value?.toFixed(2)}</strong>,
            },
          ];

          let visibleHouseholds = households;
          if (filterNoApartment) {
            visibleHouseholds = visibleHouseholds.filter(h => !h.assigned_apartment_unit);
          }
          const hhQuery = householdSearch.trim().toLowerCase();
          if (hhQuery) {
            visibleHouseholds = visibleHouseholds.filter(h =>
              h.name.toLowerCase().includes(hhQuery) ||
              (h.assigned_apartment_unit ?? '').toLowerCase().includes(hhQuery) ||
              (h.apartment_unit ?? '').toLowerCase().includes(hhQuery) ||
              (h.wbs_status ?? '').toLowerCase().includes(hhQuery) ||
              h.people.some(pers =>
                `${pers.first_name} ${pers.last_name}`.toLowerCase().includes(hhQuery)
              )
            );
          }

          return (
            <Box>
              <Box sx={{ display: 'flex', mb: 2, alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                <TextField
                  size="small"
                  placeholder="Haushalt, Wohnung oder Person suchen"
                  value={householdSearch}
                  onChange={(e) => setHouseholdSearch(e.target.value)}
                  sx={{ minWidth: 320 }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
                      ),
                    },
                  }}
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={filterNoApartment}
                      onChange={(_, checked) => setFilterNoApartment(checked)}
                    />
                  }
                  label="Nur ohne Wohnung"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={showArchivedHH}
                      onChange={(_, checked) => setShowArchivedHH(checked)}
                    />
                  }
                  label="Archivierte anzeigen"
                />
                <Box sx={{ flexGrow: 1 }} />
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateHHOpen(true)}>
                  Haushalt anlegen
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {visibleHouseholds.length} von {households.length} Haushalten
              </Typography>
              <DataGrid
                rows={visibleHouseholds}
                columns={householdColumns}
                autoHeight
                density="compact"
                disableRowSelectionOnClick
                onRowClick={(params) => setDetailHouseholdId(params.row.id)}
                initialState={{
                  sorting: { sortModel: [{ field: 'total_score', sort: 'desc' }] },
                  pagination: { paginationModel: { pageSize: 100 } },
                }}
                pageSizeOptions={[10, 25, 50, 100]}
                getRowClassName={(params) => params.row.archived ? 'archived-row' : ''}
                sx={{
                  '& .MuiDataGrid-row': { cursor: 'pointer' },
                  '& .archived-row': { opacity: 0.5 },
                }}
                localeText={deDE.components.MuiDataGrid.defaultProps.localeText}
              />
            </Box>
          );
        })()}

        {tabValue === 2 && (
          <PersonsTab onShowHousehold={(id) => setDetailHouseholdId(id)} />
        )}

        {tabValue === 3 && (
          <ApartmentsTab
            onShowHousehold={(id) => setDetailHouseholdId(id)}
            onChanged={loadData}
          />
        )}

        {tabValue === 4 && (() => {
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

        {tabValue === 5 && (
          <ImportTab onImportComplete={loadData} />
        )}

        {tabValue === 6 && (
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

      <CreateHouseholdDialog
        open={createHHOpen}
        onClose={() => setCreateHHOpen(false)}
        onCreated={(hh) => {
          setCreateHHOpen(false);
          loadData();
          setDetailHouseholdId(hh.id);
        }}
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

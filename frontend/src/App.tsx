import React, { useState, useEffect } from 'react';
import {
  AppBar, Toolbar, Typography, Container, Box, Tabs, Tab,
  Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Button, TextField, Grid, Card, CardContent, Alert, Snackbar, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControl, InputLabel, Select, MenuItem
} from '@mui/material';
import { getHouseholds, getScoringConfig, updateScoringConfig, calculateScores, uploadHouseholds, login, getRanking } from './api';
import { Household, ScoringConfig, RankingGroup } from './types';

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

  useEffect(() => {
    if (isLoggedIn) {
      loadData();
    }
  }, [isLoggedIn]);

  const loadData = async () => {
    try {
      const hh = await getHouseholds();
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
            <Tab label="Bewertungskonfiguration" />
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
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Haushaltsname</TableCell>
                  <TableCell align="right">Mitglieder</TableCell>
                  <TableCell>Mitglied seit</TableCell>
                  <TableCell align="right">Engagement</TableCell>
                  <TableCell>Bewohner</TableCell>
                  <TableCell align="right">Gesamtpunktzahl</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {households.map((hh) => (
                  <TableRow key={hh.id}>
                    <TableCell>{hh.name}</TableCell>
                    <TableCell align="right">{hh.people.length}</TableCell>
                    <TableCell>{hh.member_since ? new Date(hh.member_since).toLocaleDateString('de-DE') : '–'}</TableCell>
                    <TableCell align="right">{hh.engagement_score}</TableCell>
                    <TableCell>{hh.is_resident ? 'Ja' : 'Nein'}</TableCell>
                    <TableCell align="right"><strong>{hh.total_score.toFixed(2)}</strong></TableCell>
                  </TableRow>
                ))}
                {households.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} align="center">Keine Haushalte vorhanden.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {tabValue === 2 && (
          <Grid container spacing={2}>
            {configs.map((conf) => (
              <Grid item xs={12} sm={6} md={4} key={conf.key}>
                <Card>
                  <CardContent>
                    <Typography color="textSecondary" gutterBottom>
                      {conf.key}
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
            <Grid item xs={12}>
              <Button variant="contained" color="primary" onClick={handleSaveConfig}>
                Konfiguration speichern
              </Button>
            </Grid>
          </Grid>
        )}

        {tabValue === 3 && (
          <Box>
            <Grid container spacing={2}>
              <Grid item>
                <Button variant="contained" color="secondary" onClick={handleCalculate}>
                  Punkte neu berechnen
                </Button>
              </Grid>
              <Grid item>
                <Button variant="contained" component="label">
                  Excel-Daten hochladen
                  <input type="file" hidden onChange={handleFileUpload} accept=".xlsx" />
                </Button>
              </Grid>
            </Grid>
          </Box>
        )}
      </Container>

      <Snackbar open={!!message} autoHideDuration={6000} onClose={() => setMessage(null)}>
        <Alert onClose={() => setMessage(null)} severity={message?.type} sx={{ width: '100%' }}>
          {message?.text}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default App;

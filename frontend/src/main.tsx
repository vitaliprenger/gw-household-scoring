import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
  components: {
    MuiDialog: {
      styleOverrides: {
        // Auf dem Handy (unter sm) füllen Dialoge den Bildschirm. Kleine
        // Dialoge (maxWidth="xs", z. B. Bestätigungen) bleiben, wie sie sind.
        paper: ({ theme, ownerState }) =>
          ownerState.maxWidth === 'xs'
            ? {}
            : {
                [theme.breakpoints.down('sm')]: {
                  margin: 0,
                  width: '100%',
                  maxWidth: '100%',
                  height: '100%',
                  maxHeight: 'none',
                  borderRadius: 0,
                },
              },
      },
    },
    MuiStepLabel: {
      styleOverrides: {
        // Die Schritte der Import-Assistenten teilen sich auf dem Handy rund
        // 312 px; in kleinerer Schrift überlappt „Zusammenfassung“ nicht.
        label: ({ theme }) => ({
          [theme.breakpoints.down('sm')]: { fontSize: '0.75rem' },
        }),
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>,
)

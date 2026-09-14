# GW Haushalts-Scoring

Scoring-Anwendung zur Vergabe freier Wohnungen in einem genossenschaftlichen Wohnprojekt.

- **Bedienung** der Anwendung: [docs/Benutzerhandbuch.md](docs/Benutzerhandbuch.md)
- **Fachliche und technische Anforderungen** (für Entwicklung und LLMs): [Instructions.md](Instructions.md)

## Voraussetzungen

- Python 3.12+
- Node.js 20+ (installierbar via `winget install OpenJS.NodeJS`)

## Setup

```powershell
# Virtuelle Umgebung erstellen & aktivieren
python -m venv .venv
.venv\Scripts\Activate.ps1

# Backend-Abhängigkeiten
pip install -r backend/requirements.txt

# Frontend-Abhängigkeiten
cd frontend
npm install
cd ..
```

## Starten

```powershell
# Backend (aus Projekt-Root)
python -m uvicorn backend.main:app --reload

# Frontend (in separatem Terminal)
cd frontend
npm run dev
```

## Test

Die Tests laufen ohne Server gegen eine In-Memory-Datenbank, z. B.:

```powershell
python tests/test_scoring.py
python tests/test_ranking.py
```

Die vollständige Liste steht in [Instructions.md](Instructions.md#konventionen) unter „Konventionen“.

Zusätzlich gibt es einen Integrationstest gegen das laufende Backend:

```powershell
python tests/generate_data.py   # Erstellt test_data.xlsx
python tests/test_flow.py       # Backend muss laufen
```

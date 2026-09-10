# GW Haushalts-Scoring

Scoring-Anwendung zur Vergabe freier Wohnungen in einem genossenschaftlichen Wohnprojekt.

Fachliche und technische Anforderungen sind in [`.instructions.md`](.instructions.md) dokumentiert.

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

```powershell
python tests/generate_data.py   # Erstellt test_data.xlsx
python tests/test_flow.py       # Integration-Test (Backend muss laufen)
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

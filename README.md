# GW Haushalts-Scoring

Scoring-Anwendung zur Vergabe freier Wohnungen in einem genossenschaftlichen Wohnprojekt.

- **Bedienung** der Anwendung: [docs/Benutzerhandbuch.md](docs/Benutzerhandbuch.md)
- **Fachsprache**: [GLOSSARY.md](GLOSSARY.md)
- **Fachliche Grundlage** (Beschluss der Generalversammlung): [docs/Vergabegrundsaetze.md](docs/Vergabegrundsaetze.md)
- **Architekturentscheidungen**: [docs/adr/](docs/adr/)
- **Regeln für die Entwicklung** (für Menschen und LLMs): [CLAUDE.md](CLAUDE.md)
- **Betrieb** (Betriebsvertrag: was die Anwendung in Produktion benötigt): [docs/Betrieb.md](docs/Betrieb.md)

## Voraussetzungen

- Python 3.13 (installierbar via `winget install Python.Python.3.13`)
- Node.js 20+ (installierbar via `winget install OpenJS.NodeJS`)

## Setup

```powershell
# Virtuelle Umgebung erstellen & aktivieren
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1

# Backend-Abhängigkeiten (inkl. Testwerkzeug)
pip install -r backend/requirements-dev.txt

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

Die Anwendung läuft unter http://localhost:3000.

## Datenbankschema ändern

```powershell
alembic revision --autogenerate -m "kurze beschreibung"   # erzeugt backend/migrations/versions/…
python tests/test_migrations.py
```

Regeln dazu: [CLAUDE.md](CLAUDE.md#migrationen).

## Test

Die Tests laufen ohne Server gegen eine In-Memory-Datenbank:

```powershell
python -m pytest                              # alle Tests
python -m pytest tests/test_ranking.py        # eine Datei
```

Zusätzlich gibt es einen Integrationstest gegen das laufende Backend:

```powershell
python tests/generate_data.py   # Erstellt test_data.xlsx
python tests/test_flow.py       # Backend muss laufen
```

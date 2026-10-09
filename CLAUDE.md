# GW Haushalts-Scoring

Entscheidungshilfe der Belegungskommission der Grüner Weiler eG für die Vergabe freier Wohnungen. Code und Tests sind die Wahrheit über das Verhalten; diese Datei hält nur fest, was sich dort nicht ablesen lässt.

## Wo was steht

- **Fachsprache**: [GLOSSARY.md](GLOSSARY.md). Begriffe in Code, Issues und Texten so verwenden, wie sie dort definiert sind.
- **Fachliche Regeln**: [docs/Vergabegrundsaetze.md](docs/Vergabegrundsaetze.md), der GV-Beschluss, auf dem Punkte, Eignung und Vorrang beruhen. Vor jeder Änderung an diesen Regeln lesen.
- **Begründete Entscheidungen**: [docs/adr/](docs/adr/).
- **Bedienung**: [docs/Benutzerhandbuch.md](docs/Benutzerhandbuch.md).
- **Betrieb**: [docs/Betrieb.md](docs/Betrieb.md), der Betriebsvertrag.

## Regeln

### Benutzerhandbuch

Das Handbuch wird unverändert als Hilfe im Frontend angezeigt. Zielgruppe ist die Belegungskommission (9 Personen): Es duzt die Leser\*innen, spricht von der Kommission als „wir“ und enthält keine Implementierungsdetails und keine Links ins Repository. Ändert sich sichtbares Verhalten (Abläufe, Beschriftungen, Symbole, Punkteregeln), das Handbuch im selben Commit anpassen. Wird eine Überschrift umbenannt, `HELP_SECTIONS` in `frontend/src/App.tsx` mitziehen (Anker = Überschrift ohne Nummerierung).

### Betrieb

`docs/Betrieb.md` beschreibt nur, was die Anwendung benötigt und bereitstellt, keine Umsetzung. Ändern sich Umgebungsvariablen, Befehle, Abhängigkeiten, Anforderungen an Laufzeit, Datenbank oder HTTP-Eingang oder der Ablauf eines Updates, `docs/Betrieb.md` im selben Commit anpassen.

Ohne `APP_ENV` gilt Entwicklung: `housing.db` im Arbeitsverzeichnis, Passwort `geheim`, Migration beim Start. Mit `APP_ENV=production` wird nur geprüft, nicht migriert.

### Migrationen

- Jede Änderung an `backend/models.py` bekommt eine Alembic-Revision (`alembic revision --autogenerate -m "..."`, danach prüfen und von Hand ergänzen). Datenmigrationen gehören in dieselbe Revision.
- Spaltenänderungen über `op.batch_alter_table` (SQLite, siehe ADR 0001).
- Ausgerollte Revisionen bleiben unverändert; Korrekturen kommen als neue Revision.
- `backend/legacy_migrations.py` ist eingefroren: Es hebt nur Datenbanken aus der Zeit vor Alembic auf `0001_baseline`.

### Code

- Pydantic V2: `from_attributes = True` statt `orm_mode`.
- Relative Imports innerhalb des `backend`-Packages.
- Die Wunschanzeige gibt es zweimal: `backend/wishes.py` und `frontend/src/components/applications/wishes.ts`. Änderungen an beiden vornehmen. `wishes.py` hängt bewusst nur an der Standardbibliothek.
- Das Frontend ruft das Backend relativ unter `/api` auf; in der Entwicklung leitet der Vite-Proxy weiter und entfernt das Präfix.

### Tests

Alle Tests: `python -m pytest` (aus dem Projekt-Root; Abhängigkeiten aus `backend/requirements-dev.txt`). Einzelne Datei oder einzelner Test: `python -m pytest tests/test_<name>.py -k <test>`. Die Tests laufen ohne Server gegen eine In-Memory-Datenbank; `test_migrations.py` und `test_backup.py` nutzen temporäre Dateien. `test_flow.py` braucht ein laufendes Backend, ist von pytest ausgenommen und läuft nur als Skript.

Das Frontend hat keine Tests; dort `npm run build` (in `frontend/`) als Typprüfung nutzen.

Falls `npm` nicht gefunden wird: `$env:Path += ";C:\Program Files\nodejs"`.

## Ablauf für neue Funktionen

`/grill-with-docs` → `/to-spec` → `/contrarian` → `/to-tickets` → `/implement`. Nur das Urteil `BUILD` von `/contrarian` gibt den Weg zu `/to-tickets` frei; `SIMPLIFY` und `KILL` führen zurück zum Grilling.

## Agent skills

### Issue tracker

Issues werden als GitHub Issues in vitaliprenger/gw-household-scoring über die `gh`-CLI verwaltet. See `docs/agents/issue-tracker.md`.

### Triage labels

Standard-Vokabular (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: eine `GLOSSARY.md` + `docs/adr/` im Repo-Root. See `docs/agents/domain.md`.

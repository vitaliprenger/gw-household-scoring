# Betrieb: GW Haushalts-Scoring

> **Zielgruppe:** Betrieb und Automatisierung (auch LLM-gestützt).
> Dieses Dokument ist der **Betriebsvertrag** der Anwendung. Es legt fest, **was die Anwendung
> benötigt und was sie bereitstellt**, nicht wie der Betrieb das umsetzt. Werkzeuge, Pfade,
> Namen, Dienstverwaltung, Webserver, Automatisierung und Überwachung wählt der Betrieb.
> Ändert sich eine Anforderung, wird dieses Dokument im selben Commit angepasst. Maßgeblich ist
> immer die Fassung **in der Version, die ausgerollt wird**:
> `https://raw.githubusercontent.com/vitaliprenger/gw-household-scoring/<version>/docs/Betrieb.md`
>
> **MUSS** kennzeichnet Anforderungen, ohne die die Anwendung nicht korrekt oder nicht sicher
> läuft. Alles andere ist Information oder Empfehlung.

## Überblick

```
Browser ──HTTPS──> HTTP-Eingang
                     ├── /        → statisches Frontend  (Build-Ergebnis frontend/dist)
                     └── /api/    → Backend              (FastAPI/ASGI, genau ein Prozess)
                                      └── SQLite-Datei   (WAL-Modus, Schema über Alembic)
```

Das Frontend spricht das Backend relativ unter `/api` an.

**Warum SQLite:** 9 Nutzer\*innen, wenige hundert Datensätze, ein einziger Backend-Prozess.
Entwicklung und Tests laufen ebenfalls auf SQLite, Produktion nutzt also dieselbe, getestete
Datenbank. Kein Datenbankdienst, keine Datenbankzugangsdaten.

Die Datenbank enthält **personenbezogene Daten** der Bewerber\*innen.

## Versionen

| Branch | Zweck |
|--------|-------|
| `main` | Entwicklung |
| `prod` | **freigegebener Stand**, nur per Fast-Forward von `main` aktualisiert |

Ausgerollt wird `prod` oder ein daraus freigegebener Tag/Commit. Das Repo ist öffentlich.

## Laufzeitumgebung

| Bedarf | Anforderung |
|--------|-------------|
| Betriebssystem | Linux (getestet: Debian 13) |
| Python | **3.13**, Pakete aus `backend/requirements.txt` |
| Node.js | nur für den Frontend-Build, getestet mit Node.js 20; zur Laufzeit nicht nötig |
| Arbeitsspeicher | Laufzeit gering; der Frontend-Build braucht **über 1 GB** |
| Speicher | Anwendung, Abhängigkeiten, Datenbank und Backups: wenige GB |

Der Frontend-Build braucht den **vollständigen Checkout** (er bindet `docs/Benutzerhandbuch.md`
ein). Wo er läuft, ist frei; ausgeliefert wird nur `frontend/dist/`.

## Laufzeitkonfiguration

Backend und alle Befehle unter „Befehle“ brauchen dieselben Umgebungsvariablen:

| Variable | Wert in Produktion | Bedeutung |
|----------|--------------------|-----------|
| `APP_ENV` | `production` | schaltet die Prüfungen unten ein |
| `APP_PASSWORD` | *(Secret)*, **≥ 12 Zeichen, nicht `geheim`** | gemeinsames Login-Passwort |
| `DATABASE_URL` | `sqlite:///<absoluter Pfad>` | z. B. `sqlite:////srv/data/housing.db`: absoluter Pfad = **vier** Schrägstriche |

- Mit `APP_ENV=production` **startet das Backend nicht**, wenn das Passwort die Regeln verletzt
  oder die Datenbank nicht auf der neuesten Migration steht; es migriert dort nicht selbst. Der
  Grund steht in der Fehlerausgabe (stderr) des Prozesses.
- Passwortwechsel: Wert ändern, Backend neu starten.
- **MUSS:** Das Passwort ist nur für den Betrieb und das Backend lesbar.
- Abhängigkeiten installieren und Frontend bauen brauchen keine Laufzeitkonfiguration.

## Backend

- **Start:** ASGI-Anwendung `backend.main:app`, z. B. `uvicorn backend.main:app --host <host>
  --port <port>`. Arbeitsverzeichnis ist das Wurzelverzeichnis des Checkouts (das Paket
  `backend` muss importierbar sein). Host und Port sind frei.
- **MUSS: genau ein Prozess** (bei uvicorn `--workers 1`, keine weiteren Instanzen). Das
  Sitzungstoken liegt im Speicher des Prozesses; nach jedem Neustart melden sich alle neu an.
- **MUSS:** nach einem Absturz und nach einem Neustart des Systems ohne Eingriff wieder laufen.
- **MUSS:** Clients erreichen das Backend nur über den HTTP-Eingang, nicht direkt.
- Schreibzugriff braucht das Backend nur auf das Datenbankverzeichnis.
- Beim ersten Start legt es Wohnungsstammdaten und Scoring-Konfiguration an (idempotent). Alle
  weiteren Daten entstehen über Importe und Eingaben im Frontend.
- Das Backend wertet keine `X-Forwarded-*`-Header aus.

## Datenbank

- **MUSS: lokales Dateisystem**, nicht NFS/CIFS: dort funktionieren die Dateisperren von SQLite
  nicht zuverlässig.
- **MUSS:** Das Backend darf im **Verzeichnis** der Datenbank Dateien anlegen: SQLite legt dort
  `<name>-wal` und `<name>-shm` an. Sie gehören zur Datenbank und werden bei laufendem Backend
  nie gelöscht.
- **MUSS:** Datenbank und Backups sind nur für das Backend und den Betrieb lesbar
  (personenbezogene Daten).
- **MUSS:** Die Datenbankdatei wird bei laufendem Backend nie direkt kopiert; Kopien entstehen
  mit dem Backup-Befehl.

## HTTP-Eingang

Der Eingang (Webserver, Reverse Proxy o. Ä.) muss Folgendes leisten:

| Anforderung | Grund |
|-------------|-------|
| **MUSS:** `/` liefert die Dateien aus `frontend/dist/` aus | Frontend |
| **MUSS:** Pfade außerhalb von `/api/` und `/assets/`, zu denen keine Datei existiert, liefern `index.html` | Routing im Browser |
| **MUSS:** `/api/<pfad>` geht an das Backend als `/<pfad>`, das Präfix entfällt (`/api/health` → `/health`) | Backend kennt kein Präfix |
| **MUSS:** Request-Bodys bis mindestens **25 MB** | Excel- und vCard-Importe |
| **MUSS:** Antworten des Backends werden mindestens **300 s** abgewartet | große Importe und Neuberechnung |
| **MUSS:** `index.html` wird nicht zwischengespeichert (z. B. `Cache-Control: no-cache`) | sonst lädt der Browser nach einem Update alte Assets |
| Dateien unter `/assets/` dürfen unbegrenzt zwischengespeichert werden | Dateinamen enthalten einen Hash |
| **MUSS:** Zugriffe von außerhalb eines vertrauenswürdigen Netzes nur über HTTPS | sonst geht das Passwort im Klartext über das Netz |

Wo TLS terminiert wird, ist frei. Die Anwendung ist nicht für den ungeschützten Betrieb im
Internet gedacht.

## Befehle

Alle Befehle laufen im **Wurzelverzeichnis des Checkouts**, mit der **Laufzeitkonfiguration** und
mit denselben Dateirechten wie das Backend. `python` meint die Python-Umgebung des Backends.

| Zweck | Befehl | Ergebnis |
|-------|--------|----------|
| Python-Abhängigkeiten | `pip install -r backend/requirements.txt` | |
| Frontend bauen | `cd frontend && npm ci && npm run build` | `frontend/dist/` |
| Migrationsstand prüfen | `python -m backend.migrate --check` | Exit **0** aktuell, **1** ausstehend, sonst Fehler |
| Migrieren | `python -m backend.migrate` | idempotent; legt eine fehlende Datenbank an und übernimmt Datenbanken aus der Zeit vor Alembic |
| Revision ausgeben | `python -m backend.migrate --current` | `current=<rev> head=<rev>` |
| Backup | `python -m backend.backup <verzeichnis> --label <label> [--keep-days N]` | Pfad der Datei auf stdout; löscht mit `--keep-days` ältere Backups desselben Labels |
| Gesundheitsprüfung | `GET /api/health` (ohne Anmeldung) | HTTP 200 `{"status": "ok", "db_revision": "<rev>"}` |

Der Backup-Befehl ist auch bei laufendem Backend konsistent und prüft die Kopie mit
`PRAGMA integrity_check`.

## Ablauf beim Aktualisieren

**MUSS:** diese Reihenfolge.

1. Neuen Stand bereitstellen: Python-Abhängigkeiten installieren, Frontend bauen.
2. Migrationsstand prüfen.
3. **Nur bei Exit 1:** Backend stoppen → Backup mit `--label pre-migration` → migrieren.
   Schlägt ein Schritt fehl: **abbrechen, Backend nicht starten**.
4. Backend (neu) starten und das neue Frontend ausliefern.
5. Gesundheitsprüfung: HTTP 200, und `db_revision` entspricht `head` aus „Revision ausgeben“.

### Erstbefüllung mit einer vorhandenen Datenbank

Eine bestehende Datenbankdatei wird **vor dem ersten Ablauf** an den Datenbankpfad gelegt;
Schritt 3 hebt sie auf den aktuellen Stand. Eine vorhandene Produktionsdatenbank wird **nie**
überschrieben. Die Quelldatei muss vollständig sein: Stammt sie aus einer laufenden Anwendung,
vorher die Anwendung beenden oder die Kopie mit dem Backup-Befehl erzeugen.

## Zurückrollen

**MUSS:** Migrationen werden in Produktion **nicht** per `downgrade` zurückgenommen, sondern:

1. Backend stoppen.
2. Backup mit `--label pre-rollback`.
3. `<name>-wal` und `<name>-shm` löschen, das `pre-migration`-Backup an den Datenbankpfad legen
   (Zugriffsrechte wie unter „Datenbank“).
4. Vorherige Version bereitstellen (Abhängigkeiten, Frontend).
5. Backend starten, **ohne** zu migrieren; Gesundheitsprüfung.

Nur Daten zurück (gleiche Version): Schritte 1–3, dann Backend starten. Ist das Backup älter als
der Code, startet das Backend nicht, bis migriert wurde.

## Backups

- **MUSS:** vor jeder Migration (siehe „Ablauf beim Aktualisieren“).
- **MUSS:** zusätzlich regelmäßig, mindestens **täglich**, mit dem Backup-Befehl. Aufbewahrung
  legt der Betrieb fest (Empfehlung: 14 Tage).
- Sicherungen des ganzen Systems (Snapshots, Images) sind möglich, ersetzen den Backup-Befehl aber
  nicht: Einzelne Stände werden aus dessen Dateien wiederhergestellt.

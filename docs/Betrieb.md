# Betrieb: GW Haushalts-Scoring

> **Zielgruppe:** Betrieb und Automatisierung (Ansible, auch LLM-gestützt).
> Dieses Dokument ist der **Betriebsvertrag** der Anwendung und die einzige Quelle für ihren
> Betrieb: Was hier steht, darf eine Deployment-Automatisierung voraussetzen. Ändert sich etwas
> davon, wird dieses Dokument im selben Commit angepasst. Maßgeblich ist immer die Fassung
> **in der Version, die ausgerollt wird**:
> `https://raw.githubusercontent.com/vitaliprenger/gw-household-scoring/<version>/docs/Betrieb.md`

## Überblick

Die gesamte Anwendung läuft in **einem** Proxmox-LXC-Container:

```
Browser ──HTTP(S)──> nginx :80
                      ├── /        → statisches Frontend    (frontend/dist)
                      └── /api/    → uvicorn 127.0.0.1:8000 (FastAPI, systemd-Dienst)
                                        └── SQLite-Datei     (WAL-Modus, Schema über Alembic)
```

nginx liefert das Frontend aus und leitet `/api/` an das Backend weiter; dabei entfällt das
Präfix. Das Frontend spricht das Backend relativ unter `/api` an.

**Warum SQLite:** 9 Nutzer\*innen, wenige hundert Datensätze, ein einziger Backend-Prozess.
Entwicklung und Tests laufen ebenfalls auf SQLite, Produktion nutzt also dieselbe, getestete
Datenbank. Kein Datenbankdienst, keine Datenbankzugangsdaten.

**Container:** Debian 13 (trixie), unprivilegiert, 2 vCPU, **2 GB RAM** (der Frontend-Build
braucht über 1 GB), 10 GB Speicher. Debian 13 bringt Python 3.13 (die Projektversion), Node.js 20
und nginx aus den Standardquellen mit.

## Versionen und Branches

| Branch | Zweck |
|--------|-------|
| `main` | Entwicklung |
| `prod` | **ausgerollter Stand**, nur per Fast-Forward von `main` aktualisiert |

Freigabe einer neuen Version:

```bash
git checkout prod && git merge --ff-only main && git push origin prod
# optional ein Tag, auf den das Deployment gepinnt werden kann
git tag -a v2026.09.1 -m "Release" && git push origin v2026.09.1
```

Ausgerollt wird `prod` oder ein gepinnter Tag/Commit. Das Repo ist öffentlich und wird per
HTTPS ausgecheckt.

## Laufzeitkonfiguration

| Variable | Wert in Produktion | Bedeutung |
|----------|--------------------|-----------|
| `APP_ENV` | `production` | schaltet die Prüfungen unten ein |
| `APP_PASSWORD` | *(Secret)*, **≥ 12 Zeichen, nicht `geheim`** | gemeinsames Login-Passwort |
| `DATABASE_URL` | `sqlite:////var/lib/gw-scoring/housing.db` | absoluter Pfad = **vier** Schrägstriche |

Mit `APP_ENV=production` **startet das Backend nicht**, wenn das Passwort die Regeln verletzt oder
die Datenbank nicht auf der neuesten Migration steht; die Anwendung migriert dort nicht selbst.
Der Grund steht im Journal des Dienstes. Passwortwechsel: Wert in der Umgebungsdatei ändern,
Dienst neu starten.

## Pfade und Rechte

Pfade und Namen sind Vorschläge; eine Automatisierung darf sie über Variablen ändern. Die Rechte
sind verbindlich.

| Zweck | Pfad | Eigentümer | Rechte |
|-------|------|------------|--------|
| Dienstnutzer | `gw-scoring` (Systemnutzer, ohne Login) | | |
| Checkout (vollständig, der Build liest `docs/`) | `/opt/gw-scoring/app` | Dienstnutzer | `0755` |
| virtualenv | `/opt/gw-scoring/venv` | Dienstnutzer | `0755` |
| Umgebungsdatei | `/etc/gw-scoring/gw-scoring.env` | `root`:Dienstnutzer | `0640` |
| Datenbankverzeichnis | `/var/lib/gw-scoring/` | Dienstnutzer | `0750` |
| Datenbank | `/var/lib/gw-scoring/housing.db` | Dienstnutzer | `0640` |
| Backups | `/var/backups/gw-scoring/` | Dienstnutzer | `0700` (Dateien `0600`) |

- Das Datenbankverzeichnis liegt auf **lokalem** Container-Speicher, nicht auf NFS/CIFS: dort
  funktionieren die Dateisperren von SQLite nicht zuverlässig.
- Das **Verzeichnis** muss dem Dienstnutzer gehören: SQLite legt daneben `housing.db-wal` und
  `housing.db-shm` an. Sie gehören zur Datenbank und werden bei laufendem Dienst nie gelöscht.

## Befehle

Alle Befehle laufen **als Dienstnutzer**, im **Checkout-Verzeichnis** und mit der
Laufzeitkonfiguration.

| Zweck | Befehl | Ergebnis |
|-------|--------|----------|
| Python-Abhängigkeiten | `<venv>/bin/pip install -r backend/requirements.txt` | |
| Frontend bauen | `cd frontend && npm ci && npm run build` | `frontend/dist/` |
| Migrationsstand prüfen | `<venv>/bin/python -m backend.migrate --check` | Exit **0** aktuell, **1** ausstehend, sonst Fehler |
| Migrieren | `<venv>/bin/python -m backend.migrate` | idempotent; legt eine fehlende Datenbank an und übernimmt Datenbanken aus der Zeit vor Alembic |
| Revision ausgeben | `<venv>/bin/python -m backend.migrate --current` | `current=<rev> head=<rev>` |
| Backup | `<venv>/bin/python -m backend.backup <verzeichnis> --label <label> [--keep-days N]` | Pfad der Datei auf stdout; löscht mit `--keep-days` ältere Backups desselben Labels |
| Gesundheitsprüfung | `GET /api/health` (ohne Anmeldung) | HTTP 200 `{"status": "ok", "db_revision": "<rev>"}` |

Das Backend selbst startet über die systemd-Unit (siehe „Referenzkonfiguration“).

## Ablauf beim Aktualisieren

Die Reihenfolge ist verbindlich:

1. Neuen Stand auschecken, Python-Abhängigkeiten installieren, Frontend bauen.
2. Migrationsstand prüfen.
3. **Nur bei Exit 1:** Dienst stoppen → Backup mit `--label pre-migration` → migrieren.
   Schlägt ein Schritt fehl: **abbrechen, Dienst nicht starten**.
4. Dienst (neu) starten.
5. Gesundheitsprüfung: HTTP 200, und `db_revision` entspricht `head` aus „Revision ausgeben“.

Beim ersten Start legt die Anwendung Wohnungsstammdaten und Scoring-Konfiguration an
(idempotent). Alle weiteren Daten entstehen über Importe und Eingaben im Frontend.

### Erstbefüllung mit einer vorhandenen Datenbank

Eine bestehende `housing.db` wird **vor dem ersten Ablauf** an den Datenbankpfad kopiert;
Schritt 3 hebt sie auf den aktuellen Stand. Eine vorhandene Produktionsdatenbank wird **nie**
überschrieben. Die Quelldatei muss vollständig sein: Stammt sie aus einer laufenden Anwendung,
vorher die Anwendung beenden oder die Kopie mit dem Backup-Befehl erzeugen.

## Zurückrollen

Migrationen werden in Produktion **nicht** per `downgrade` zurückgenommen, sondern:

1. Dienst stoppen.
2. Backup mit `--label pre-rollback`.
3. `housing.db-wal` und `housing.db-shm` löschen, das `pre-migration`-Backup an den Datenbankpfad
   kopieren.
4. Vorherige Version auschecken, Abhängigkeiten installieren, Frontend bauen.
5. Dienst starten, **ohne** zu migrieren; Gesundheitsprüfung.

## Backups

- Vor jeder Migration (siehe „Ablauf beim Aktualisieren“) und täglich per systemd-Timer (siehe
  „Referenzkonfiguration“).
- Der Backup-Befehl ist auch bei laufendem Dienst konsistent und prüft die Kopie mit
  `PRAGMA integrity_check`. **Die Datenbankdatei wird nie direkt kopiert**, solange der Dienst läuft.
- Ein Proxmox-Backup (vzdump) des Containers sichert die Datenbank zusätzlich mit; einzelne Stände
  werden aus den Backup-Dateien wiederhergestellt.

## Anmeldung

Das Sitzungstoken liegt **im Speicher des Backend-Prozesses**. Deshalb läuft uvicorn mit
**genau einem Worker**, und nach jedem Neustart des Dienstes melden sich alle neu an.

## Referenzkonfiguration

Mit den Pfaden aus „Pfade und Rechte“.

### systemd: Anwendung

```ini
# /etc/systemd/system/gw-scoring.service
[Unit]
Description=GW Haushalts-Scoring (Backend)
After=network.target

[Service]
Type=simple
User=gw-scoring
Group=gw-scoring
WorkingDirectory=/opt/gw-scoring/app
EnvironmentFile=/etc/gw-scoring/gw-scoring.env
ExecStart=/opt/gw-scoring/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/gw-scoring

[Install]
WantedBy=multi-user.target
```

### systemd: tägliches Backup

```ini
# /etc/systemd/system/gw-scoring-backup.service
[Unit]
Description=GW Haushalts-Scoring: tägliches Datenbank-Backup

[Service]
Type=oneshot
User=gw-scoring
Group=gw-scoring
WorkingDirectory=/opt/gw-scoring/app
EnvironmentFile=/etc/gw-scoring/gw-scoring.env
ExecStart=/opt/gw-scoring/venv/bin/python -m backend.backup /var/backups/gw-scoring --label daily --keep-days 14
```

```ini
# /etc/systemd/system/gw-scoring-backup.timer
[Unit]
Description=GW Haushalts-Scoring: tägliches Datenbank-Backup

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

### nginx

```nginx
# /etc/nginx/sites-available/gw-scoring
server {
    listen 80;
    server_name _;

    root /opt/gw-scoring/app/frontend/dist;
    index index.html;

    # Excel- und vCard-Importe
    client_max_body_size 25m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;   # abschließender Slash entfernt das Präfix /api
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;             # große Importe und Neuberechnung
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri /index.html;
        add_header Cache-Control "no-cache";
    }
}
```

TLS terminiert ein vorgelagerter Reverse Proxy oder nginx im Container (zusätzlicher
`listen 443 ssl`-Block). Ohne TLS wird das Passwort im Klartext übertragen; die Anwendung ist
nicht für den ungeschützten Betrieb im Internet gedacht.

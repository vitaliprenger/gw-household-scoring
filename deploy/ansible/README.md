# Rolle `gw_scoring` — GW Haushalts-Scoring

> **Vorlage aus dem Anwendungsrepo** (`deploy/ansible/README.md`). In das Ansible-Projekt nach
> `roles/gw_scoring/README.md` kopieren.
>
> **Hinweis für LLMs:** Diese Datei legt fest, **wie die Rolle gebaut ist**. **Was** auf dem
> Zielsystem passieren muss — Befehle, Umgebungsvariablen, Pfade und Rechte, Reihenfolge beim
> Aktualisieren, Zurückrollen, Referenz für systemd und nginx —, steht ausschließlich im
> Betriebsvertrag der Anwendung, **in der Version, die ausgerollt wird**:
>
> `https://raw.githubusercontent.com/vitaliprenger/gw-household-scoring/{{ gw_scoring_version }}/docs/Betrieb.md`
>
> Lies ihn vor jeder Änderung an der Rolle. Verweise wie **› Befehle** meinen den gleichnamigen
> Abschnitt dort. Übernimm keine Inhalte aus dem Betriebsvertrag in diese Datei; ändert er sich,
> wird die Rolle angepasst, nicht diese Beschreibung.

## Zweck

Die Rolle installiert die Anwendung in einem Proxmox-LXC-Container (**› Überblick**) und hält sie
aktuell. Ein und derselbe Playbook-Lauf dient der Erstinstallation und jeder Aktualisierung; ein
wiederholter Lauf ohne neue Version meldet `changed=0`.

Nginx im Container nimmt HTTP (Port 80, Referenzkonfiguration) und zusätzlich HTTPS (Port 443) mit
einem selbstsignierten Zertifikat an. Der vorgelagerte Reverse Proxy spricht den Container über
HTTPS an und vertraut diesem Zertifikat (**› Referenzkonfiguration**, letzter Absatz).

Nicht Aufgabe der Rolle: den Container anlegen, TLS-Zertifikate des vorgelagerten Reverse Proxy,
Daten importieren, **Zurückrollen** (siehe unten).

## Variablen

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `gw_scoring_app_password` | – (**Pflicht**, Vault) | Wert für `APP_PASSWORD` |
| `gw_scoring_repo_url` | `https://github.com/vitaliprenger/gw-household-scoring.git` | |
| `gw_scoring_version` | `prod` | Branch, Tag oder Commit |
| `gw_scoring_user` | Referenzwert | Dienstnutzer (**› Pfade und Rechte**) |
| `gw_scoring_base_dir` | Referenzwert | enthält Checkout `app/` und `venv/` |
| `gw_scoring_config_dir` | Referenzwert | Verzeichnis der Umgebungsdatei |
| `gw_scoring_data_dir` | Referenzwert | Datenbankverzeichnis |
| `gw_scoring_backup_dir` | Referenzwert | Backups |
| `gw_scoring_backup_retention_days` | Referenzwert | `--keep-days` des täglichen Backups |
| `gw_scoring_backup_time` | Referenzwert | `OnCalendar` des Backup-Timers |
| `gw_scoring_backend_port` | Referenzwert | Port von uvicorn |
| `gw_scoring_server_name` | Referenzwert | `server_name` in nginx; CN/SAN des Zertifikats |
| `gw_scoring_client_max_body_size` | Referenzwert | Upload-Grenze in nginx |
| `gw_scoring_initial_db_file` | `""` | optional: Datei auf dem Controller für **› Erstbefüllung** |
| `gw_scoring_tls_cert` | `<config_dir>/tls/<server_name>.crt` | selbstsigniertes Zertifikat für Port 443 |
| `gw_scoring_tls_key` | `<config_dir>/tls/<server_name>.key` | zugehöriger Schlüssel |
| `gw_scoring_tls_days` | `3650` | Gültigkeit des Zertifikats in Tagen |

„Referenzwert“ = der Wert aus **› Pfade und Rechte** bzw. **› Referenzkonfiguration**, in
`defaults/main.yml` hinterlegt. Abgeleitete Werte (Pfade von Checkout, virtualenv, Umgebungsdatei
und Datenbank sowie die Laufzeitkonfiguration) stehen in `vars/main.yml` und werden nicht gesetzt.
Die Datenbank-URL wird aus `gw_scoring_data_dir` abgeleitet und ist keine eigene Variable.

## Aufbau

```
roles/gw_scoring/
├── README.md
├── defaults/main.yml
├── vars/main.yml                # abgeleitete Pfade, Laufzeitkonfiguration als Dict
├── handlers/main.yml            # reload nginx, daemon-reload
├── tasks/
│   ├── main.yml                 # bindet die Schritte unten in dieser Reihenfolge ein
│   ├── validate.yml
│   ├── packages.yml
│   ├── layout.yml
│   ├── checkout.yml
│   ├── build.yml
│   ├── config.yml
│   ├── migrate.yml
│   ├── service.yml
│   ├── nginx.yml
│   ├── backup.yml
│   └── verify.yml
└── templates/                   # je eine Datei aus › Referenzkonfiguration und die Umgebungsdatei
```

Es gibt **kein** Rollback-Playbook und keine `tasks/rollback.yml`.

## Schritte

| # | Datei | Umsetzung | Grundlage |
|---|-------|-----------|-----------|
| 1 | `validate` | `assert` auf `gw_scoring_app_password`, **bevor irgendetwas geändert wird** | › Laufzeitkonfiguration |
| 2 | `packages` | Pakete für alle Befehle, dazu `acl` und `sudo` (für `become_user`) | › Überblick, › Befehle |
| 3 | `layout` | Dienstnutzer und Verzeichnisse (Basisverzeichnis gehört dem Dienstnutzer und ist sein HOME, für die Caches von npm und pip); bei gesetztem `gw_scoring_initial_db_file` Kopie mit `force: false` | › Pfade und Rechte, › Erstbefüllung |
| 4 | `checkout` | `ansible.builtin.git`, `force: true`; Ergebnis als `app_checkout` registrieren | › Versionen und Branches |
| 5 | `build` | nur wenn `app_checkout.changed` oder virtualenv bzw. `frontend/dist` fehlen | › Befehle |
| 6 | `config` | Umgebungsdatei aus Template | › Laufzeitkonfiguration, › Pfade und Rechte |
| 7 | `migrate` | Schritte 2–3; `--check` mit `failed_when: rc not in [0, 1]` und `changed_when: false`; stdout des Backups registrieren und bei einem Fehler in der Meldung nennen; danach Rechte der Datenbankdatei setzen | › Ablauf beim Aktualisieren |
| 8 | `service` | Unit aus Template, `enabled`; Neustart als Task (nicht Handler) genau dann, wenn Checkout, virtualenv, Umgebungsdatei oder Unit geändert wurden oder migriert wurde; danach `started` | › Referenzkonfiguration |
| 9 | `nginx` | `openssl` installieren, selbstsigniertes Zertifikat einmalig erzeugen (`creates:`, CN/SAN = `gw_scoring_server_name` und IP des Containers); Site aus Template (Referenzkonfiguration plus gleichlautender `listen 443 ssl`-Block), Default-Site deaktivieren, Konfiguration mit `nginx -t` prüfen, Handler `reload nginx`, dann `meta: flush_handlers` | › Referenzkonfiguration |
| 10 | `backup` | Service und Timer aus Templates, Timer `enabled` und `started` | › Referenzkonfiguration |
| 11 | `verify` | `uri` über nginx (Port 80) mit `retries`/`until`, danach Revision vergleichen | › Ablauf beim Aktualisieren, Schritt 5 |

## Regeln für die Umsetzung

- **Nur der Betriebsvertrag:** Die Rolle führt ausschließlich die Befehle aus **› Befehle** aus und
  setzt die **› Referenzkonfiguration** mit Variablen um. Keine eigenen SQL-, `alembic`- oder
  `sqlite3`-Aufrufe, keine eigenen Abläufe für Migration, Backup oder Rollback. Einzige Ergänzung:
  der `listen 443 ssl`-Block mit selbstsigniertem Zertifikat.
- **Befehle der Anwendung** laufen mit `become_user: "{{ gw_scoring_user }}"`,
  `chdir: "{{ gw_scoring_base_dir }}/app"` und der Laufzeitkonfiguration als `environment:` am
  Task (aus Rollenvariablen, nicht per `source` der Umgebungsdatei).
- **Idempotenz:** `changed_when` an jedem `command`/`shell`-Task.
- **Secrets:** `no_log: true` an jedem Task, der das Passwort oder die Umgebungsdatei berührt.
  Damit Fehler trotzdem lesbar bleiben, stehen Build und Migration in einem `block` mit `rescue`,
  das Taskname, Exit-Code und das Ende von stderr aus `ansible_failed_result` meldet.
- **`check_mode`** läuft durch, ohne etwas zu verändern; Build, Backup, Migration, `nginx -t` und
  `verify` werden dort übersprungen. Existiert der Dienstnutzer noch nicht (Erstinstallation),
  endet der Check-Lauf nach `layout` mit einem Hinweis.
- **Aktualisieren** = Playbook erneut ausführen. Pinnen über `gw_scoring_version`.

## Zurückrollen

Kein eigener Ablauf in der Rolle. Die Schritte aus **› Zurückrollen** werden von Hand im Container
ausgeführt; der Backup-Befehl läuft dabei wie der Dienst als Dienstnutzer mit der Umgebungsdatei:

```bash
systemctl stop gw-scoring
systemd-run --wait --pipe -p User=gw-scoring -p Group=gw-scoring \
  -p EnvironmentFile=/etc/gw-scoring/gw-scoring.env -p WorkingDirectory=/opt/gw-scoring/app \
  /opt/gw-scoring/venv/bin/python -m backend.backup /var/backups/gw-scoring --label pre-rollback
rm -f /var/lib/gw-scoring/housing.db-wal /var/lib/gw-scoring/housing.db-shm
cp /var/backups/gw-scoring/housing-pre-migration-<…>.db /var/lib/gw-scoring/housing.db
chown gw-scoring:gw-scoring /var/lib/gw-scoring/housing.db && chmod 0640 /var/lib/gw-scoring/housing.db
```

(Pfade und Nutzer = Referenzwerte.) Danach:

- **Nur Daten zurück** (gleiche Version): `systemctl start gw-scoring`. Ist das Backup älter als der
  Code, startet das Backend nicht; ein normaler Playbook-Lauf migriert es.
- **Auch Code zurück:** Playbook mit `-e gw_scoring_version=<vorherige Version>` ausführen. Die
  Datenbank passt zur alten Version, es wird nicht migriert; Checkout, Build, Neustart und `verify`
  laufen wie bei jedem Update. Soll die Version bleiben, `gw_scoring_version` im Inventory pinnen.
  Wird die Datenbank vorher nicht getauscht, bricht `migrate` mit einem Backup ab und der Dienst
  bleibt gestoppt.

## Beispiel-Playbook

```yaml
# gw_scoring.yml – neben roles/, sonst findet Ansible die Rolle ohne roles_path nicht
- hosts: gw_scoring
  become: true
  roles:
    - role: gw_scoring
```

```yaml
# Vault, z. B. host_vars/gw-scoring/vault.yml  (ansible-vault encrypt)
gw_scoring_app_password: "..."
```

## Abnahmekriterien

Nachweisbar in einem frischen Container nach **› Überblick**:

1. **Erstlauf:** Anwendung über nginx erreichbar (Port 80 und 443); Login mit `gw_scoring_app_password` klappt, mit `geheim` nicht.
2. **Rechte:** Gesundheitsprüfung grün; alle Pfade entsprechen **› Pfade und Rechte**.
3. **Idempotenz:** zweiter Lauf ohne Änderungen: `changed=0`, kein Neustart; Zertifikat bleibt erhalten.
4. **Validierung:** ungültiges Passwort: Abbruch in `validate`, nichts verändert.
5. **Update mit Migration:** neuer Commit auf `prod`: `pre-migration`-Backup vorhanden, migriert, neu gestartet, `verify` grün.
6. **Update ohne Migration:** neuer Commit auf `prod`: kein Backup, keine Migration, neu gestartet, `verify` grün.
7. **Fehlgeschlagene Migration:** Abbruch, Dienst gestoppt, Backup vorhanden und in der Meldung genannt.
8. **Erstbefüllung:** Erstlauf mit `gw_scoring_initial_db_file` übernimmt die Daten; ein späterer Lauf überschreibt sie nicht.
9. **Container-Neustart:** Anwendung ohne Eingriff wieder erreichbar.
10. **Tägliches Backup:** Timer aktiv; manueller Start erzeugt ein `daily`-Backup; ältere als `gw_scoring_backup_retention_days` werden entfernt.
11. **Zurückrollen:** Mit den Schritten unter „Zurückrollen“ und einem Lauf mit gepinnter `gw_scoring_version` ist ein `pre-migration`-Stand wiederhergestellt; `verify` grün.
12. **Lint:** `ansible-lint` ohne Fehler.

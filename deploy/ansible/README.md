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

Nicht Aufgabe der Rolle: den Container anlegen, TLS-Zertifikate eines vorgelagerten Reverse Proxy,
Daten importieren.

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
| `gw_scoring_server_name` | Referenzwert | `server_name` in nginx |
| `gw_scoring_client_max_body_size` | Referenzwert | Upload-Grenze in nginx |
| `gw_scoring_initial_db_file` | `""` | optional: Datei auf dem Controller für **› Erstbefüllung** |
| `gw_scoring_restore_file` | – | nur Rollback: Backup-Datei auf dem Ziel |

„Referenzwert“ = der Wert aus **› Pfade und Rechte** bzw. **› Referenzkonfiguration**, in
`defaults/main.yml` hinterlegt. Die Datenbank-URL wird aus `gw_scoring_data_dir` abgeleitet und
ist keine eigene Variable.

## Aufbau

```
roles/gw_scoring/
├── README.md
├── defaults/main.yml
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
│   ├── verify.yml
│   └── rollback.yml             # nur über tasks_from, nicht in main.yml
└── templates/                   # je eine Datei aus › Referenzkonfiguration und die Umgebungsdatei
```

Rollback-Playbook im Ansible-Projekt: `playbooks/gw_scoring_rollback.yml` mit
`include_role: { name: gw_scoring, tasks_from: rollback }`.

## Schritte

| # | Datei | Umsetzung | Grundlage |
|---|-------|-----------|-----------|
| 1 | `validate` | `assert` auf `gw_scoring_app_password`, **bevor irgendetwas geändert wird** | › Laufzeitkonfiguration |
| 2 | `packages` | Pakete für alle Befehle, dazu `acl` (für `become_user`) | › Überblick, › Befehle |
| 3 | `layout` | Dienstnutzer und Verzeichnisse; bei gesetztem `gw_scoring_initial_db_file` Kopie mit `force: false` | › Pfade und Rechte, › Erstbefüllung |
| 4 | `checkout` | `ansible.builtin.git`, `force: true`; Ergebnis als `app_checkout` registrieren | › Versionen und Branches |
| 5 | `build` | nur wenn `app_checkout.changed` oder virtualenv bzw. `frontend/dist` fehlen | › Befehle |
| 6 | `config` | Umgebungsdatei aus Template | › Laufzeitkonfiguration, › Pfade und Rechte |
| 7 | `migrate` | Schritte 2–3; `--check` mit `failed_when: rc not in [0, 1]` und `changed_when: false`; stdout des Backups registrieren und bei einem Fehler in der Meldung nennen | › Ablauf beim Aktualisieren |
| 8 | `service` | Unit aus Template, `enabled`; Neustart als Task (nicht Handler) genau dann, wenn Checkout, virtualenv, Umgebungsdatei oder Unit geändert wurden oder migriert wurde | › Referenzkonfiguration |
| 9 | `nginx` | Site aus Template, Default-Site deaktivieren, Konfiguration mit `nginx -t` prüfen, Handler `reload nginx`, dann `meta: flush_handlers` | › Referenzkonfiguration |
| 10 | `backup` | Service und Timer aus Templates, Timer `enabled` und `started` | › Referenzkonfiguration |
| 11 | `verify` | `uri` über nginx mit `retries`/`until`, danach Revision vergleichen | › Ablauf beim Aktualisieren, Schritt 5 |
| – | `rollback` | alle Schritte, Pflichtvariablen `gw_scoring_version` und `gw_scoring_restore_file`, danach `verify` | › Zurückrollen |

## Regeln für die Umsetzung

- **Nur der Betriebsvertrag:** Die Rolle führt ausschließlich die Befehle aus **› Befehle** aus und
  setzt die **› Referenzkonfiguration** mit Variablen um. Keine eigenen SQL-, `alembic`- oder
  `sqlite3`-Aufrufe, keine eigenen Abläufe für Migration, Backup oder Rollback.
- **Befehle der Anwendung** laufen mit `become_user: "{{ gw_scoring_user }}"`,
  `chdir: "{{ gw_scoring_base_dir }}/app"` und der Laufzeitkonfiguration als `environment:` am
  Task (aus Rollenvariablen, nicht per `source` der Umgebungsdatei).
- **Idempotenz:** `changed_when` an jedem `command`/`shell`-Task.
- **Secrets:** `no_log: true` an jedem Task, der das Passwort oder die Umgebungsdatei berührt.
- **`check_mode`** läuft durch, ohne etwas zu verändern; Build, Backup und Migration werden dort
  übersprungen.
- **Aktualisieren** = Playbook erneut ausführen. Pinnen über `gw_scoring_version`.

## Beispiel-Playbook

```yaml
# playbooks/gw_scoring.yml
- hosts: gw_scoring
  become: true
  roles:
    - role: gw_scoring
```

```yaml
# host_vars/gw-scoring/vault.yml  (ansible-vault encrypt)
gw_scoring_app_password: "..."
```

## Abnahmekriterien

Nachweisbar in einem frischen Container nach **› Überblick**:

1. **Erstlauf:** Anwendung über nginx erreichbar; Login mit `gw_scoring_app_password` klappt, mit `geheim` nicht.
2. **Rechte:** Gesundheitsprüfung grün; alle Pfade entsprechen **› Pfade und Rechte**.
3. **Idempotenz:** zweiter Lauf ohne Änderungen: `changed=0`, kein Neustart.
4. **Validierung:** ungültiges Passwort: Abbruch in `validate`, nichts verändert.
5. **Update mit Migration:** neuer Commit auf `prod`: `pre-migration`-Backup vorhanden, migriert, neu gestartet, `verify` grün.
6. **Update ohne Migration:** neuer Commit auf `prod`: kein Backup, keine Migration, neu gestartet, `verify` grün.
7. **Fehlgeschlagene Migration:** Abbruch, Dienst gestoppt, Backup vorhanden und in der Meldung genannt.
8. **Erstbefüllung:** Erstlauf mit `gw_scoring_initial_db_file` übernimmt die Daten; ein späterer Lauf überschreibt sie nicht.
9. **Container-Neustart:** Anwendung ohne Eingriff wieder erreichbar.
10. **Tägliches Backup:** Timer aktiv; manueller Start erzeugt ein `daily`-Backup; ältere als `gw_scoring_backup_retention_days` werden entfernt.
11. **Rollback:** Das Rollback-Playbook stellt einen `pre-migration`-Stand wieder her; `verify` grün.
12. **Lint:** `ansible-lint` ohne Fehler.

# SQLite auch in Produktion

Die Anwendung läuft auch in Produktion auf SQLite (WAL-Modus, Schema über Alembic) statt auf einem Datenbankserver. Neun Nutzer\*innen, wenige hundert Datensätze und ein einziger Backend-Prozess rechtfertigen keinen eigenen Dienst; Entwicklung, Tests und Produktion laufen so auf derselben, getesteten Datenbank. Die Folgen für den Betrieb (lokales Dateisystem, ein Prozess, Backups bei offener Verbindung) stehen in [Betrieb.md](../Betrieb.md).

## Consequences

Spaltenänderungen in Migrationen laufen über `op.batch_alter_table`, weil SQLite Spalten nur über einen Tabellen-Neuaufbau ändern kann.

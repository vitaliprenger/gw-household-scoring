# Automatische Zuordnung nach Treffer-Art, nicht nach Ähnlichkeitswert

Beim Import wird eine Zeile nur dann automatisch einem Haushalt oder einer Person zugeordnet, wenn die Treffer-Art eindeutig ist: gleiche Mitgliedsnummer, exakt gleicher Personenname, eindeutiger Haushaltsname oder ein Namenstreffer, den die genannte Wohnung bestätigt. Ein unscharfer Namensvergleich erreicht mühelos 90 % und mehr; eine reine Prozentschwelle hätte ihn zum sicheren Treffer gemacht und Dubletten oder Verschmelzungen erzeugt. Ähnliche Treffer bleiben Vorschläge, über die ein Mensch entscheidet.

## Consequences

- Wo die Alternative selbst Daten anlegt (vCard, Bewerbungsliste), stehen unsichere Zeilen auf „Bitte entscheiden“, und der Import ist gesperrt, bis alle entschieden sind.
- Der Name benennt den Bewerber, die Wohnung bestätigt ihn nur: Die Bewerbungsliste nennt die Wohnung zum Zeitpunkt der Bewerbung, in der heute jemand anderes wohnen kann.
- Unbekannte Aktionen behandeln alle Commit-Endpunkte wie „Überspringen“.

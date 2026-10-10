---
status: superseded by ADR-0011
---

# Importkette: die vCard legt an, die Fragebögen ergänzen

Die vier Importe laufen in fester Reihenfolge: vCard-Mitgliederliste, Individualbogen, Haushaltsbogen, Bewerbungsliste. Nur die vCard legt Personen an, und Haushalte nur bei erkannter Wohnungsnummer; die Fragebögen ergänzen ausschließlich Vorhandenes. So hängt die Vollständigkeit der Personen an einer einzigen Quelle, und die Fragebögen können keine konkurrierenden Dubletten erzeugen.

Bewusste Ausnahme: Der Bewerbungslisten-Import darf Haushalte anlegen. Wartepool-Haushalte wohnen noch nicht im Projekt, die vCard legt für sie keinen Haushalt an; ohne die Ausnahme bliebe der halbe Wartepool außerhalb der Anwendung. Vorhandene Personen ohne Haushalt werden dabei zur Zuordnung vorgeschlagen.

## Consequences

Alle Importe löschen nie etwas, und leere Werte überschreiben keine vorhandenen Angaben.

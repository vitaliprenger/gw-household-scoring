---
name: contrarian
description: Gegenprüfung eines fertigen Specs vor dem Zerlegen in Tickets. Versucht, den Spec zu verhindern, und urteilt BUILD, SIMPLIFY oder KILL. Use when the user says "contrarian", "red-team this spec" or "versuch den Plan zu killen", or after /to-spec before /to-tickets.
---

# contrarian

`/to-spec` hält fest, *was* gebaut werden soll. Dieser Skill prüft, ob es gebaut werden *muss*. Ein Spec kann in sich stimmig sein und trotzdem Maschinerie bauen, die vorhandener Code, eine vorhandene Einstellung oder ein Handgriff der Belegungskommission schon abdeckt. Die billigste Absage ist die auf dem Papier.

Arbeite als **Gegner**: Dein erklärtes Ziel ist, dass der Spec nicht gebaut wird. Urteile **unabhängig**: Leite jede Antwort selbst aus Code, Glossar, ADRs und Vergabegrundsätzen her; die Begründungen im Spec und im Grilling-Verlauf sind Behauptungen, keine Belege. Läuft dieser Skill im selben Kontext wie das Grilling, gib die Prüfung an einen Subagenten, der nur den Spec als Auftrag bekommt.

## 1. Spec laden

Der Spec ist ein GitHub-Issue; lies ihn wie in `docs/agents/issue-tracker.md` unter „Read an issue“. Nimm das genannte Issue, sonst das zuletzt mit `/to-spec` veröffentlichte. Lies dazu `GLOSSARY.md`, `docs/adr/` und `docs/Vergabegrundsaetze.md`.

**Fertig, wenn** das Problem, das der Spec löst, in einem Satz in den Begriffen des Glossars formuliert ist.

## 2. Angriffe

In dieser Reihenfolge:

1. **Notwendigkeit**: Durchsuche `backend/`, `frontend/` und `tests/` nach Vorhandenem, das das Problem schon löst. Belege mit `datei:zeile`.
2. **Einfachster Weg**: Konstruiere die billigste Lösung aus Vorhandenem: Bewertungskonfiguration (Gewichte, Zielwerte), Sonderfall-Kennzeichen, Excel-Export, Datenpflege im Frontend oder ein Handgriff der Belegungskommission ganz ohne Code. Vergleiche ehrlich mit dem Spec: Was leistet der Spec, was der einfache Weg nicht leistet, und verlangt das Problem diesen Unterschied?
3. **Komplexitätsbudget**: Zähle jedes neue Teilsystem auf: Tabelle oder Spalte (also eine Alembic-Revision), Endpunkt, Tab oder Dialog, Import, Konfigurationswert, Abhängigkeit. Für jedes muss der Spec begründen, warum nichts Vorhandenes reicht; eine fehlende Begründung ist ein Befund.
4. **Regelkonflikt**: Prüfe den Spec gegen die Vergabegrundsätze und die ADRs. Ein Widerspruch, den der Spec nicht ausdrücklich begründet, ist ein Befund; nenne die Stelle.
5. **Einwand der Belegungskommission**: Formuliere in ein, zwei Sätzen den Einwand, den das kundigste Kommissionsmitglied erheben würde, in dessen Worten.

**Fertig, wenn** jeder der fünf Angriffe einen Befund oder ein begründetes „nichts gefunden“ hat.

## 3. Urteil

- **`BUILD`**: Die Notwendigkeit trägt, jedes neue Teilsystem ist begründet, kein Regelkonflikt ist offen.
- **`SIMPLIFY`**: Ein Teil lässt sich durch einen billigeren Weg aus Vorhandenem ersetzen. Nenne den Teil und den Weg.
- **`KILL`**: Vorhandenes deckt das Problem ab (Beleg `datei:zeile` oder benannter Ablauf), oder der Spec widerspricht den Vergabegrundsätzen.

Schreibe das Urteil als Kommentar an das Spec-Issue:

```md
## contrarian: <BUILD | SIMPLIFY | KILL>

### Einfachster Weg
| Spec | Alternative aus Vorhandenem | Unterschied | Vom Problem verlangt? |
|------|-----------------------------|-------------|-----------------------|

### Neue Teilsysteme
- <Teilsystem>: Begründung vorhanden / fehlt

### Regelkonflikte
- <Vergabegrundsatz oder ADR>: <Befund> (oder „keine“)

### Einwand der Belegungskommission
> <ein, zwei Sätze>
```

## 4. Tor

Stelle das Urteil vor. Nur `BUILD` gibt den Weg zu `/to-tickets` frei. Bei `SIMPLIFY` und `KILL` geht der Spec zurück zu `/grill-with-docs` oder wird verworfen. Halte das Urteil so scharf, wie die Befunde es tragen: Ein `KILL` bleibt ein `KILL`, auch wenn der Spec sorgfältig ausgearbeitet ist.

Herkunft und Lizenz: [SOURCE.md](SOURCE.md).

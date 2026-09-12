# Projektanforderungen: GW Haushalts-Scoring

> **Hinweis für Menschen und LLMs:** Diese Datei ist die zentrale Quelle für alle fachlichen und technischen Anforderungen. Bei jeder Änderung oder Erweiterung der Anforderungen **muss** dieses Dokument entsprechend aktualisiert werden, bevor oder während die Implementierung erfolgt.

## Zweck

Anwendung zur Vergabe freier Wohnungen in einem genossenschaftlichen Wohnprojekt.
Für jeden Haushalt wird ein Scoring berechnet, das die Vergabeentscheidung unterstützt.

---

## Fachliche Anforderungen

### Scoring-Kriterien

| Kategorie | Kriterium | Bewertungslogik |
|-----------|-----------|-----------------|
| **Durchmischung** | Alter | Zielwerte pro Altersgruppe (20–29, 30–39, 40–49, 50–59, 60–69, 70–79, 80–89, >89), orientiert an der Bevölkerungsstruktur Münsters. Berechnungsgrundlage: Bevölkerung Münster ab 20 Jahre (258.677 Personen). Die beiden Gruppen unter 20 (27.067 + 27.815) sind ausgenommen. Anteil je Gruppe = Bevölkerung der Gruppe / 258.677. Die IST-Verteilung wird aus allen Haushalten mit `is_resident=True` berechnet. Je weiter der IST-Wert unter dem Ziel liegt, desto mehr Punkte. Personen unter 20 werden nicht in die Alters-Durchmischung einbezogen. |
| **Durchmischung** | Geschlecht | Zielwerte pro Ausprägung (m/f/d). Akzeptierte Werte: f/w/female/weiblich, m/male/männlich, d/divers/diverse/non-binary. Gleiche Logik wie Alter. |
| **Durchmischung** | Haupttätigkeit | Zielwerte pro Berufskategorie (1–10): 1 Organisation/Verwaltung/Recht, 2 Pädagogik/Psychologie/Soziales, 3 Geistes-/Gesellschafts-/Wirtschaftswiss., 4 Handwerk, 5 Dienstleistung, 6 Kunst/Kultur/Unterhaltung, 7 Landwirtschaft/Gartenbau/Tierpflege, 8 Architektur/Bauplanung, 9 Naturwissenschaft/Geographie, 10 Verkehr/Logistik/Schutz/Sicherheit. Kategorie 0 (kein Eintrag) = 0 Punkte. Gleiche Logik wie Alter. |
| **Durchmischung** | Bildungsabschluss | Zielwerte pro Ausprägung (1–8, orientiert am EQR): 1 Berufsausbildungsvorbereitung, 2 Hauptschulabschluss, 3 Zweijährige Berufsausbildung/Mittlerer Schulabschluss, 4 Dreijährige Berufsausbildung/Hochschulreife (inkl. Fachabitur), 5 Erste berufliche Fortbildungsqualifikation, 6 Bachelor/FH-Diplom/Staatsexamen/Fachwirt/Meister/Fachschule/Berufsakademie, 7 Master/Uni-Diplom/Magister/Staatsexamen/Betriebswirt/Strategischer Professional, 8 Promotion. Kategorie 0 (Keine Antwort) = 0 Punkte. Gleiche Logik wie Alter. |
| **Durchmischung** | Kulturelle Vielfalt | Erfüllungsgrad 0–1 pro Haushalt (Bonus). |
| **Durchmischung** | Besondere Lebenslagen / Finanzen | Erfüllungsgrad 0–1 pro Haushalt (Bonus). |
| **Wohnraumausnutzung** | Ausfüllen der Wohnung | Bewertet, ob der Haushalt die Wohnung mit seinen Mitgliedern **ausfüllt**: Mitgliederzahl ≥ Zimmerzahl ⇒ voller Erfüllungsgrad (1), sonst **0 Punkte**. Hängt an der Zimmerzahl und wird deshalb **je Wohnungsgröße** vergeben, nicht pauschal. |
| **Mitgliedsdauer** | Jahre in Genossenschaft | Pro Person gespeichert (`member_since`). Für das Scoring wird das früheste Eintrittsdatum aller Personen im Haushalt herangezogen. Längere Dauer = mehr Punkte. |
| **Engagement** | Aktives Engagement im Projekt | Erfüllungsgrad 0–1. |

### Scoring-Berechnung

Ein Haushalt erhält **kein pauschales Scoring**, sondern **ein Scoring je in Frage kommender Wohnungsgröße**. Der Score besteht aus zwei Teilen:

**1. Grundpunktzahl** — alle Kriterien, die ausschließlich vom Haushalt selbst abhängen. Sie ist unabhängig von Wohnungsgröße und Wohnungsart, wird von `scoring.run_scoring` berechnet und in `Household.total_score` zwischengespeichert.

- Jedes Kriterium erhält ein **Gewicht** (editierbar über die UI).
- **Zielwert-Kriterien** (Alter, Geschlecht, Haupttätigkeit, Bildung): Punkte = f(Zielwert − IST-Wert) × Anzahl passender Personen im Haushalt.
- **Erfüllungsgrad-Kriterien** (kulturelle Vielfalt, besondere Lebenslagen, Engagement): Punkte = Erfüllungsgrad × Gewicht.
- **Mitgliedsdauer**: Punkte = f(Jahre), gekappt bei Maximum.
- Grundpunktzahl = Σ (Gewicht_i × Teilscore_i).

**2. Wohnraumausnutzung** (§3 Abs. 2) — hängt an der Zimmerzahl der Wohnung und wird deshalb **je Wohnungskategorie** aufgeschlagen (`services.build_ranking`), nicht in der Grundpunktzahl gespeichert.

- Ein Haushalt **füllt eine Wohnung aus**, wenn seine Mitgliederzahl der Zimmerzahl **entspricht oder sie übersteigt**. Dann gilt der volle Erfüllungsgrad (1), sonst 0.
- Punkte = Erfüllungsgrad × `weight_occupancy`.
- Beispiel: Ein Haushalt mit 3 Mitgliedern erhält für eine **3-Zimmer-Wohnung** die vollen Ausnutzungspunkte, für eine **4-Zimmer-Wohnung 0 Punkte**. Sein Gesamtscore ist in der Kategorie „3 Zimmer" also höher als in „4 Zimmer".
- Maßgeblich ist allein die Zimmerzahl, nicht die Wohnungsart: auch Ausbau- und Atelierwohnungen mit Zimmerzahl werden danach bewertet. Wohnungen **ohne Zimmerangabe** kennen keine Zimmerschranke; dort gilt das Kriterium als erfüllt, weil die Eignungsprüfung die Mindestbelegung bereits sicherstellt.
- Da die Eignungsprüfung Wohnungen mit weniger Zimmern als Mitgliedern ausschließt, kommt der Fall „mehr Mitglieder als Zimmer" in der Rangliste nicht vor.

**Gesamt-Score einer Kategorie** = Grundpunktzahl + Wohnraumausnutzung dieser Zimmerzahl.

### Bewerbungen

Eine **Bewerbung** (`Application`) verbindet einen Haushalt mit einem oder mehreren
Wohnungswünschen. Sie richtet sich **nicht** auf eine konkrete Wohnung: die konkrete Wohnung
entsteht erst bei der Erfüllung.

**Drei Bewerbungsarten** (`kind`):

| Art | Wer | Vergabe |
|-----|-----|---------|
| `wartepool` | Haushalte, die **noch nicht** im Wohnprojekt wohnen | per **Scoring** (Rangliste je Wohnungskategorie) |
| `wechselwunsch` | bestehende **Bewohner**-Haushalte | **vorrangig**, nach dem Zeitpunkt des Wunsches (`requested_at`) |
| `joker` | bestehende Haushalte (Joker-Zimmer können nur von ihnen angemietet werden) | nach dem Zeitpunkt des Wunsches; eigene Warteliste, keine Wohnungskategorie |

**Der Wunsch ist kein Freitext.** Er wird als Liste von **Wohnungskategorien** gespeichert
(`Application.wishes`, JSON-Array, validiert über `schemas.ApplicationWish`):

```
{"size_rooms": 2, "funding_type": "WBS A", "apartment_category": null}
```

- Das entspricht genau dem Schlüssel, den `services.apartment_categories` aus den
  Wohnungsstammdaten ableitet. Die Auswahlliste des Frontends entsteht aus den **tatsächlich
  vorhandenen Wohnungen** (`GET /apartments/categories`, `services.apartment_category_options`) —
  ein Wunsch kann deshalb nicht von den Stammdaten abweichen.
- `null` heißt in jedem Feld „egal": so lässt sich auch „WBS B, Größe egal" abbilden.
- Das halbe Zimmer entfällt wie überall im Modell (`3,5` → `size_rooms = 3`); die **Anzeige**
  nutzt die Schreibweise der Liste („3,5 A", `wishes.wish_label`).
- **Ausbau- und Atelierwohnungen zählen als Standardwohnungen** und erzeugen keine eigene
  Wohnungsart im Wunsch. Clusterwohnungen und Joker-Zimmer müssen **ausdrücklich** gewünscht
  werden (`wishes.wish_matches`).

**Status und Historie** (`status`): `offen`, `erfuellt`, `zurueckgezogen`. Erfüllte und
zurückgezogene Bewerbungen bleiben erhalten — so ist rückwirkend einsehbar, welche Bewerbungen es
gab und warum sie endeten (`status_note`). Je Haushalt und Bewerbungsart darf es nur **eine offene**
Bewerbung geben (HTTP 409); die Historie entsteht über den Status, nicht über Dubletten.

**Erfüllung entsteht automatisch**: Zieht ein Haushalt in eine Wohnung ein
(`services.assign_household`), werden alle seine offenen Bewerbungen auf `erfuellt` gesetzt und
mit der Wohnung verknüpft (`fulfilled_apartment_id`, `fulfilled_at`) — siehe
`services.close_open_applications`. Das **Lösen** der Zuordnung nimmt das nicht zurück: die
erfüllte Bewerbung bleibt Historie, eine neue entsteht nicht. Wird die **Wohnung gelöscht**,
verliert die Bewerbung nur den Verweis auf die Wohnung.

**Abweichung von der Regelvergabe**: Gründe, aus denen im Einzelfall von der Regel abgewichen
werden sollte, werden über das Kennzeichen `special_case` (Ja/Nein) mit Begründung
(`special_case_note`) festgehalten. In Bewerbungsübersicht und Rangliste erscheint dazu ein
Warnzeichen mit der Begründung als Tooltip. Der allgemeine Kommentar der gepflegten Liste steht in
`note`.

**Nicht gespeichert** werden „Aktueller Typ" und „Aktuelle Wohnung" der gepflegten Liste: beides
ergibt sich aus der Wohnungszuordnung des Haushalts (`Household.assigned_apartment_unit`).

#### Zuordnung zu Wohnungstypen

- **Wartepool**: Ein Haushalt erscheint in jeder Kategorie, für die er **in Frage kommt**
  (`services.is_eligible`, siehe „Wer kommt für eine Wohnung in Frage?") **und zusätzlich** in
  jeder Kategorie, die er **ausdrücklich wünscht**. Letztere tragen `by_wish_only` und werden in
  der Rangliste als „nur auf Wunsch" gekennzeichnet: die Eignungsprüfung würde sie ausschließen,
  aber die Angaben zum Haushalt (etwa die Mitgliederzahl) sind möglicherweise unvollständig — die
  Entscheidung bleibt bei der Belegungskommission. Sie werden regulär mitgescort und mitgerankt.
- **Wechselwunsch**: Der Haushalt erscheint **nur** in den ausdrücklich gewünschten Kategorien.
  Eine Eignungs-Automatik gibt es hier nicht, weil Bewohner-Haushalte sonst gar nicht in der
  Rangliste stehen.
- **Joker**: bildet keine Wohnungskategorie und erscheint in keiner Rangliste, sondern als eigene
  Warteliste (`services.build_joker_waitlist`, `GET /applications/joker`).

### Ranking

- Bezugsmenge sind ausschließlich Haushalte mit **offener Bewerbung**. Ohne Bewerbung steht ein
  Haushalt in keiner Rangliste.
- Je Wohnungskategorie entstehen zwei Blöcke: der **Vorrang-Block** (Wechselwünsche, nach
  `requested_at` aufsteigend, ohne Score) steht **vor** der score-basierten **Wartepool-Rangliste**.
- Das **Ranking** (Rangvergabe) erfolgt **pro Wohnungskategorie** (Kombination aus Wohnungsgröße und Förderungsart), nicht über alle Haushalte hinweg.
- Innerhalb jeder Kategorie werden die Haushalte nach ihrem **Gesamt-Score dieser Kategorie** (Grundpunktzahl + Wohnraumausnutzung der Zimmerzahl) absteigend sortiert und erhalten einen Rang (1, 2, 3, …). Derselbe Haushalt kann in unterschiedlichen Kategorien unterschiedliche Scores und damit unterschiedliche Ränge haben.
- Ein Haushalt **bewirbt sich nicht auf einzelne Wohnungen**: er erscheint mit seiner Bewerbung in jeder Kategorie, für die er in Frage kommt oder die er wünscht, und damit in der Regel in mehreren Kategorien.

#### Nicht per Scoring vergebene Wohnungen

**Clusterwohnungen** und **Joker-Zimmer** werden nicht über das Scoring vergeben. Sie werden bei der Zuordnung von Haushalten zu Wohnungen ignoriert: aus ihnen entsteht keine Wohnungskategorie, sie erscheinen also weder als Gruppe der Rangliste noch in den Filtern des Ranking-Tabs. In den Wohnungsstammdaten bleiben sie unverändert erhalten und können im Tab „Wohnungen" weiterhin manuell einem Haushalt zugeordnet werden — als Bewohner-Haushalte fließen sie wie gewohnt in die IST-Verteilung der Durchmischung ein.

Maßgeblich ist die Wohnungsart (`apartment_category`); implementiert in `services.is_scored_category` / `services.NON_SCORED_CATEGORIES`, ausgewertet in `services.apartment_categories`. Wohnungen ohne gepflegte Wohnungsart gelten als per Scoring vergeben.

#### Wer kommt für eine Wohnung in Frage?

Ein Haushalt kommt für eine Wohnung in Frage, wenn **alle** drei Bedingungen erfüllt sind:

1. **Mindestbewohner**: Die Zahl der (nicht archivierten) Haushaltsmitglieder erreicht mindestens die `min_occupants` der Wohnung.
2. **Zimmerzahl**: Die Wohnung hat **nicht weniger Zimmer als der Haushalt Mitglieder** (`size_rooms >= Mitgliederzahl`). Das gilt für jede Wohnungsart mit Zimmerzahl; nur Wohnungen ohne Zimmerangabe unterliegen dieser Schranke nicht.
3. **Förderbedingung**: Ein Haushalt darf jede Wohnung bewohnen, deren Förderstufe höchstens seiner eigenen entspricht:
   - **WBS A** darf WBS A, WBS B und freifinanziert bewohnen,
   - **WBS B** darf WBS B und freifinanziert bewohnen,
   - **freifinanziert / ohne Angabe** darf nur freifinanziert bewohnen.

Innerhalb einer Kategorie genügt es, wenn der Haushalt für **eine** der Wohnungen in Frage kommt; maßgeblich ist deshalb die niedrigste `min_occupants` der Kategorie.

Implementiert in `services.is_eligible` / `services.build_ranking`; getestet mit `python tests/test_ranking.py`.

### Wohnungstypen

- **Größe**: 1 bis 5 Zimmer, als **ganze Zahl**. Das halbe Zimmer der Bauplanung entfällt: aus „3,5 Zimmer" wird `size_rooms = 3`.
- **Klein**: Standardwohnungen, die für ihre Zimmerzahl klein ausfallen, tragen das Kennzeichen `is_small`. Das betrifft die sechs Wohnungen, die in der Bauplanung „Mini WG" hießen (P.101, P.102, P.201, P.202, P.301, P.302) — sie sind gewöhnliche 3-Zimmer-Wohnungen am unteren Rand ihrer Größenklasse, keine eigene Wohnungsart.
- **Förderungsart**: „freifinanziert", „WBS A", „WBS B".
- **Wohnungsart** (Mehrfachauswahl): „Standard Wohnungstypen", „Clusterwohnung", „Ausbauwohnung", „Atelierwohnung". „Gartencluster", „C-Riegel" und die Wohngemeinschaften (WPG) sind **keine** eigenen Wohnungsarten, sondern Clusterwohnungen. In den Wohnungsstammdaten kommt zusätzlich „Joker" vor. Der **Wunsch eines Haushalts** wird nicht mehr am Haushalt geführt, sondern strukturiert an seiner Bewerbung (siehe „Bewerbungen"); Ausbau- und Atelierwohnungen zählen dort als Standardwohnungen.
- Wohngemeinschaften (WG) werden **nicht** vergeben.
- Haushalte bewerben sich **nicht** auf konkrete Wohnungen; sie werden über ihre Bewerbung in allen Kategorien geführt, für die sie in Frage kommen oder die sie wünschen (siehe „Bewerbungen" und „Ranking").
- **Gruppiertes Ranking**: Haushalte werden **nicht** über alle Haushalte hinweg gerankt, sondern **pro Wohnungskategorie** (Kombination aus Wohnungsgröße und Förderungsart). Beispiel: Alle Haushalte, die für „3 Zimmer / WBS A" in Frage kommen, erhalten einen eigenen Rang innerhalb dieser Gruppe. Ausbau- und Atelierwohnungen mit Zimmerzahl laufen in der Gruppe ihrer Zimmerzahl; Wohnungen ohne Zimmerangabe bilden eine eigene Gruppe „ohne Zimmerangabe". Clusterwohnungen und Joker-Zimmer bilden überhaupt keine Kategorie, weil sie nicht per Scoring vergeben werden (s. „Nicht per Scoring vergebene Wohnungen").

### Wohnungsstammdaten

Die konkreten Wohnungen der Genossenschaft (131 Einheiten) sind als Stammdaten in der Anwendung hinterlegt. Sie werden **nicht** über einen Import eingelesen: die Daten liegen in `backend/apartment_seed_data.py` und werden beim Start der Anwendung angelegt (`services.seed_apartments`). Der Seed ist **idempotent und additiv** — Wohnungen, deren `unit_number` bereits existiert, bleiben unverändert; im Frontend vorgenommene Änderungen werden also nie überschrieben. Gepflegt werden die Daten anschließend ausschließlich im Frontend (Tab „Wohnungen": anlegen, bearbeiten, löschen).

Darüber hinaus legt die Anwendung **keine Daten** an: Haushalte, Personen und Bewerbungen entstehen ausschließlich über den Import oder die Eingabe im Frontend. Eine leere Datenbank bleibt bis auf die Wohnungsstammdaten und die Scoring-Konfiguration leer. (Beispieldaten für die Tests liegen in `tests/example_data.py`.)

Quelle der Stammdaten ist `imported_data/Wohnungen.xlsx`.

Die Spalte `Etage` aus der Quelldatei wird bewusst **nicht** übernommen; der Rohwert der Spalte `Typ` wird ebenfalls nicht gespeichert, weil er vollständig in Zimmerzahl, Wohnungsart und `is_small` aufgeht.

| Feld | Quelle (Spalte) | Bemerkung |
|------|-----------------|-----------|
| `unit_number` | `Wohnung` | z. B. `P.101`, `W.008.1`; eindeutig, entspricht der Wohnungsnummer aus dem vCard-Import |
| `size_rooms` | abgeleitet aus `Typ` | ganze Zahl (Standardwohnungen 1–5); das halbe Zimmer entfällt (`3.5` → `3`). **Jede Wohnungsart kann eine Zimmerzahl haben.** Bei Clusterwohnungen und Joker ist sie für die Vergabe irrelevant, weil diese nicht per Scoring vergeben werden. Leer = ohne Zimmerangabe |
| `apartment_category` | abgeleitet aus `Typ` | Wohnungsart: numerischer Typ und `Mini WG` → „Standard Wohnungstypen"; `CL`, `CL Punkt`, `C-Riegel` und `WPG` → „Clusterwohnung"; `Ausbau` → „Ausbauwohnung"; `Atelier` → „Atelierwohnung"; `Joker` bleibt eigenständig |
| `is_small` | abgeleitet aus `Typ` | `true` für die sechs `Mini WG`-Wohnungen: Standardwohnungen mit 3 Zimmern, die für ihre Zimmerzahl klein ausfallen. Im Frontend frei setzbar |
| `area_shares` | `qm Anteile` | Fläche für die Anteilsberechnung |
| `area_rent` | `qm mietwirksam` | mietwirksame Fläche |
| `area_utilities` | `qm Nebenkosten` | Fläche für die Nebenkostenumlage |
| `funding_type` | abgeleitet aus `WBS` | `N` → „freifinanziert", `A` und `WPG-A` → „WBS A", `B` → „WBS B", `Joker` und `WPG-Gast` → „freifinanziert" |
| `min_occupants` | `mind. Bewohner` | Mindestbelegung laut Wohnungsübersicht |
| `household_id` | – | Haushalt, der in der Wohnung wohnt (s. u.) |

### Zuordnung von Wohnungen zu Haushalten

- Eine Wohnung kann **keinem oder genau einem** Haushalt zugeordnet sein (`Apartment.household_id`). Die Zuordnung bedeutet: **dieser Haushalt wohnt in dieser Wohnung**.
- Umgekehrt wohnt ein Haushalt in **höchstens einer** Wohnung. Wird ein Haushalt einer neuen Wohnung zugeordnet, wird eine bestehende Zuordnung zu einer anderen Wohnung automatisch gelöst.
- Mit der Zuordnung gilt der Haushalt als aktueller Bewohner: `is_resident` wird implizit gesetzt und — falls noch leer — `apartment_unit` mit der Wohnungsnummer gefüllt. Damit fließt der Haushalt in die IST-Verteilung der Durchmischung ein.
- `is_resident` ist **nicht direkt editierbar**; es wird ausschließlich über die Wohnungszuordnung gesteuert: Zuordnung setzt `is_resident=True`, Lösen setzt `is_resident=False`.
- Die Zuordnung erfolgt **manuell im Tab „Wohnungen"** oder **automatisch durch den vCard-Import** (wenn die Wohnungsnummer einer existierenden Wohnung entspricht).
- Das **Lösen** einer Zuordnung ist kein Löschen: Wohnung und Haushalt bleiben unverändert erhalten.
- Das **Löschen** einer Wohnung entfernt keine Bewerbungen: erfüllte Bewerbungen verlieren nur den Verweis auf die Wohnung.

### Ist-Belegung (aktuelle Bewohner)

- Haushalte mit dem Flag `is_resident=True` stellen die aktuelle Belegung der Genossenschaft dar.
- Aus allen Bewohner-Haushalten wird die **IST-Verteilung** (Alter, Geschlecht etc.) aggregiert.
- Bezugsmenge sind die **nicht archivierten Personen nicht archivierter Bewohner-Haushalte** (`scoring.resident_people`). Archivierte Einträge zählen — wie überall — nicht mit.
- Personen **ohne gepflegte Angabe** zu einem Merkmal (kein Geburtsdatum; kein oder ein nicht erkanntes Geschlecht; Berufs- bzw. Bildungskategorie 0, leer oder nicht erkannt) zählen in **keiner** fachlichen Gruppe mit und werden bei diesem Merkmal **ignoriert**: Bezugsgröße der Anteile ist **je Merkmal die Zahl der Bewohner-Personen mit Angabe** (`scoring.basis_totals`). Unvollständige Datensätze verzerren die IST-Verteilung damit nicht — zählten sie mit, erschiene jede Gruppe kleiner, als sie ist, und Bewerber erhielten zu viele Durchmischungspunkte. Die Anteile aller Gruppen eines Merkmals ergänzen sich zu 100 %.
- Bei den **Altersgruppen** bleiben außerdem die **Personen unter 20** außerhalb der Bezugsgröße (`scoring.EXCLUDED_GROUPS`): Die Zielwerte der Altersstruktur beziehen sich auf die Bevölkerung Münsters ab 20 Jahren, die IST-Anteile deshalb ebenso auf die Bewohner-Personen ab 20. Bei Geschlecht, Haupttätigkeit und Bildungsabschluss zählen Personen unter 20 wie alle anderen mit, sofern die Angabe gepflegt ist.
- Die Abweichung der IST-Verteilung von der Soll-Verteilung bestimmt, wie viele Punkte ein Bewerber-Haushalt für Durchmischung erhält.
- Beim Scoring werden nur Nicht-Bewohner-Haushalte bewertet; Bewohner dienen ausschließlich als Referenzdaten.
- Der **vCard-Import** verknüpft Haushalte mit einer Wohnungsnummer automatisch mit der entsprechenden Wohnung (`services.assign_household`), sofern diese in den Stammdaten existiert. Die Wohnungsnummer wird zusätzlich in `Household.apartment_unit` gespeichert.

### Ist-Statistik der aktuellen Bewohner

Die aggregierte Belegung wird als eigene Seite ausgewiesen (Tab „Ist-Statistik", `GET /statistics/residents`, berechnet in `scoring.calculate_resident_statistics`).

- Grundlage ist **dieselbe Personenmenge wie die IST-Verteilung** der Durchmischung (s. „Ist-Belegung"). Die relativen Zahlen der Seite sind damit exakt die Werte, gegen die die Zielwerte im Scoring verrechnet werden.
- Ausgewiesen werden je Merkmal **absolute Zahlen** (Anzahl Personen bzw. Haushalte) **und relative Zahlen** (Anteil an der Bezugsgröße). Beide Darstellungen zeigen dieselben Daten; die Seite schaltet zwischen ihnen um.
- Merkmale: **Altersgruppen** (ab 20 Jahren; die Zahl der Personen unter 20 wird nur nachrichtlich ausgewiesen, `excluded_groups`), **Geschlecht**, **Haupttätigkeit**, **Bildungsabschluss** — Bezugsgröße sind die Personen — sowie **Haushaltsgröße** — Bezugsgröße sind die Haushalte.
- Zu jeder Ausprägung wird der **Zielwert** aus der Bewertungskonfiguration mitgeliefert, absolut (Zielwert × Bezugsgröße) und relativ, dazu die Abweichung Ist − Ziel. Ohne konfigurierten Zielwert bleiben diese Felder leer; das betrifft die Haushaltsgröße.
- **Datensätze ohne Angabe werden ignoriert** (s. „Ist-Belegung"): Sie bilden keine eigene Ausprägung, die Bezugsgröße (`total`) umfasst je Merkmal nur die Personen mit Angabe. Wie viele Personen beim Merkmal ignoriert wurden, steht in `unknown_count` und wird unter der Tabelle ausgewiesen. Die Kopfzeile nennt zusätzlich die Zahl der Personen mit mindestens einer fehlenden Angabe (`incomplete_person_count`).
- **Prüfliste „ohne Angabe"** (`GET /statistics/residents/missing`, `scoring.resident_people_missing_data`): Fehlende Angaben können auf Fehler beim Datenimport hindeuten. Deshalb lassen sich die betroffenen Personen einzeln prüfen — je Merkmal oder über alle Merkmale. Je Person werden Name, Mitgliedsnummer, Haushalt, Wohnung, Alter und das Datum des Individualbogen-Imports geliefert, dazu je fehlendem Merkmal der Grund (`scoring.missing_value`):
  - **leer** — das Feld ist nicht gepflegt,
  - **Kategorie 0** — bewusst keine Zuordnung (Schüler\*in bzw. „Keine Antwort"),
  - **nicht erkannt** — ein gespeicherter Wert, der keiner Gruppe entspricht, samt Rohwert. Das entsteht, wenn der Individualbogen-Import eine Antwort nicht übersetzen konnte (z. B. „Handwerker" statt „Handwerk") und sie roh übernommen hat.
  - Als **Verdacht auf Importfehler** (`suspected_import_error`) gelten nicht erkannte Werte sowie leere Felder zu Geschlecht, Haupttätigkeit oder Bildungsabschluss bei Personen, für die ein Individualbogen importiert wurde.
- Korrigiert wird über den Haushaltsdetail-Dialog; die Prüfliste verlinkt dorthin. Die Prüfliste enthält genau die Personen, die in der Statistik beim jeweiligen Merkmal ignoriert werden.
- Die Seite ist reine Auswertung: sie verändert keine Daten und stößt keine Berechnung an.

### Archivierung

- Haushalte und Personen können **archiviert** werden (Soft-Delete).
- Beim Archivieren eines Haushalts werden automatisch alle zugehörigen Personen mit archiviert.
- Archivierte Einträge sind in Listen und Rankings **standardmäßig ausgeblendet**.
- Über einen Toggle „Archivierte anzeigen" können sie eingeblendet werden.
- Archivierte Einträge werden beim **Scoring** und im **Ranking** nicht berücksichtigt.
- Archivierte Einträge können jederzeit **wiederhergestellt** werden.

### Löschen von Objekten

- Das **Haushalt**-Objekt ist das führende Objekt. Solange ein Haushalt zugeordnet ist, können zugeordnete Personen und Wohnungen **nicht** gelöscht werden.
- **Haushalt löschen** (`DELETE /households/{id}`): Endgültiges Löschen. Kaskadiert: alle zugehörigen Personen und Bewerbungen werden mitgelöscht. Eine bestehende Wohnungszuordnung wird gelöst (Wohnung bleibt bestehen).
- **Person löschen** (`DELETE /people/{id}`): Nur möglich, wenn die Person **keinem Haushalt zugeordnet** ist (`household_id IS NULL`). Andernfalls wird HTTP 409 zurückgegeben. Person muss zuerst aus dem Haushalt entfernt werden.
- **Alle Personen ohne Haushalt löschen** (`DELETE /people/unassigned`): Löscht sämtliche Personen ohne Haushaltszuordnung in einem Schritt. Archivierte Personen werden nur mitgelöscht, wenn `include_archived=true` übergeben wird — der Aufruf löscht also genau die Personen, die im Personen-Tab mit dem Filter „Nur ohne Haushalt" sichtbar sind. Zugeordnete Personen bleiben unberührt. Antwort: Anzahl der gelöschten Personen.
- **Wohnung löschen** (`DELETE /apartments/{id}`): Nur möglich, wenn **kein Haushalt** der Wohnung zugeordnet ist (`household_id IS NULL`). Andernfalls wird HTTP 409 zurückgegeben. Zuordnung muss zuerst gelöst werden. Bewerbungen, die mit dieser Wohnung erfüllt wurden, bleiben als Historie erhalten und verlieren nur den Verweis auf die Wohnung.
- **Bewerbung löschen** (`DELETE /applications/{id}`): Endgültiges Löschen. Soll eine Bewerbung nur nicht mehr gelten, ist der Status „zurückgezogen" der richtige Weg — dann bleibt sie als Historie erhalten.
- Im Frontend wird der Löschen-Button für Personen nur bei Personen ohne Haushalt angezeigt. Bei Wohnungen wird die Fehlermeldung des Backends angezeigt.

### Zuordnung von Personen zu Haushalten

- Eine Person kann **keinem oder genau einem** Haushalt zugeordnet sein (`Person.household_id` ist optional).
- Personen **ohne Zuordnung** entstehen z. B. beim Einzelpersonen-Import ohne erkannten Haushalt oder nachdem sie aus einem Haushalt entfernt wurden. Sie sind im Personen-Tab über den Filter „Nur ohne Haushalt" auffindbar.
- Eine Person **ohne Haushalt kann einem bestehenden Haushalt zugeordnet** werden — entweder aus dem Personen-Tab heraus (Haushalt auswählen) oder aus der Haushaltsdetailansicht heraus („Person hinzufügen", Auswahl aus den Personen ohne Zuordnung).
- Eine Person kann **aus ihrem Haushalt entfernt** werden. Das ist kein Löschen: Die Person bleibt mit allen Daten erhalten und ist danach ohne Haushaltszuordnung. Beide Aktionen werden vor der Ausführung bestätigt.
- Jede Zuordnungsänderung setzt `Person.updated_at`.
- Zuordnungsänderungen verändern die Haushaltsgröße und damit das Scoring. Der Score wird **nicht automatisch** neu berechnet; dies erfolgt weiterhin über „Score berechnen".

### Datenimport

#### Reihenfolge der Importe

Die vier Importe bauen aufeinander auf und müssen in dieser Reihenfolge ausgeführt werden. Die
beiden **Fragebogen-Importe ergänzen ausschließlich**, was bereits existiert; sie legen weder
Personen noch Haushalte an. Damit hängt die Vollständigkeit der Personenstammdaten an einer
einzigen Quelle und die Fragebögen können keine konkurrierenden Dubletten erzeugen.

| # | Import | Legt an | Ergänzt |
|---|--------|---------|---------|
| 1 | **vCard-Mitgliederliste** (.vcf) | alle enthaltenen Personen; Haushalte **nur** bei erkannter Wohnungszuordnung | vorhandene Personen und Haushalte |
| 2 | **Individualbogen** (.xlsx) | – | vorhandene Personen (auch solche ohne Haushalt) |
| 3 | **Haushaltsbogen** (.xlsx) | Wartepool-**Bewerbung**, falls der Haushalt noch keine offene hat | vorhandene Haushalte |
| 4 | **Bewerbungsliste** (.xlsx) | Bewerbungen **und Haushalte** | vorhandene Bewerbungen |

Der **Bewerbungslisten-Import darf Haushalte anlegen** — bewusst abweichend vom Grundsatz „nur die
vCard legt an". Wartepool-Bewerber wohnen noch nicht im Projekt, der vCard-Import legt für sie
deshalb keinen Haushalt an (er tut das nur bei erkannter Wohnungsnummer). Ohne diese Ausnahme
bliebe der halbe Wartepool außerhalb des Tools. Vorhandene **Personen ohne Haushalt** werden im
Assistenten zur Zuordnung vorgeschlagen, damit keine Dubletten zu den vCard-Personen entstehen.

Die Assistenten von Individual- und Haushaltsbogen bieten deshalb nur noch „Aktualisieren" und „Überspringen" an; Datensätze ohne zuordenbares Ziel werden als `skipped_no_match` ausgewiesen. Fehlen die Basisdaten komplett (keine Personen bzw. keine Haushalte in der Datenbank), weist der jeweilige Assistent im Analyse-Schritt darauf hin, dass zuerst die vCard-Datei zu importieren ist.

#### Zuordnungssicherheit

**Nur ein eindeutiger Treffer wird automatisch zugeordnet.** Ein nur *ähnlicher* Treffer bleibt ein
Vorschlag, über den ein Mensch entscheidet. Die Grenze zieht `schemas.MatchResult.is_certain`; das
Feld wird zentral aus `matched_household_id` und der **Treffer-Art** berechnet und kann von keiner
der vier Treffer-Quellen übergangen werden (auch nicht durch einen mitgelieferten Wert).

Als **eindeutig** gelten (`schemas.CERTAIN_MATCH_TYPES`):

| Treffer-Art | Bedeutung | Wo |
|-------------|-----------|-----|
| `exact_member_nr` | eindeutige **Mitgliedsnummer** | alle Importe (`import_service.match_household`, `match_individual_to_person`) |
| `exact_name_dob` | **exakt übereinstimmender Personenname** — mit bestätigendem Geburtsdatum (`confidence` 1.0) oder ohne (0.9) | alle Importe |
| `exact_household_name` | **Haushaltsname stimmt genau überein** und kommt im Bestand nur einmal vor | Bewerbungsliste (`application_import_service._match_by_household_name`) |
| `apartment_unit` | der Namenstreffer **wohnt zusätzlich** in der Wohnung, die die Zeile nennt — die Wohnung bestätigt ihn | Bewerbungsliste |

**Nicht eindeutig** sind der unscharfe Namenstreffer (`fuzzy`, `confidence` ab 0.7), die bloße
Ähnlichkeit des Haushaltsnamens (`household_name`) und `apartment_occupant` (s. u.). Alle bleiben
im Assistenten sichtbar und über den Treffer-Chip auswählbar — nur vorausgewählt werden sie nie.

**Der Name benennt den Bewerber, die Wohnung bestätigt ihn nur.** Die Reihenfolge in
`application_import_service._match_row` ist deshalb: erst der Name, dann die Wohnungsnummer. Die
Spalte „Aktuelle Wohnung" hält den Stand **zum Zeitpunkt der Bewerbung** fest; bei einer erfüllten
Zeile ist der Haushalt längst ausgezogen und in der genannten Wohnung wohnt jemand anderes. Wer
heute dort wohnt, ist dann gerade **nicht** der Bewerber. Passt der Name zu keinem Haushalt, wird
der heutige Bewohner nur als **Hinweis** ausgewiesen (`apartment_occupant`) — etwa wenn jemand
unter anderem Namen geführt wird —, aber nie automatisch zugeordnet.

Aus demselben Grund prüft die Warnung „Wohnung weicht ab" bei einer **erfüllten** Zeile gegen
„neue Wohnung" statt gegen „Aktuelle Wohnung"; sonst wäre jeder vollzogene Wechsel eine Abweichung.

Maßgeblich ist bewusst die **Treffer-Art und nicht der Prozentwert**: Ein unscharfer Namensvergleich
(`SequenceMatcher`) erreicht mühelos 0.9 und mehr, eine reine Zahlenschwelle würde ihn deshalb zu
einem eindeutigen Treffer machen.

Was statt der Zuordnung vorbelegt wird, hängt davon ab, ob die Alternative selbst Daten erzeugt:

- **Individualbogen und Haushaltsbogen** legen nichts an. Dort ist „Überspringen" die unschuldige
  Vorbelegung; ein Hinweis über der Tabelle nennt die Zahl der unsicheren Treffer.
- **vCard und Bewerbungsliste** würden stattdessen einen Haushalt anlegen — das wäre bei einem
  unsicheren Treffer eine Dublette. Solche Zeilen stehen deshalb auf **„Bitte entscheiden"**, und
  der Import ist gesperrt, solange noch eine offen ist. Über dem Assistenten steht die Zahl der
  offenen Entscheidungen samt den Sammelaktionen „Alle neu anlegen" und „Alle überspringen".

Zusätzlich behandeln **alle Commit-Endpunkte jede unbekannte Aktion wie „Überspringen"**: Eine
unentschiedene Zeile kann auch dann nichts bewirken, wenn sie doch abgeschickt wird. Im Frontend
steht die Regel in `frontend/src/components/import/matching.ts`; getestet in
`tests/test_matching.py`.

#### Mitgliedsnummern

Die Quellen schreiben Mitgliedsnummern mal mit, mal ohne führende Nullen. Beim Mapping gelten beide Schreibweisen als **dieselbe Nummer**: `3` = `003`, `20` = `020`.

- Importierte Nummern werden in die kanonische, **mindestens dreistellige Form mit führenden Nullen** gebracht, wie sie die vCard verwendet (`3` → `003`, `0003` → `003`; längere Nummern wie `1234` bleiben unverändert). Implementiert in `import_service.normalize_member_number`.
- Beim Vergleich werden **beide Seiten** normalisiert (`import_service.same_member_number` / `find_person_by_member_number`), damit auch ältere, ohne führende Nullen gespeicherte Nummern wiedergefunden werden. Das gilt für alle drei Importe (vCard, Individualbogen, Haushaltsbogen).

#### Fragebogen-Importe (Excel)

- Haushalts- und Personendaten werden per **Excel-Upload** (.xlsx) importiert.
- Erwartete Spalten: `Household Name`, `Member Since`, `Engagement Score`, `First Name`, `Last Name`, `Birth Date`, `Gender`, `Occupation`, `Education`, `Cultural Background`, `Special Needs`. `Member Since` wird pro Person gespeichert (bei altem Format ohne personenbezogenes Datum wird der Wert der ersten Zeile für alle Personen des Haushalts übernommen).
- Mehrere Zeilen mit gleichem `Household Name` werden zu einem Haushalt gruppiert.
- **Individualbogen** (`import_service.commit_individual_bogen`): ergänzt Geschlecht, Haupttätigkeit, Bildungsabschluss, kulturellen Hintergrund und besondere Lebenslage bei einer zugeordneten Person. Die Zuordnung berücksichtigt **alle** Personen — auch die vom vCard-Import angelegten Personen **ohne Haushalt**. Eine Mitgliedsnummer wird nur gesetzt, wenn die Person noch keine hat. Neue Personen entstehen nicht.
- **Haushaltsbogen** (`import_service.commit_household_bogen`): ergänzt WBS-Status, Haustiere, Rollstuhlgerechtigkeit und finanzielle Rahmenbedingungen eines bestehenden Haushalts. Der **Wohnungswunsch** wird nicht mehr am Haushalt gespeichert, sondern in dessen offene Wartepool-Bewerbung geschrieben (`import_service._apply_wishes_from_bogen`); existiert keine, wird sie angelegt. Neue **Haushalte** entstehen weiterhin nicht. Neue Haushalte entstehen nicht. Personen des Fragebogens werden über `import_service.match_person_in` (Mitgliedsnummer → Name → Nachname + Geburtsdatum) im Haushalt wiedergefunden, damit abweichende Schreibweisen keine Dubletten zu den bereits per vCard angelegten Personen erzeugen; nur wirklich unbekannte Personen werden dem Haushalt hinzugefügt. Geburtsdatum und Mitgliedsnummer werden dabei nur **gefüllt**, nicht überschrieben — führende Quelle ist die vCard.

#### Bewerbungslisten-Import (.xlsx)

Quelle ist die außerhalb des Tools gepflegte Bewerbungstabelle. Erwartete Spalten:
`Haushalt`, `Typ`, `Aktueller Typ`, `Aktuelle Wohnung`, `(Wechsel-)Wunsch`, `Mail / Info von`,
`Status`, `neue Wohnung`, `Kommentar`. Implementiert in `backend/application_import_service.py`,
zweistufig wie die übrigen Importe (`analyze` → Assistent → `commit`).

**Die Kopfzeile wird tolerant gelesen** (`_norm_header`): Für den Vergleich zählt nur die
Buchstaben- und Ziffernfolge, Leerzeichen und Satzzeichen fallen weg. Die gepflegte Liste schreibt
ihre Kopfzeile nicht buchstabengetreu — „(Wechsel-) Wunsch" mit Leerzeichen nach dem Bindestrich,
„Mail / Info vom" statt „von". Eine nicht erkannte Spalte fällt **stillschweigend** aus dem Import;
genau so blieb der Wunsch anfangs leer.

**Eine Zeile = eine Bewerbung.** Derselbe Haushalt darf mehrfach vorkommen (etwa Wechselwunsch
*und* Joker); das Modell unterscheidet sie über `kind`.

| Spalte | Ziel |
|--------|------|
| `Haushalt` | Zuordnung zum Haushalt (Namen werden zerlegt, siehe unten); bei „Haushalt neu anlegen" auch der Name |
| `Typ` | `Application.kind` (`parse_kind`) |
| `Aktueller Typ`, `Aktuelle Wohnung` | **nicht gespeichert**; im Assistenten nur zum Abgleich, Abweichung als Warnung |
| `(Wechsel-)Wunsch` | `Application.wishes` (`wishes.parse_wish`) |
| `Mail / Info von` | `Application.requested_at` |
| `Status` | `Application.status` (`parse_status`, verkraftet den Zeilenumbruch in „zurück-gezogen") |
| `neue Wohnung` | `Application.fulfilled_apartment_id`, sofern der Status „erfüllt" ist |
| `Kommentar` | `Application.note` — das Kennzeichen `special_case` setzt der Import **nicht** selbst, das entscheidet ein Mensch |

**Zuordnung zum Haushalt** (`_match_row`): zuerst über die Namen der Spalte „Haushalt"
(`import_service.match_household`, ersatzweise der Haushaltsname), danach bestätigt die
Wohnungsnummer den Treffer — sie identifiziert ihn nicht (siehe „Zuordnungssicherheit").
Die Spalte „Haushalt" wird dafür in einzelne Personennamen zerlegt (`split_person_names`):
„Christine (Tine) und Simon Langkamp" → „Christine Langkamp", „Simon Langkamp"; ein Vorname ohne
Nachnamen erbt den Nachnamen des letzten vollständigen Namens der Zelle.

**Wunsch-Parser** (`backend/wishes.py`): „2,5 A" → Zimmerzahl 2 + WBS A · „3,5 frei" →
freifinanziert · „B" → WBS B, Größe egal · „Cluster B" → Clusterwohnung + WBS B · „Joker" →
Joker · „1,5 B Ausbau / Atelier" → ein Wunsch (Ausbau und Atelier zählen als Standard) ·
„3,5 A/B" → zwei Wünsche (eine reine Förderangabe erbt die zuletzt genannte Zimmerzahl derselben
Zelle) · „Ausb", „att", „kl"/„3,5k" sind Abkürzungen der Liste für Ausbau, Atelier und die kleine
Bauvariante und tragen keine eigene Angabe · Wohnungsnummern wie „2,5 A - W.006" sind Hinweise und
kein Wunsch. **Teilstücke, aus denen sich gar nichts ableiten lässt, werden nicht stillschweigend
übernommen**, sondern im Assistenten je Zeile als „nicht erkannt" ausgewiesen — dazu gehört auch
ein Teilstück, das **nur** aus einer Wohnungsnummer besteht („W.213"): ein Wunsch, den das Modell
nicht kennt, und deshalb nichts, was verschwinden darf.

**Aktionen je Zeile**: „Bewerbung aktualisieren" (die Zeile ist bereits als Bewerbung vorhanden),
„Bewerbung anlegen" (bestehender Haushalt), „Haushalt neu anlegen" (samt Auswahl der vorhandenen
Personen ohne Haushalt) und „Überspringen".

**Erneuter Import derselben Liste** (`_find_existing_application`): Die Liste wird weiter außerhalb
gepflegt und wiederholt eingelesen. Eine Zeile gilt als bereits vorhanden, wenn es eine nicht
archivierte Bewerbung mit **gleichem Haushalt, gleicher Art und gleichem Zeitpunkt des Wunsches**
gibt (fehlt der Zeitpunkt auf beiden Seiten, gilt das ebenso). Der **Status** entscheidet dabei nur
als Feinheit: zuerst zählt die Bewerbung mit demselben Status, erst danach dieselbe Kennung mit
abweichendem Status — sonst gälte eine Zeile, die in der Liste von „offen" auf „erfüllt" gewandert
ist, als neue Bewerbung. Greift das alles nicht, wird auf die offene Bewerbung derselben Art
zurückgefallen (so findet die Zeile auch die Bewerbung, die der Haushaltsbogen angelegt hat). Würde
nur eine *offene* Bewerbung als vorhanden gelten, erzeugte jeder erneute Import für jede erfüllte
oder zurückgezogene Zeile eine Dublette.

**Eine vorhandene Bewerbung gehört zu höchstens einer Zeile** (`claimed`): Zwei gleichartige Zeilen
desselben Haushalts **ohne** Datum würden sonst dieselbe Bewerbung überschreiben und sich
gegenseitig auslöschen; die zweite Zeile wird stattdessen zu einer zweiten Bewerbung — was sie ja
auch ist. Belegt wird nur, was ohne Rückfrage aktualisiert wird: eine Zeile mit unsicherem Treffer
entscheidet ein Mensch und nimmt der nächsten Zeile nichts vorweg. Zwei Zeilen desselben Haushalts
mit **unterschiedlichem** Datum bleiben ohnehin zwei Bewerbungen — die Liste führt Wechselwünsche
über die Jahre.

#### vCard-Import (Mitgliederliste, .vcf)

Der vCard-Import ist der **erste Schritt der Importkette** und legt den Personen- und Haushaltsbestand an. Quelle ist der Adressbuch-Export der Genossenschaft (vCard 3.0/4.0).

**Feld-Mapping pro Kontakt:**

| vCard-Feld | Ziel | Bemerkung |
|------------|------|-----------|
| `X-WEILERID` | `Person.member_number` | Mitgliedsnummer, primäres Match-Kriterium |
| `N` (bzw. `FN`) | `Person.first_name` / `last_name` | strukturierter Name hat Vorrang |
| `BDAY` | `Person.birth_date` | Format `YYYYMMDD` oder `YYYY-MM-DD` |
| `GENDER` / `X-GENDER` | `Person.gender` | `M`→`m`, `F`→`f`, `O`/`N`→`d` |
| `ADR` Komponente 2 (Extended Address) | `Household.apartment_unit` | z. B. `W.002`, `P.108.1`; gesetzt ⇒ `is_resident=True` |
| `NOTE` „Aufnahmegespräch am TT.MM.JJJJ" | `Person.member_since` | Beginn der Mitgliedschaft |
| `X-ANNIVERSARY` / `X-ABDATE` (Label „Anniversary"/„Jahrestag") | `Person.member_since` | Fallback, wenn kein Aufnahmegespräch in der Notiz steht; Label „Todestag" wird ignoriert |
| `REV` | `Household.vcf_import_timestamp`, `Person.vcf_import_timestamp` | Idempotenz: gleicher Zeitstempel ⇒ „bereits importiert" |

**Anlegen von Personen:**

- Der Import legt **alle** in der Datei enthaltenen Personen an, sofern keine passende Person im System gefunden wird — unabhängig davon, ob eine Wohnungszuordnung vorliegt.
- Dazu zählen auch die aus dem Notizfeld gelesenen **Kinder** (Name + Geburtsdatum) und **Partner\*innen ohne eigene Karte**.
- Gefundene Personen werden mit den vCard-Daten **überschrieben**; **leere vCard-Werte überschreiben nichts** (Geburtsdatum, Geschlecht, Mitgliedsnummer, Mitglied seit). Felder, die die vCard nicht kennt (Haupttätigkeit, Bildungsabschluss, …), bleiben unangetastet.
- Personen werden über `PersonIndex` wiedergefunden: innerhalb eines zugeordneten Haushalts unscharf (Mitgliedsnummer → Name → Nachname + Geburtsdatum, inkl. Rufname), über den gesamten Bestand hinweg dagegen nur bei **eindeutigen** Treffern (Mitgliedsnummer oder ein Name, den genau eine Person trägt, ohne widersprechendes Geburtsdatum). Ein mehrdeutiger Name führt zu einer neuen Person, damit nicht zwei verschiedene Menschen verschmolzen werden.

**Haushaltsbildung:**

- Ein Haushalt entsteht **nur bei erkannter Wohnungszuordnung** — oder wenn im Assistenten ausdrücklich ein bestehender Haushalt zugeordnet wurde. **Für alle übrigen Personen wird kein Haushalt angelegt**: sie bleiben ohne Zuordnung und sind im Personen-Tab über den Filter „Nur ohne Haushalt" erreichbar (`persons_without_household` in der Import-Zusammenfassung).
- **Primär über die Wohnungsnummer**: Alle Personen mit identischer Wohnungsnummer bilden genau einen Haushalt und werden als aktuelle Bewohner geführt. Cluster-Zimmer (`P.108.1`, `P.108.2`, …) sind eigene Haushalte.
- **Sekundär über Partnerbeziehungen** aus dem Notizfeld (`Partner:`, `Partnerin:`, `Mann von`, `Frau von`, `gehört zu`), aber nur zwischen Personen **ohne** Wohnungsnummer, damit die Wohnungszuordnung nicht überschrieben wird. Aus dieser Gruppierung entsteht kein Haushalt; sie hält die Personen im Assistenten lediglich zusammen.
- **Elternbeziehungen** (`Tochter von X`, `Sohn von X`) werden bewusst **nicht** zum Gruppieren genutzt — erwachsene Kinder mit eigener Familie würden sonst mit dem Elternhaushalt verschmolzen. Sie können im Import-Assistenten manuell zugeordnet werden.
- Aus dem Notizfeld gelesene **Kinder** (`Kind: Name (TT.MM.JJJJ)`, `Kinder:`-Blöcke, `Tochter: Name TT.MM.JJJJ`) und **Partner\*innen ohne eigene Karte** werden als zusätzliche Personen ohne Mitgliedsnummer angelegt. Nennen beide Partner\*innen dasselbe Kind, wird über Vorname + Geburtsdatum entdoppelt.
- `Household.household_member_count` = Anzahl der übernommenen Personen (Mitglieder + Partner\*innen + Kinder).

**Ablauf und Sicherheitsnetz:**

- Zweistufig wie die Fragebogen-Importe: `analyze` liefert eine Vorschau mit Match-Vorschlag, `commit` schreibt die bestätigten Entscheidungen.
- Da das Notizfeld Freitext ist, sind daraus abgeleitete Personen **Schätzungen**. Im Assistenten lässt sich jede Person einzeln abwählen (`excluded_person_temp_ids`).
- Der Import **löscht nie** Personen. Personen, die nur in der Datenbank existieren, bleiben erhalten und werden in der Vorschau ausgewiesen.
- Leere vCard-Werte überschreiben keine vorhandenen Daten.
- Im Assistenten steht je Gruppe „Haushalt neu anlegen" bzw. — ohne Wohnungsnummer — „Nur Personen anlegen", „Aktualisieren" (bestehender Haushalt) und „Überspringen" zur Wahl. „Überspringen" verwirft die Gruppe vollständig, es werden dann auch keine Personen angelegt.
- Zeigen mehrere Import-Haushalte auf denselben bestehenden Haushalt, wird das als Warnung angezeigt.
- Der Score wird **nicht** automatisch neu berechnet.

---

## Grundsätze zur Vergabe (Quelle: Beschluss GV 23.06.2018, letzte Änderung 29.06.2019)

Die folgenden Grundsätze bilden die fachliche Basis des Scoring-Systems. Sie sind bei jeder Erweiterung oder Anpassung der Anwendung zu berücksichtigen.

### Voraussetzungen (§2 Abs. 1–3)

- Vergabe nur an **Mitglieder** der Genossenschaft, die nutzungsbezogene Anteile gezahlt haben (oder Solidaritätsanteile nutzen).
- **Wohnungsgröße muss zur Haushaltsgröße passen** (Zimmeranzahl vs. Personenzahl gemäß Satzung §4 Abs. 1).
- **Öffentlich geförderter Wohnraum** (WBS A / WBS B) darf nur an Personen mit entsprechender Berechtigung (Wohnberechtigungsschein) vergeben werden.

### Vorrangregeln (§2 Abs. 4–5, §3 Abs. 4)

Folgende Vorrangregeln greifen **vor** dem Scoring-Ranking:

1. **Interne Umzüge wegen Unterbelegung** (gemäß Satzung) haben höchsten Vorrang.
2. **Interne Umzüge wegen Familienzuwachs** (minderjährige Kinder) haben Vorrang.
3. **Interner Wohnungswechsel** (gewünschter Wechsel der Wohnform) hat Vorrang vor externen Bewerbungen, solange andere Grundsätze nicht entgegenstehen.
4. **Mieter\*innen von Gewerberäumen** der Grüner Weiler eG haben bei der Vergabe von Wohnraum Vorrang.
5. **Erstbezug**: Mitglieder, die sich an den Planungskosten beteiligt haben, werden beim Erstbezug vorrangig berücksichtigt (kein Anspruch auf bestimmte Wohnung).

### Vergabekriterien / Scoring (§3)

#### Durchmischung (§3 Abs. 1)
Die soziale Durchmischung orientiert sich an der Bevölkerungsstruktur Münsters. Folgende Dimensionen werden abhängig von der aktuellen Belegung flexibel gewichtet:
- a) Ausgewogene **Altersstruktur**
- b) Ausgewogenes **Geschlechterverhältnis**
- c) **Kulturelle Vielfalt**
- d) Vielfalt bezüglich **beruflicher und nichtberuflicher Tätigkeiten**
- e) Vielfalt der **Bildungsabschlüsse**
- f) Einbeziehung von Menschen in **besonderen Lebenslagen oder schwierigen finanziellen Situationen**

#### Ausnutzung (§3 Abs. 2)
Größere Haushaltsgröße wird bevorzugt. Auch der **beabsichtigte Zuwachs durch minderjährige Kinder** wird berücksichtigt.

#### Dauer der Mitgliedschaft (§3 Abs. 3)
Längere Mitgliedschaft = mehr Punkte.

#### Engagement für die Genossenschaft (§3 Abs. 5)
- a) Ehemalige Vorstands-, Aufsichtsrats- oder Belegungskommissionsmitglieder (≥ 1 Jahr) werden beim **ersten Einzug** bevorzugt.
- b) Regelmäßig aktive Mitglieder **können** bevorzugt werden.
- c) Mitglieder, die die Entwicklung **maßgeblich gefördert** haben, können bevorzugt werden.

### Sonderregeln

#### Nachzug (§2 Abs. 6)
Nachzüge in bestehende Haushalte können genehmigt werden, sofern andere Vergabegrundsätze nicht entgegenstehen. Ein Anspruch auf eine größere Wohnung entsteht dadurch **nicht**.

#### Haustiere (§2 Abs. 7)
Bei Bewerbungen mit Haustieren (Hunde, Katzen, Exoten) gilt das Haustierreglement der Genossenschaft. Kein direkter Scoring-Einfluss, aber ggf. Ausschlusskriterium.

#### Vermeidung von Notlagen (§3 Abs. 6)
Belegungskommission und Vorstand können im Einzelfall aus wichtigem Grund von den Vergabegrundsätzen abweichen (manuelle Entscheidung, kein Scoring-Einfluss).

#### Gemeinschaftswohnformen (§4 Abs. 1)
Bei WGs entscheiden Mitbewohner\*innen gemeinsam mit der Belegungskommission über den Belegungsvorschlag. Die übrigen Vergabegrundsätze sind zu berücksichtigen.

#### Pflege-WG (§4 Abs. 2)
Vergabe durch Vorstand. Sonderregeln: Pflegebedarf, Finanzierung, Vorrang für bestehende Bewohner\*innen, dann Angehörige, dann Quartier.

---

## Technische Anforderungen

### Stack

| Schicht | Technologie |
|---------|-------------|
| Backend | Python, FastAPI, SQLAlchemy, Pandas |
| Frontend | React (TypeScript), Vite, Material UI (inkl. MUI X Data Grid und MUI X Charts) |
| Datenbank | SQLite (Dev), PostgreSQL (Prod) |
| Auth | Einfaches Passwort (Env-Variable `APP_PASSWORD`, Default: `geheim`) |

### API-Endpunkte

| Methode | Pfad | Beschreibung | Auth |
|---------|------|--------------|------|
| POST | `/token` | Login (Passwort prüfen, Token zurückgeben) | – |
| GET | `/households/` | Alle Haushalte mit Personen & Score | Auth |
| POST | `/households/` | Haushalt anlegen | Auth |
| PUT | `/households/{id}` | Haushalt bearbeiten (u. a. Haushaltsname; leerer Name → HTTP 400) | Auth |
| DELETE | `/households/{id}` | Haushalt löschen (kaskadiert Personen, Bewerbungen; löst Wohnungszuordnung) | Auth |
| GET | `/apartments/` | Alle Wohnungen inkl. Name des zugeordneten Haushalts | Auth |
| POST | `/apartments/` | Wohnung anlegen | Auth |
| PUT | `/apartments/{id}` | Wohnung bearbeiten | Auth |
| DELETE | `/apartments/{id}` | Wohnung löschen (inkl. Bewerbungen darauf) | Auth |
| POST | `/apartments/{id}/assign/{household_id}` | Wohnung dem Haushalt zuordnen, der darin wohnt | Auth |
| DELETE | `/apartments/{id}/assign` | Zuordnung lösen (Wohnung bleibt bestehen) | Auth |
| GET | `/applications/` | Bewerbungen, optional gefiltert nach `kind`, `status`, `household_id`, `include_archived` | Auth |
| POST | `/applications/` | Bewerbung anlegen (409 bei zweiter offener Bewerbung derselben Art) | Auth |
| PUT | `/applications/{id}` | Bewerbung bearbeiten (Wunsch, Status, Datum, Kennzeichen, Kommentar) | Auth |
| DELETE | `/applications/{id}` | Bewerbung endgültig löschen | Auth |
| PATCH | `/applications/{id}/archive` | Bewerbung archivieren/wiederherstellen | Auth |
| GET | `/applications/joker` | Joker-Warteliste, nach dem Zeitpunkt des Wunsches gereiht | Auth |
| GET | `/apartments/categories` | Wählbare Wunschkategorien, abgeleitet aus den Wohnungsstammdaten | Auth |
| GET | `/ranking/` | Gruppiertes Ranking je (Größe, Förderungsart). `priority` enthält die Wechselwünsche dieser Kategorie (nach Datum), `households` die Wartepool-Rangliste (nach Gesamt-Score) mit `base_score`, `occupancy_score`, `total_score` sowie `by_wish_only`, `special_case` und `special_case_note` | Auth |
| PATCH | `/households/{id}/archive` | Haushalt archivieren/wiederherstellen (inkl. Personen) | Auth |
| POST | `/people/` | Person eigenständig anlegen (ohne Haushalt) | Auth |
| DELETE | `/people/{id}` | Person löschen (nur ohne Haushaltszuordnung; 409 wenn zugeordnet) | Auth |
| DELETE | `/people/unassigned` | Alle Personen ohne Haushaltszuordnung löschen (`include_archived` optional) | Auth |
| GET | `/people/` | Alle Personen inkl. Name des zugeordneten Haushalts | Auth |
| GET | `/people/unassigned` | Personen ohne Haushaltszuordnung | Auth |
| PUT | `/people/{id}` | Person bearbeiten | Auth |
| POST | `/people/{id}/assign/{household_id}` | Person einem Haushalt zuordnen | Auth |
| DELETE | `/people/{id}/assign` | Person aus ihrem Haushalt entfernen (Person bleibt bestehen) | Auth |
| PATCH | `/people/{id}/archive` | Person archivieren/wiederherstellen | Auth |
| POST | `/upload/households/` | Excel-Import | Auth |
| POST | `/import/applications/analyze` | Bewerbungsliste analysieren, Vorschau + Match-Vorschläge | Auth |
| POST | `/import/applications/commit` | Bestätigte Entscheidungen der Bewerbungsliste übernehmen | Auth |
| POST | `/import/vcf/analyze` | vCard-Datei analysieren, Vorschau + Match-Vorschläge | Auth |
| POST | `/import/vcf/commit` | Bestätigte vCard-Entscheidungen übernehmen | Auth |
| POST | `/scoring/calculate` | Scoring neu berechnen | Auth |
| GET | `/statistics/residents` | Ist-Statistik der aktuellen Bewohner: je Merkmal absolute Zahlen, Anteile und Zielwerte (Datensätze ohne Angabe ignoriert, Anzahl in `unknown_count`) | Auth |
| GET | `/statistics/residents/missing` | Prüfliste: Bewohner-Personen ohne Angabe zu mindestens einem Merkmal, je Merkmal mit Grund, Rohwert und Verdacht auf Importfehler | Auth |
| GET | `/scoring/config` | Gewichte & Zielwerte lesen | Auth |
| PUT | `/scoring/config` | Gewichte & Zielwerte ändern | Auth |

### Authentifizierung

- Einfaches Passwort-Login (kein SSO, keine Rollen, keine Nutzerverwaltung).
- Das Passwort wird über die Umgebungsvariable `APP_PASSWORD` gesetzt (Default: `geheim`).
- Alle Endpunkte außer `/token` erfordern ein gültiges Bearer-Token.
- Ohne Anmeldung sind keine Inhalte erreichbar.

### Datenmodell (Übersicht)

```
Household (1) ──< Person (N)
Household (1) ──< Application (N)        # Bewerbungen; Wunsch als Kategorien, nicht als Wohnung
Application (N) ──> Apartment (0..1)     # erfüllte Bewerbung: "neue Wohnung"
Household (0..1) ──── Apartment (0..1)   # Ist-Belegung: Haushalt wohnt in Wohnung
ScoringConfig: Key-Value-Paare für Gewichte und Zielwerte
```

`Application`: `kind` (`wartepool` | `wechselwunsch` | `joker`), `requested_at`, `wishes` (JSON),
`status` (`offen` | `erfuellt` | `zurueckgezogen`), `status_note`, `special_case`,
`special_case_note`, `note`, `fulfilled_apartment_id`, `fulfilled_at`, `created_at`,
`updated_at`, `archived`.

### Frontend-Anforderungen

- **Ranking-Tab**: Über der Rangliste steht der Block **„Vorrang — Wechselwunsch"** mit den Spalten Rang, Haushaltsname, Mitglieder, Aktuelle Wohnung und Wunsch seit — gereiht nach dem Zeitpunkt des Wunsches, ohne Punkte. Darunter die **Wartepool**-Rangliste mit zwei Dropdown-Filtern (Wohnungsgröße und Förderungsart) und den Spalten Rang, Haushaltsname, Mitglieder, **Grundpunktzahl**, **Wohnraumausnutzung** und **Gesamtpunktzahl**. Haushalte, die nur über ihren ausdrücklichen Wunsch in der Kategorie stehen, tragen den Chip **„nur auf Wunsch"**; Bewerbungen mit gesetztem Sonderfall-Kennzeichen ein Warnzeichen mit der Begründung als Tooltip. Beide Filter stehen **standardmäßig auf „Alle“** und schränken dann nicht ein: die Rangliste zeigt zunächst **alle nicht archivierten Haushalte mit offener Wartepool-Bewerbung, die keine Wohnung bewohnen** — auch solche, die für keine Wohnungskategorie in Frage kommen. Ohne offene Bewerbung erscheint ein Haushalt in keiner Rangliste. **Bestehende Bewohner (`is_resident=True`) erscheinen nie in der Rangliste**: sie suchen keine Wohnung und dienen nur als Referenzdaten der Durchmischung. Wird die Wohnungszuordnung eines Haushalts gelöst, taucht er wieder in der Rangliste auf. Ohne Filter gibt es keine Zimmerzahl und damit keine Wohnraumausnutzung: die Spalte zeigt „—“, die Gesamtpunktzahl entspricht der Grundpunktzahl. Wird ein Filter gesetzt, zeigt die Tabelle die Haushalte, die für die passenden Kategorien in Frage kommen; da derselbe Haushalt je Kategorie einen anderen Score hat, wird beim Entdoppeln über die Haushalts-id die **Kategorie mit dem höchsten Gesamtscore** behalten. Der **Rang wird immer für die aktuelle Auswahl neu vergeben** (1, 2, 3, …).
- **Bewerbungen-Tab**: Tabelle aller Bewerbungen mit Freitextsuche (Haushalt, Wunsch, Kommentar, Sonderfall-Begründung, aktuelle Wohnung) und den Filtern „Typ" und „Status" (Standard: „offen"). Spalten: Haushalt (Link in den Haushaltsdetail-Dialog, mit Sonderfall-Warnzeichen), Typ, Wunsch (Chips), Wunsch seit, Status, Kommentar sowie Bearbeiten und Löschen. **Aktuelle und neue Wohnung sind keine Spalten**: die aktuelle Wohnung steht am Haushalt (ein Klick auf den Namen), die neue entsteht beim Einzug von selbst. Beides bleibt als Daten erhalten — die aktuelle Wohnung wird weiterhin von der Freitextsuche erfasst. Rechtsbündig „Bewerbung anlegen". Unter der Tabelle die **Joker-Warteliste**, nach dem Zeitpunkt des Wunsches gereiht. Im **Bearbeiten-Dialog** wird der Wunsch ausschließlich über eine **Mehrfachauswahl aus den vorhandenen Wohnungskategorien** gepflegt (kein Freitextfeld); beim Anlegen sind Bewerbungsart (Bewohner → Wechselwunsch, sonst Wartepool) und Datum vorbelegt. Das Löschen wird bestätigt und weist darauf hin, dass der Status „zurückgezogen" die Bewerbung als Historie erhält.
- **Haushalte-Tab**: Der Haushalts-Score wird hier **nicht** angezeigt: die Grundpunktzahl allein ist ohne die Wohnraumausnutzung der jeweiligen Wohnungsgröße nicht aussagekräftig; Punktzahlen und Ränge stehen deshalb ausschließlich in der Rangliste. Tabelle aller Haushalte mit Freitextsuche (Haushaltsname, Wohnungsnummer, WBS-Status und Namen der Haushaltsmitglieder) sowie den Filtern „Nur ohne Wohnung“ und „Archivierte anzeigen“. Der Button „Haushalt anlegen“ steht — wie im Wohnungen-Tab — rechtsbündig in der Filterzeile. Über der Tabelle wird die Zahl der sichtbaren von allen Haushalten angezeigt. Standardsortierung ist der Haushaltsname (aufsteigend). Ein Klick auf eine Zeile öffnet den Haushaltsdetail-Dialog.
- **Personen-Tab**: Tabelle aller Personen mit Suche, Sortierung und den Filtern „Nur ohne Haushalt" und „Archivierte anzeigen". Pro Zeile: Haushalt zuordnen (bei Personen ohne Haushalt), aus Haushalt entfernen (bei zugeordneten Personen), Archivieren/Wiederherstellen sowie Löschen (nur bei Personen ohne Haushalt). Über der Tabelle steht zusätzlich „Alle ohne Haushalt löschen (N)"; die Aktion wird mit Anzahl bestätigt und löscht — je nach Schalter „Archivierte anzeigen" — auch archivierte Personen ohne Haushalt.
- **Haushaltsdetail-Dialog**: Zeigt Haushaltsdaten (einschließlich zugeordnete Wohnung, sofern vorhanden), einen Abschnitt **„Bewerbungen"** und Personenkarten. Die Felder „Gewünschte Wohnungsgröße" und „Wohnungsart" gibt es hier nicht mehr — der Wunsch wird in der Bewerbung gepflegt. Der Abschnitt „Bewerbungen" listet alle Bewerbungen des Haushalts (Typ, Status, Wunsch-Chips, Sonderfall-Warnzeichen, Datum, erfüllte Wohnung) und erlaubt Anlegen und Bearbeiten, ohne den Dialog zu verlassen. Der Score erscheint als „Grundpunktzahl (ohne Wohnraumausnutzung)“. Der **Haushaltsname ist editierbar**: im Bearbeiten-Modus wird die Dialogüberschrift zum Eingabefeld „Haushaltsname“. Ein leerer Name wird abgelehnt (Speichern deaktiviert, Backend antwortet mit HTTP 400); führende und nachfolgende Leerzeichen werden entfernt. Der Bewohnerstatus (`is_resident`) wird als Nur-Lese-Feld angezeigt und ergibt sich implizit aus der Wohnungszuordnung. Erlaubt „Person hinzufügen" (Auswahl aus Personen ohne Haushalt) und das Entfernen einzelner Personen aus dem Haushalt.
- **Wohnungen-Tab**: Tabelle aller Wohnungen (Wohnungsnummer, Zimmer, Kennzeichen „klein", Wohnungsart, Förderungsart, qm mietwirksam, mind. Bewohner, bewohnt von) mit Suche über Wohnungsnummer, Wohnungsart und Haushalt, sortierbaren Spalten und den Filtern „Wohnungsart", „Förderungsart" und „Nur belegte". Pro Zeile: bearbeiten, Haushalt zuordnen bzw. Zuordnung lösen, Wohnung löschen. Über der Tabelle „Wohnung anlegen". Der zugeordnete Haushalt ist als Link in die Haushaltsdetailansicht ausgeführt. Im Bearbeiten-Dialog wird eine Zimmerzahl mit Nachkommastelle abgelehnt.
- **Import-Tab**: Vier Upload-Bereiche (vCard-Mitgliederliste, Individualbogen, Haushaltsbogen, Bewerbungsliste). Jeder öffnet einen Assistenten mit den Schritten Analyse → Zuordnung → Zusammenfassung. Im vCard-Assistenten ist jeder Haushalt aufklappbar; dort sind alle Personen mit Rolle (Mitglied/Partner*in/Kind) und Herkunft (Kontakt/Notiz) sichtbar und einzeln abwählbar. Der Bewerbungslisten-Assistent zeigt je Zeile die geparsten Wunsch-Chips, nicht erkannte Wunschangaben, Warnungen zu abweichenden oder unbekannten Wohnungsnummern sowie die Aktion; bei „Haushalt neu anlegen" zusätzlich Haushaltsname und die auswählbaren Personen ohne Haushalt. In **allen vier Assistenten** wird eine Zuordnung nur bei einem eindeutigen Treffer vorausgewählt (siehe „Zuordnungssicherheit"); nur ähnliche Treffer erscheinen als orangefarbener Chip mit dem Ähnlichkeitsgrad im Tooltip.
- **Ist-Statistik-Tab**: Auswertung der aktuellen Belegung. Kopfzeile mit der Zahl der Bewohner-Haushalte, der Personen und der Personen mit fehlenden Angaben (Button „Prüfen" öffnet die Prüfliste über alle Merkmale), darunter ein Umschalter „Absolute Zahlen" / „Relative Zahlen". Je Merkmal (Altersgruppen, Geschlecht, Haupttätigkeit, Bildungsabschluss, Haushaltsgröße) eine Tabelle mit den Spalten Ausprägung, Anzahl bzw. Anteil, Zielwert und Abweichung sowie einer Summenzeile. Als Bezugsgröße steht über der Tabelle die Zahl der Personen mit Angabe; darunter „N Personen ohne Angabe – nicht berücksichtigt" mit dem Button „Prüfen" (Prüfliste für dieses Merkmal). Unter der Tabelle der Altersgruppen steht zusätzlich „N Personen unter 20 – nicht berücksichtigt" (ohne „Prüfen", denn das ist keine fehlende Angabe). Merkmale ohne Zielwert zeigen nur Ausprägung und Wert. Bei allen Merkmalen mit Zielwert — **Altersgruppen, Geschlecht, Haupttätigkeit und Bildungsabschluss** — steht zwischen Bezugsgröße und Tabelle ein **waagerechtes Balkendiagramm** (MUI X Charts, `TargetDistributionChart`): je Ausprägung ein Balken für den Ist-Wert und eine senkrechte Marke für den Zielwert, darüber eine Legende „Ist" / „Zielwert". Das Diagramm folgt dem Umschalter (Anzahl bzw. Anteil in %); seine Form bleibt dabei gleich, weil der absolute Zielwert Zielanteil × Bezugsgröße ist. Lange Ausprägungen werden an der Achse gekürzt; der Tooltip nennt die vollständige Ausprägung, Ist, Ziel und Abweichung. Die Tabelle bleibt als vollständige Zahlenansicht erhalten. Ist die Bezugsgröße 0, entfällt das Diagramm.
- **Prüfliste (Dialog im Ist-Statistik-Tab)**: Tabelle mit Name, Mitgliedsnummer, Haushalt (Link in den Haushaltsdetail-Dialog), Wohnung, Alter, Datum des Individualbogen-Imports und der fehlenden Angabe samt Grund („leer", „leer trotz Individualbogen", „0 – keine Zuordnung", „„Wert" nicht erkannt"). Verdachtsfälle auf Importfehler stehen oben und sind orange markiert. Schalter „Nur Verdacht auf Importfehler" und „Personen unter 20 ausblenden" (Kinder haben meist legitim keinen Beruf und Bildungsabschluss). Nach dem Schließen des Haushaltsdetail-Dialogs werden Statistik und Prüfliste neu geladen.
- **Config-Tab**: Editierbare Karten für alle Gewichte und Zielwerte (nur für eingeloggte Admins sichtbar).
- **Tabellen**: Alle Datentabellen (Ranking, Bewerbungen, Haushalte, Personen, Wohnungen) zeigen standardmäßig **100 Zeilen pro Seite**; wählbar sind 10, 25, 50 und 100. Alle Tabellen sind **abwechselnd eingefärbt (Zebrastreifen)**: jede zweite Zeile erhält einen leicht abgesetzten Hintergrund. Die Streifen richten sich nach der Position in der aktuellen Seite und bleiben daher nach Sortieren, Filtern und Blättern korrekt; der Hover-Effekt bleibt auf allen Zeilen sichtbar. In den Tabellen der Ist-Statistik bleibt die Summenzeile ungestreift.
- **Kopfzeile (AppBar)**: Der Button „Punkte neu berechnen" steht in der Kopfzeile der Seite und ist damit aus jedem Tab erreichbar. Einen eigenen „Aktionen"-Tab gibt es nicht mehr; der frühere Alt-Upload „Excel-Daten hochladen" entfällt, Excel-Dateien werden ausschließlich über den Datenimport-Tab eingelesen.
- Login/Logout über AppBar.

---

## Konventionen

- Backend-Code in `backend/`, Frontend in `frontend/`, Tests in `tests/`.
- Import-Logik: Fragebögen in `backend/import_service.py`, vCard in `backend/vcf_import_service.py`, Bewerbungsliste in `backend/application_import_service.py` (beide nutzen Session-Store, Namensnormalisierung und Haushalts-Matching aus `import_service`).
- Wohnungswünsche: `backend/wishes.py` — Parsen, Anzeigen und Abgleichen der Wunschkategorien. Hängt bewusst nur an der Standardbibliothek und wird von Ranking, beiden Importen und der Startmigration benutzt. Das Frontend spiegelt die Anzeige in `frontend/src/components/applications/wishes.ts`.
- Wohnungsstammdaten: `backend/apartment_seed_data.py` (generiert aus `imported_data/Wohnungen.xlsx`), angelegt über `services.seed_apartments`; die Zuordnung zum Haushalt erfolgt über `services.assign_household`.
- Tests: `python tests/test_apartments.py` (Wohnungsstammdaten und Zuordnung), `python tests/test_ranking.py` (Eignung, Rangliste, Vorrang und Bewerbungspflicht), `python tests/test_applications.py` (Wunsch-Parser, Statusregeln, Auswahlkategorien), `python tests/test_application_import.py` (Bewerbungslisten-Import), `python tests/test_statistics.py` (Ist-Statistik der Bewohner und Prüfliste „ohne Angabe", u. a. mit den Beispieldaten und einem Individualbogen-Importfehler), `python tests/test_import_order.py` (Reihenfolge der Importe), `python tests/test_matching.py` (Zuordnungssicherheit der Importe), `python tests/test_vcf_import.py` (vCard-Import). Alle laufen ohne Server gegen eine In-Memory-Datenbank.
- Pydantic V2: `from_attributes = True` statt `orm_mode`.
- Relative Imports innerhalb des `backend`-Packages.
- `backend/__init__.py` muss vorhanden sein.
- Backend starten: `python -m uvicorn backend.main:app --reload` (aus Projekt-Root).
- Frontend starten: `npm run dev` (aus `frontend/`).
- Node.js-Pfad ggf. manuell setzen: `$env:Path += ";C:\Program Files\nodejs"`.

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
| **Wohnraumausnutzung** | Personen pro Wohnung | Mehr Personen = höheres Scoring. |
| **Mitgliedsdauer** | Jahre in Genossenschaft | Pro Person gespeichert (`member_since`). Für das Scoring wird das früheste Eintrittsdatum aller Personen im Haushalt herangezogen. Längere Dauer = mehr Punkte. |
| **Engagement** | Aktives Engagement im Projekt | Erfüllungsgrad 0–1. |

### Scoring-Berechnung

- Das Scoring wird **unabhängig von Wohnungsgröße und Wohnungsart** berechnet. Jeder Haushalt erhält genau einen Gesamt-Score, der ausschließlich auf seinen eigenen Eigenschaften basiert.
- Jedes Kriterium erhält ein **Gewicht** (editierbar über die UI).
- **Zielwert-Kriterien** (Alter, Geschlecht, Haupttätigkeit, Bildung): Punkte = f(Zielwert − IST-Wert) × Anzahl passender Personen im Haushalt.
- **Erfüllungsgrad-Kriterien** (kulturelle Vielfalt, besondere Lebenslagen, Engagement): Punkte = Erfüllungsgrad × Skalierungsfaktor.
- **Mitgliedsdauer**: Punkte = f(Jahre), gekappt bei Maximum.
- **Wohnraumausnutzung**: Punkte = f(Haushaltsgröße / Zimmerzahl der beantragten Wohnung).
- Gesamt-Score = Σ (Gewicht_i × Teilscore_i).

### Ranking

- Das **Ranking** (Rangvergabe) erfolgt **pro Wohnungskategorie** (Kombination aus Wohnungsgröße und Förderungsart), nicht über alle Haushalte hinweg.
- Innerhalb jeder Kategorie werden die Haushalte nach ihrem Gesamt-Score absteigend sortiert und erhalten einen Rang (1, 2, 3, …).
- Ein Haushalt **bewirbt sich nicht auf einzelne Wohnungen**: er erscheint automatisch in jeder Kategorie, für die er in Frage kommt, und damit in der Regel in mehreren Kategorien.

#### Wer kommt für eine Wohnung in Frage?

Ein Haushalt kommt für eine Wohnung in Frage, wenn **alle** drei Bedingungen erfüllt sind:

1. **Mindestbewohner**: Die Zahl der (nicht archivierten) Haushaltsmitglieder erreicht mindestens die `min_occupants` der Wohnung.
2. **Zimmerzahl**: Die Wohnung hat **nicht weniger Zimmer als der Haushalt Mitglieder** (`size_rooms >= Mitgliederzahl`). Wohnungen ohne Zimmerangabe (Cluster, Ausbau, Atelier, Joker) unterliegen dieser Schranke nicht.
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
- **Wohnungsart** (Mehrfachauswahl): „Standard Wohnungstypen", „Clusterwohnung", „Ausbauwohnung", „Atelierwohnung". Ein Haushalt kann sich auf mehrere Wohnungsarten gleichzeitig bewerben. Die Auswahl wird als Liste gespeichert (JSON-Array im Feld `desired_apartment_type`). „Gartencluster", „C-Riegel" und die Wohngemeinschaften (WPG) sind **keine** eigenen Wohnungsarten, sondern Clusterwohnungen. In den Wohnungsstammdaten kommt zusätzlich „Joker" vor; darauf bewerben sich Haushalte nicht.
- Wohngemeinschaften (WG) werden **nicht** vergeben.
- Haushalte bewerben sich **nicht** auf konkrete Wohnungen; sie werden automatisch in allen Kategorien geführt, für die sie in Frage kommen (siehe „Ranking").
- **Gruppiertes Ranking**: Haushalte werden **nicht** über alle Haushalte hinweg gerankt, sondern **pro Wohnungskategorie** (Kombination aus Wohnungsgröße und Förderungsart). Beispiel: Alle Haushalte, die für „3 Zimmer / WBS A" in Frage kommen, erhalten einen eigenen Rang innerhalb dieser Gruppe. Wohnungen ohne Zimmerangabe (Cluster, Ausbau, Atelier, Joker) bilden eine eigene Gruppe „ohne Zimmerangabe".

### Wohnungsstammdaten

Die konkreten Wohnungen der Genossenschaft (136 Einheiten) sind als Stammdaten in der Anwendung hinterlegt. Sie werden **nicht** über einen Import eingelesen: die Daten liegen in `backend/apartment_seed_data.py` und werden beim Start der Anwendung angelegt (`services.seed_apartments`). Der Seed ist **idempotent und additiv** — Wohnungen, deren `unit_number` bereits existiert, bleiben unverändert; im Frontend vorgenommene Änderungen werden also nie überschrieben. Gepflegt werden die Daten anschließend ausschließlich im Frontend (Tab „Wohnungen": anlegen, bearbeiten, löschen).

Quelle der Stammdaten ist `imported_data/Wohnungen.xlsx`.

Die Spalte `Etage` aus der Quelldatei wird bewusst **nicht** übernommen; der Rohwert der Spalte `Typ` wird ebenfalls nicht gespeichert, weil er vollständig in Zimmerzahl, Wohnungsart und `is_small` aufgeht.

| Feld | Quelle (Spalte) | Bemerkung |
|------|-----------------|-----------|
| `unit_number` | `Wohnung` | z. B. `P.101`, `W.008.1`; eindeutig, entspricht der Wohnungsnummer aus dem vCard-Import |
| `size_rooms` | abgeleitet aus `Typ` | ganze Zahl 1–5; das halbe Zimmer entfällt (`3.5` → `3`). Leer bei Wohnungen ohne Zimmerangabe (Cluster, Ausbau, Atelier, Joker) |
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
- Die Zuordnung erfolgt **manuell im Tab „Wohnungen"** oder **automatisch durch den vCard-Import** (wenn die Wohnungsnummer einer existierenden Wohnung entspricht). Beim Anlegen der Beispieldaten werden die Bewohner-Haushalte anhand ihrer `apartment_unit` automatisch mit der passenden Wohnung verknüpft.
- Das **Lösen** einer Zuordnung ist kein Löschen: Wohnung und Haushalt bleiben unverändert erhalten.
- Das **Löschen** einer Wohnung entfernt auch die Bewerbungen auf diese Wohnung.

### Ist-Belegung (aktuelle Bewohner)

- Haushalte mit dem Flag `is_resident=True` stellen die aktuelle Belegung der Genossenschaft dar.
- Aus allen Bewohner-Haushalten wird die **IST-Verteilung** (Alter, Geschlecht etc.) aggregiert.
- Die Abweichung der IST-Verteilung von der Soll-Verteilung bestimmt, wie viele Punkte ein Bewerber-Haushalt für Durchmischung erhält.
- Beim Scoring werden nur Nicht-Bewohner-Haushalte bewertet; Bewohner dienen ausschließlich als Referenzdaten.
- Der **vCard-Import** verknüpft Haushalte mit einer Wohnungsnummer automatisch mit der entsprechenden Wohnung (`services.assign_household`), sofern diese in den Stammdaten existiert. Die Wohnungsnummer wird zusätzlich in `Household.apartment_unit` gespeichert.

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
- **Wohnung löschen** (`DELETE /apartments/{id}`): Nur möglich, wenn **kein Haushalt** der Wohnung zugeordnet ist (`household_id IS NULL`). Andernfalls wird HTTP 409 zurückgegeben. Zuordnung muss zuerst gelöst werden. Bewerbungen auf die Wohnung werden mitgelöscht.
- Im Frontend wird der Löschen-Button für Personen nur bei Personen ohne Haushalt angezeigt. Bei Wohnungen wird die Fehlermeldung des Backends angezeigt.

### Zuordnung von Personen zu Haushalten

- Eine Person kann **keinem oder genau einem** Haushalt zugeordnet sein (`Person.household_id` ist optional).
- Personen **ohne Zuordnung** entstehen z. B. beim Einzelpersonen-Import ohne erkannten Haushalt oder nachdem sie aus einem Haushalt entfernt wurden. Sie sind im Personen-Tab über den Filter „Nur ohne Haushalt" auffindbar.
- Eine Person **ohne Haushalt kann einem bestehenden Haushalt zugeordnet** werden — entweder aus dem Personen-Tab heraus (Haushalt auswählen) oder aus der Haushaltsdetailansicht heraus („Person hinzufügen", Auswahl aus den Personen ohne Zuordnung).
- Eine Person kann **aus ihrem Haushalt entfernt** werden. Das ist kein Löschen: Die Person bleibt mit allen Daten erhalten und ist danach ohne Haushaltszuordnung. Beide Aktionen werden vor der Ausführung bestätigt.
- Jede Zuordnungsänderung setzt `Person.updated_at`.
- Zuordnungsänderungen verändern die Haushaltsgröße und damit das Scoring. Der Score wird **nicht automatisch** neu berechnet; dies erfolgt weiterhin über „Score berechnen".

### Datenimport

- Haushalts- und Personendaten werden per **Excel-Upload** (.xlsx) importiert.
- Erwartete Spalten: `Household Name`, `Member Since`, `Engagement Score`, `First Name`, `Last Name`, `Birth Date`, `Gender`, `Occupation`, `Education`, `Cultural Background`, `Special Needs`. `Member Since` wird pro Person gespeichert (bei altem Format ohne personenbezogenes Datum wird der Wert der ersten Zeile für alle Personen des Haushalts übernommen).
- Mehrere Zeilen mit gleichem `Household Name` werden zu einem Haushalt gruppiert.

#### vCard-Import (Mitgliederliste, .vcf)

Zusätzlich zu den Fragebögen können Mitgliedsdaten aus dem Adressbuch-Export der Genossenschaft (vCard 3.0/4.0) importiert werden. Der Import aktualisiert sowohl Personen- als auch Haushaltsdaten.

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

**Haushaltsbildung:**

- **Primär über die Wohnungsnummer**: Alle Personen mit identischer Wohnungsnummer bilden genau einen Haushalt und werden als aktuelle Bewohner geführt. Cluster-Zimmer (`P.108.1`, `P.108.2`, …) sind eigene Haushalte.
- **Sekundär über Partnerbeziehungen** aus dem Notizfeld (`Partner:`, `Partnerin:`, `Mann von`, `Frau von`, `gehört zu`), aber nur zwischen Personen **ohne** Wohnungsnummer, damit die Wohnungszuordnung nicht überschrieben wird.
- **Elternbeziehungen** (`Tochter von X`, `Sohn von X`) werden bewusst **nicht** zum Gruppieren genutzt — erwachsene Kinder mit eigener Familie würden sonst mit dem Elternhaushalt verschmolzen. Sie können im Import-Assistenten manuell zugeordnet werden.
- Aus dem Notizfeld gelesene **Kinder** (`Kind: Name (TT.MM.JJJJ)`, `Kinder:`-Blöcke, `Tochter: Name TT.MM.JJJJ`) und **Partner\*innen ohne eigene Karte** werden als zusätzliche Personen ohne Mitgliedsnummer angelegt. Nennen beide Partner\*innen dasselbe Kind, wird über Vorname + Geburtsdatum entdoppelt.
- `Household.household_member_count` = Anzahl der übernommenen Personen (Mitglieder + Partner\*innen + Kinder).

**Ablauf und Sicherheitsnetz:**

- Zweistufig wie die Fragebogen-Importe: `analyze` liefert eine Vorschau mit Match-Vorschlag, `commit` schreibt die bestätigten Entscheidungen.
- Da das Notizfeld Freitext ist, sind daraus abgeleitete Personen **Schätzungen**. Im Assistenten lässt sich jede Person einzeln abwählen (`excluded_person_temp_ids`).
- Der Import **löscht nie** Personen. Personen, die nur in der Datenbank existieren, bleiben erhalten und werden in der Vorschau ausgewiesen.
- Leere vCard-Werte überschreiben keine vorhandenen Daten.
- **Primärzweck ist die Ergänzung fehlender Daten** bei vorhandenen Einträgen. Neue Haushalte und Personen werden **nur** angelegt, wenn sie eine Wohnungsnummer besitzen (= bereits eine Wohnung bewohnen). Haushalte ohne Wohnungsnummer, die keinem bestehenden Haushalt zugeordnet werden können, werden übersprungen.
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
| Frontend | React (TypeScript), Vite, Material UI |
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
| GET | `/applications/` | Alle Bewerbungen | Auth |
| POST | `/applications/` | Bewerbung anlegen (Haushalt → Wohnung) | Auth |
| GET | `/ranking/` | Gruppiertes Ranking: alle geeigneten Haushalte pro (Größe, Förderungsart), nach Score sortiert | Auth |
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
| POST | `/import/vcf/analyze` | vCard-Datei analysieren, Vorschau + Match-Vorschläge | Auth |
| POST | `/import/vcf/commit` | Bestätigte vCard-Entscheidungen übernehmen | Auth |
| POST | `/scoring/calculate` | Scoring neu berechnen | Auth |
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
Household (N) ──< Application (N) >── Apartment (1)
Household (0..1) ──── Apartment (0..1)   # Ist-Belegung: Haushalt wohnt in Wohnung
ScoringConfig: Key-Value-Paare für Gewichte und Zielwerte
```

### Frontend-Anforderungen

- **Ranking-Tab**: Rangliste mit zwei Dropdown-Filtern (Wohnungsgröße und Förderungsart). Beide Filter stehen **standardmäßig auf „Alle“** und schränken dann nicht ein: die Rangliste zeigt zunächst **alle nicht archivierten Haushalte**, nach Score sortiert — auch solche, die für keine Wohnungskategorie in Frage kommen. Wird ein Filter gesetzt, zeigt die Tabelle die Haushalte, die für die passenden Kategorien in Frage kommen (bei mehreren Kategorien über die Haushalts-id entdoppelt). Der **Rang wird immer für die aktuelle Auswahl neu vergeben** (1, 2, 3, …).
- **Haushalte-Tab**: Tabelle aller Haushalte mit Freitextsuche (Haushaltsname, Wohnungsnummer, WBS-Status und Namen der Haushaltsmitglieder) sowie den Filtern „Nur ohne Wohnung“ und „Archivierte anzeigen“. Der Button „Haushalt anlegen“ steht — wie im Wohnungen-Tab — rechtsbündig in der Filterzeile. Über der Tabelle wird die Zahl der sichtbaren von allen Haushalten angezeigt. Ein Klick auf eine Zeile öffnet den Haushaltsdetail-Dialog.
- **Personen-Tab**: Tabelle aller Personen mit Suche, Sortierung und den Filtern „Nur ohne Haushalt" und „Archivierte anzeigen". Pro Zeile: Haushalt zuordnen (bei Personen ohne Haushalt), aus Haushalt entfernen (bei zugeordneten Personen), Archivieren/Wiederherstellen sowie Löschen (nur bei Personen ohne Haushalt). Über der Tabelle steht zusätzlich „Alle ohne Haushalt löschen (N)"; die Aktion wird mit Anzahl bestätigt und löscht — je nach Schalter „Archivierte anzeigen" — auch archivierte Personen ohne Haushalt.
- **Haushaltsdetail-Dialog**: Zeigt Haushaltsdaten (einschließlich zugeordnete Wohnung, sofern vorhanden) und Personenkarten. Der **Haushaltsname ist editierbar**: im Bearbeiten-Modus wird die Dialogüberschrift zum Eingabefeld „Haushaltsname“. Ein leerer Name wird abgelehnt (Speichern deaktiviert, Backend antwortet mit HTTP 400); führende und nachfolgende Leerzeichen werden entfernt. Der Bewohnerstatus (`is_resident`) wird als Nur-Lese-Feld angezeigt und ergibt sich implizit aus der Wohnungszuordnung. Erlaubt „Person hinzufügen" (Auswahl aus Personen ohne Haushalt) und das Entfernen einzelner Personen aus dem Haushalt.
- **Wohnungen-Tab**: Tabelle aller Wohnungen (Wohnungsnummer, Zimmer, Kennzeichen „klein", Wohnungsart, Förderungsart, qm mietwirksam, mind. Bewohner, bewohnt von) mit Suche über Wohnungsnummer, Wohnungsart und Haushalt, sortierbaren Spalten und den Filtern „Wohnungsart", „Förderungsart" und „Nur belegte". Pro Zeile: bearbeiten, Haushalt zuordnen bzw. Zuordnung lösen, Wohnung löschen. Über der Tabelle „Wohnung anlegen". Der zugeordnete Haushalt ist als Link in die Haushaltsdetailansicht ausgeführt. Im Bearbeiten-Dialog wird eine Zimmerzahl mit Nachkommastelle abgelehnt.
- **Import-Tab**: Drei Upload-Bereiche (Haushaltsbogen, Individualbogen, vCard-Mitgliederliste). Jeder öffnet einen Assistenten mit den Schritten Analyse → Zuordnung → Zusammenfassung. Im vCard-Assistenten ist jeder Haushalt aufklappbar; dort sind alle Personen mit Rolle (Mitglied/Partner*in/Kind) und Herkunft (Kontakt/Notiz) sichtbar und einzeln abwählbar.
- **Config-Tab**: Editierbare Karten für alle Gewichte und Zielwerte (nur für eingeloggte Admins sichtbar).
- **Actions-Tab**: Buttons für „Score berechnen" und „Excel hochladen" (nur Admin).
- **Tabellen**: Alle Datentabellen (Ranking, Haushalte, Personen, Wohnungen) zeigen standardmäßig **100 Zeilen pro Seite**; wählbar sind 10, 25, 50 und 100.
- Login/Logout über AppBar.

---

## Konventionen

- Backend-Code in `backend/`, Frontend in `frontend/`, Tests in `tests/`.
- Import-Logik: Fragebögen in `backend/import_service.py`, vCard in `backend/vcf_import_service.py` (nutzt Session-Store, Namensnormalisierung und Haushalts-Matching aus `import_service`).
- Wohnungsstammdaten: `backend/apartment_seed_data.py` (generiert aus `imported_data/Wohnungen.xlsx`), angelegt über `services.seed_apartments`; die Zuordnung zum Haushalt erfolgt über `services.assign_household`.
- Tests: `python tests/test_apartments.py` (Wohnungsstammdaten und Zuordnung), `python tests/test_ranking.py` (Eignung und Rangliste), `python tests/test_vcf_import.py` (vCard-Import). Alle laufen ohne Server gegen eine In-Memory-Datenbank.
- Pydantic V2: `from_attributes = True` statt `orm_mode`.
- Relative Imports innerhalb des `backend`-Packages.
- `backend/__init__.py` muss vorhanden sein.
- Backend starten: `python -m uvicorn backend.main:app --reload` (aus Projekt-Root).
- Frontend starten: `npm run dev` (aus `frontend/`).
- Node.js-Pfad ggf. manuell setzen: `$env:Path += ";C:\Program Files\nodejs"`.

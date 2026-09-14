# Benutzerhandbuch: GW Haushalts-Scoring

Hier steht, wie du mit der Anwendung arbeitest. Du findest diese Anleitung auch direkt in der
Anwendung: Das Hilfe-Symbol **?** oben rechts öffnet sie – gleich an der Stelle, die zu deinem
aktuellen Tab passt.

---

## 1. Wozu die Anwendung dient

Die Anwendung hilft uns als Belegungskommission, freie Wohnungen zu vergeben. Sie

- verwaltet Haushalte, Personen, Wohnungen und Bewerbungen,
- berechnet für jeden Haushalt, der sich bewirbt, Punkte nach unseren Vergabegrundsätzen
  (Beschluss der Generalversammlung vom 23.06.2018, zuletzt geändert am 29.06.2019),
- macht daraus eine **Rangliste je Wohnungskategorie** (Zimmerzahl + Förderungsart).

Die Rangliste ist eine **Entscheidungshilfe** – entscheiden tun wir. Wenn wir im Einzelfall von
der Regel abweichen, halten wir das an der Bewerbung als Sonderfall fest.

**Anmeldung:** mit unserem gemeinsamen Passwort. Ohne Anmeldung siehst du nichts.

---

## 2. Die Tabs im Überblick

| Tab | Wofür |
|-----|-------|
| **Rangliste** | Wechselwünsche (Vorrang) und Wartepool-Rangliste je Kategorie; Punkte prüfen und vergleichen |
| **Bewerbungen** | Bewerbungen anlegen, bearbeiten, Status pflegen; darunter die Joker-Warteliste |
| **Alle Haushalte** | Haushalte suchen und im Detail-Dialog bearbeiten |
| **Personen** | Personen suchen, Haushalten zuordnen oder aus ihnen entfernen |
| **Wohnungen** | Wohnungsdaten pflegen, Haushalte einer Wohnung zuordnen |
| **Ist-Statistik** | Wie setzen sich die aktuellen Bewohner zusammen – verglichen mit den Zielwerten; Prüfliste fehlender Angaben |
| **Bewertungskonfiguration** | Gewichte, Zielwerte und „Maximale Mitgliedsjahre“ einstellen |
| **Datenimport** | vCard, Individualbogen, Haushaltsbogen und Bewerbungsliste einlesen |

Den Button **„Punkte neu berechnen“** findest du oben in der Kopfzeile – er ist aus jedem Tab
erreichbar.

---

## 3. Daten einlesen

Die vier Importe bauen aufeinander auf. **Halte die Reihenfolge ein:**

1. **vCard-Mitgliederliste** (.vcf) – legt die Personen an; Haushalte nur für Personen mit
   Wohnungsnummer.
2. **Individualbogen** (.xlsx) – ergänzt Geschlecht, Tätigkeit, Bildung usw. bei den vorhandenen
   Personen.
3. **Haushaltsbogen** (.xlsx) – ergänzt WBS-Status, Haustiere usw. bei den vorhandenen Haushalten
   und überträgt den Wohnungswunsch in die Wartepool-Bewerbung.
4. **Bewerbungsliste** (.xlsx) – legt Bewerbungen an, wenn nötig auch neue Haushalte.

Jeder Import führt dich durch einen Assistenten: **Analyse → Zuordnung → Zusammenfassung**.
Gespeichert wird erst, wenn du den letzten Schritt bestätigst – vorher kannst du also nichts
kaputt machen.

**Darauf solltest du achten:**

- Automatisch zugeordnet wird nur ein **eindeutiger Treffer** (gleiche Mitgliedsnummer oder
  genau gleicher Name). Ist ein Treffer nur *ähnlich*, siehst du einen **orangefarbenen Chip**;
  klickst du darauf, wird er übernommen.
- Bei vCard und Bewerbungsliste stehen unsichere Zeilen auf **„Bitte entscheiden“**. Du kannst
  den Import erst abschließen, wenn alle entschieden sind – einzeln oder mit „Alle neu anlegen“ /
  „Alle überspringen“.
- Im vCard-Assistenten kannst du Kinder und Partner\*innen, die aus dem Notizfeld erkannt wurden,
  einzeln abwählen, falls dabei etwas schiefgegangen ist.
- Die Importe **löschen nie** etwas, und leere Werte überschreiben keine vorhandenen Angaben.
- Wunschangaben aus der Bewerbungsliste, die nicht erkannt wurden, zeigt dir der Assistent je
  Zeile an. Schau sie dir an und trag sie bei Bedarf in der Bewerbung nach.
- **Klick nach dem Import auf „Punkte neu berechnen“.**

---

## 4. Eine Vergabe durchführen

### Schritt 1: Punkte aktualisieren
Klick in der Kopfzeile auf **„Punkte neu berechnen“**. Siehst du in der Rangliste ein
**Uhr-Symbol**, haben sich seit der letzten Berechnung Daten geändert.

### Schritt 2: Kategorie wählen
Grenz im Tab **Rangliste** die freie Wohnung über die Filter **Wohnungsgröße** und
**Förderungsart** ein. Dann siehst du:

- oben den Block **„Vorrang – Wechselwunsch“**: Haushalte, die schon bei uns wohnen und in diese
  Kategorie wechseln möchten – gereiht nach dem Datum ihres Wunsches (ohne Punkte),
- darunter die **Wartepool-Rangliste**, sortiert nach Gesamtpunktzahl.

Was die Symbole in der Rangliste bedeuten:

| Symbol | Bedeutung |
|--------|-----------|
| Chip **„nur auf Wunsch“** | Der Haushalt wünscht sich diese Kategorie ausdrücklich, erfüllt laut Daten aber nicht alle Voraussetzungen (z. B. zu wenige Mitglieder). Schau genauer hin. |
| **Warnzeichen** | Die Bewerbung ist als Sonderfall markiert; die Begründung siehst du, wenn du mit der Maus darüber fährst. |
| **Uhr** | Die Punktzahl ist veraltet – einmal neu berechnen. |
| **Info-Symbol** | öffnet die Aufschlüsselung der Punkte dieses Haushalts. |

Ohne Filter gibt es keine Zimmerzahl; in der Spalte „Wohnraumausnutzung“ steht dann „—“.

### Schritt 3: Punkte nachvollziehen
Über das **Info-Symbol** siehst du je Kriterium Wert, Gewicht und Punkte. Klickst du auf ein
Kriterium, klappt der Rechenweg mit den echten Zahlen auf. Mit „Als Excel exportieren“ bekommst
du eine Datei, in der du jede Punktzahl als Formel nachrechnen kannst.

### Schritt 4: Spitzen-Haushalte vergleichen
Liegen Haushalte dicht beieinander, markier bis zu 5 davon per Kästchen und klick auf
**„Vergleichen“**. Dort kannst du die Kriterien, die wir von Hand bewerten – **Engagement**,
**Kulturelle Vielfalt** und **Besondere Lebenslagen** (jeweils 0–1) –, per Regler durchspielen:

- Geänderte Werte sind gelb markiert, darunter siehst du, wie sich die Gesamtpunktzahl verändert.
- Der Pfeil beim Rang zeigt, ob sich die Reihenfolge verschiebt.
- **Gespeichert wird nichts**, solange du nicht auf **„Werte übernehmen“** klickst. Dann werden die
  Werte am Haushalt gespeichert und alle Punkte neu berechnet.
- „Zurücksetzen“ verwirft deine Simulation; „Als Excel exportieren“ nimmt die simulierten Werte mit.

### Schritt 5: Wohnung zuordnen
Ordne im Tab **Wohnungen** die Wohnung dem Haushalt zu, für den ihr euch entschieden habt. Damit

- gilt der Haushalt als Bewohner und verschwindet aus der Rangliste,
- werden seine offenen Bewerbungen automatisch auf **„erfüllt“** gesetzt,
- zählt er ab der nächsten Berechnung zur Ist-Verteilung der Bewohner.

---

## 5. So entstehen die Punkte

Jeder Haushalt hat **eine Grundpunktzahl**. Dazu kommen **je Wohnungsgröße** Punkte für die
Wohnraumausnutzung:

**Gesamtpunktzahl = Grundpunktzahl + Wohnraumausnutzung**

Jedes Kriterium ergibt einen Wert. Der wird mit seinem **Gewicht** aus der
Bewertungskonfiguration multipliziert.

| Kriterium | Wie der Wert entsteht |
|-----------|-----------------------|
| **Alter, Geschlecht, Haupttätigkeit, Bildungsabschluss** | Je Person: Ist eine Gruppe unter den Bewohnern schwächer vertreten als ihr Zielwert, gibt es Punkte – umso mehr, je größer die Lücke. Fehlt die Gruppe ganz, gibt es 1 Punkt pro Person. Alle Personen im Haushalt zählen einzeln. |
| **Mitgliedsdauer** | Je Person anteilig bis zu den „Maximalen Mitgliedsjahren“ (Standard 10): 5 von 10 Jahren = 0,5. Die Werte aller Personen werden addiert. |
| **Engagement, Kulturelle Vielfalt, Besondere Lebenslagen** | Bewerten wir von Hand mit 0–1 im Detail-Dialog des Haushalts. |
| **Wohnraumausnutzung** | 1, wenn der Haushalt mindestens so viele Mitglieder hat, wie die Wohnung Zimmer hat; sonst 0. |

**Ein Beispiel** (Gewichte ausgedacht): Ein Paar, 34 und 36 Jahre alt, seit 5 Jahren Mitglied.
Für die Altersgruppe 30–39 liegt der Zielwert bei 15 %, unter den Bewohnern sind es 10 %.

- Alter: je Person (15 − 10) / 15 = 0,33 → zusammen 0,67; × Gewicht 2 = **1,33**
- Mitgliedsdauer: je Person 5 / 10 = 0,5 → zusammen 1,0; × Gewicht 1 = **1,00**
- Wohnraumausnutzung für eine 2-Zimmer-Wohnung: 2 Mitglieder ≥ 2 Zimmer → 1; × Gewicht 1 = **1,00**
- Für eine 3-Zimmer-Wohnung dagegen: 2 < 3 → **0**

Derselbe Haushalt hat also bei „2 Zimmer“ mehr Punkte als bei „3 Zimmer“.

**Wer steht in welcher Rangliste?** Ein Haushalt mit offener Wartepool-Bewerbung taucht in jeder
Kategorie auf, für die er in Frage kommt. Das heißt:

1. genug Mitglieder für die Mindestbelegung der Wohnung,
2. nicht mehr Mitglieder als Zimmer,
3. passender WBS: Mit WBS A geht WBS A, WBS B und freifinanziert; mit WBS B geht WBS B und
   freifinanziert; ohne WBS nur freifinanziert.

Außerdem taucht er in jeder Kategorie auf, die er sich ausdrücklich wünscht („nur auf Wunsch“).
Clusterwohnungen und Joker-Zimmer vergeben wir **nicht** über Punkte.

---

## 6. Bewerbungen pflegen

- Es gibt drei Arten: **Wartepool** (wohnt noch nicht bei uns, Vergabe nach Punkten),
  **Wechselwunsch** (wohnt schon bei uns, Vorrang nach Datum) und **Joker** (eigene Warteliste).
- Den **Wunsch** wählst du aus den Wohnungskategorien aus, die es tatsächlich gibt; mehrere
  Wünsche sind möglich.
- Pro Haushalt und Art kann es nur **eine offene** Bewerbung geben.
- Gilt eine Bewerbung nicht mehr, setz den Status lieber auf **„zurückgezogen“**, statt sie zu
  löschen – so können wir später noch sehen, dass es sie gab.
- **Sonderfall**: Setz das Kennzeichen und schreib eine Begründung dazu, wenn wir im Einzelfall
  von der Regel abweichen. Die Begründung erscheint dann als Warnzeichen in der Rangliste.

---

## 7. Datenqualität prüfen

Im Tab **Ist-Statistik** siehst du, wie sich die Bewohner auf Altersgruppen, Geschlecht,
Tätigkeit, Bildung und Haushaltsgröße verteilen – als Anzahl oder in Prozent, jeweils mit
Zielwert. Genau diese Zahlen sind die Grundlage für die Durchmischungspunkte.

Wer zu einem Merkmal **keine Angabe** hat, wird dort nicht mitgezählt. Über **„Prüfen“** öffnest
du die Liste dieser Personen. **Orange markiert** sind Fälle, bei denen vermutlich beim Import
etwas schiefgegangen ist – etwa eine Antwort aus dem Individualbogen, die nicht erkannt wurde.
Klickst du auf den Haushalt, kannst du die Angaben direkt im Detail-Dialog korrigieren. Denk danach
an „Punkte neu berechnen“.

---

## 8. Häufige Fragen

**Ein Haushalt fehlt in der Rangliste – warum?**
Mögliche Gründe: Er hat keine offene Bewerbung · er ist schon einer Wohnung zugeordnet (wohnt also
bei uns) · er ist archiviert · er kommt für die gefilterte Kategorie nicht in Frage (Mitglieder,
Zimmer, WBS) · es ist ein Wechselwunsch – der steht oben im Vorrang-Block.

**Ich habe Daten geändert, aber die Punkte sind gleich geblieben.**
Punkte werden nicht automatisch neu berechnet. Klick in der Kopfzeile auf „Punkte neu berechnen“.

**Warum hat ein Haushalt je nach Kategorie unterschiedliche Punkte?**
Wegen der Wohnraumausnutzung – die hängt von der Zimmerzahl ab (siehe Abschnitt 5).

**Warum zeigt der Tab „Alle Haushalte“ keine Punkte?**
Die Grundpunktzahl allein sagt ohne Wohnungsgröße wenig aus. Punkte findest du deshalb nur in der
Rangliste.

**Was ist der Unterschied zwischen Archivieren und Löschen?**
Archivieren blendet Haushalte oder Personen aus, und du kannst es rückgängig machen; archivierte
Einträge zählen nicht für Punkte und Rangliste. Löschen ist endgültig – wenn du einen Haushalt
löschst, sind auch seine Personen und Bewerbungen weg.

**Was bedeutet „Zuordnung lösen“ bei einer Wohnung?**
Der Haushalt wohnt nicht mehr dort. Wohnung und Haushalt bleiben erhalten; hat der Haushalt eine
offene Bewerbung, taucht er wieder in der Rangliste auf.

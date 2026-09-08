# -*- coding: utf-8 -*-
"""Tests für den vCard-Import (ohne Datenbank).

Aufruf aus dem Projekt-Root:  python tests/test_vcf_import.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import vcf_import_service as V

SAMPLE = """BEGIN:VCARD
VERSION:3.0
PRODID:-//Sabre//Sabre VObject 4.5.6//EN
UID:00000000-aaaa-bbbb-cccc-000000000001
CATEGORIES:-C- Mitglieder,Mailingliste - mitglieder,Mailingliste - newslett
 er
FN:Jannis Dreyer
N:Dreyer;Jannis;;;
BDAY:19870911
GENDER:M
EMAIL;TYPE=HOME:jannis.dreyer@example.org
TEL;TYPE=CELL:+49 171 3920012
ADR;TYPE=HOME:;W.202;Edith-Miltenberg-Weg 2;Münster;;48161;Deutschland
NOTE:Infoveranstaltung am 11.03.2023 [XY]\\nAufnahmegespräch am 11.03.2023
 [XY]\\n\\nPartnerin: Svenja Dreyer\\nKinder: Jakob Finn Dreyer (14.03.2021)
 \\, Anton Bo Dreyer (09.10.2023)
REV;VALUE=DATE-TIME:20260123T210829Z
X-WEILERID:907
END:VCARD

BEGIN:VCARD
VERSION:3.0
UID:11111111-2222-3333-4444-555555555555
FN:Svenja Dreyer
N:Dreyer;Svenja;;;
BDAY:19880101
GENDER:F
ADR;TYPE=HOME:;W.202;Edith-Miltenberg-Weg 2;Münster;;48161;Deutschland
NOTE:Aufnahmegespräch am 25.03.2023\\n\\nPartner: Jannis Dreyer\\nKinder: Jakob Finn Dreyer (14.03.2021)\\, Anton Bo Dreyer (09.10.2023)
REV;VALUE=DATE-TIME:20260123T210830Z
X-WEILERID:908
END:VCARD

BEGIN:VCARD
VERSION:3.0
UID:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
FN:Nina Beispiel
N:Beispiel;Nina;;;
BDAY:19910824
ADR;TYPE=HOME:;;Beispielweg 1;Münster;;48147;Deutschland
NOTE:Tochter von Helga Beispiel\\nsie zog aus\\n\\n01.12.2018 Infoveranstaltung\\n01.12.2018 Aufnahmegespräch
ITEM1.X-ABDATE;VALUE=DATE-AND-OR-TIME:20181207
ITEM1.X-ABLABEL:_$!<Anniversary>!$_
REV;VALUE=DATE-TIME:20260101T120000Z
X-WEILERID:900
END:VCARD

BEGIN:VCARD
VERSION:3.0
UID:ffffffff-0000-1111-2222-333333333333
FN:Olaf Ohnedatum
N:Ohnedatum;Olaf;;;
NOTE:Zwillinge Karl und Emil\\, 2 Jahre jung
ITEM1.X-ABDATE;VALUE=DATE-AND-OR-TIME:20200101
ITEM1.X-ABLABEL:Todestag
REV;VALUE=DATE-TIME:20260101T120000Z
X-WEILERID:901
END:VCARD
"""

FAILURES = []


def check(condition, message):
    if condition:
        print("  ok   " + message)
    else:
        print("  FAIL " + message)
        FAILURES.append(message)


def check_equal(actual, expected, message):
    check(actual == expected, "%s (erwartet %r, war %r)" % (message, expected, actual))


def test_low_level_parsing():
    print("vCard-Grundlagen")
    cards = V.parse_vcards(SAMPLE)
    check_equal(len(cards), 4, "vier Karten erkannt")

    person = V.parse_vcard_person(cards[0])
    check_equal(person["first_name"], "Jannis", "Vorname aus N")
    check_equal(person["last_name"], "Dreyer", "Nachname aus N")
    check_equal(person["member_number"], "907", "Mitgliedsnummer aus X-WEILERID")
    check_equal(person["birth_date"], "1987-09-11", "Geburtsdatum aus BDAY")
    check_equal(person["gender"], "m", "Geschlecht aus GENDER")
    check_equal(person["apartment_unit"], "W.202", "Wohnungsnummer aus ADR")
    check(person["is_resident"], "mit Wohnungsnummer = aktueller Bewohner")
    check_equal(person["member_since"], "2023-03-11", "Mitglied seit = Aufnahmegespräch")
    check_equal(person["rev"].isoformat(), "2026-01-23T21:08:29", "REV als Zeitstempel")
    # Zeilenfaltung (RFC 6350): die Kategorie steht ueber zwei Zeilen verteilt
    check("Mailingliste - newsletter" in person["categories"], "gefaltete Zeile zusammengesetzt")


def test_note_extraction():
    print("NOTE-Auswertung")
    cards = V.parse_vcards(SAMPLE)
    jannis = V.parse_vcard_person(cards[0])

    check_equal(jannis["partner_names"], ["Svenja Dreyer"], "Partnerin erkannt")
    check_equal(
        [(c["first_name"], c["last_name"], c["birth_date"]) for c in jannis["children"]],
        [("Jakob Finn", "Dreyer", "2021-03-14"), ("Anton Bo", "Dreyer", "2023-10-09")],
        "zwei Kinder mit Geburtsdatum",
    )

    nina = V.parse_vcard_person(cards[2])
    check_equal(nina["parent_names"], ["Helga Beispiel"], "Elternteil erkannt")
    check_equal(nina["children"], [], "'Tochter von X' erzeugt kein Kind")
    check_equal(nina["member_since"], "2018-12-01", "Datum vor dem Stichwort erkannt")

    olaf = V.parse_vcard_person(cards[3])
    check_equal(
        sorted(c["first_name"] for c in olaf["children"]), ["Emil", "Karl"],
        "Zwillinge ohne Datum erkannt, '2 Jahre jung' verworfen",
    )
    check_equal(olaf["member_since"], None, "Label 'Todestag' wird nicht als Beitritt gewertet")


def test_household_building():
    print("Haushaltsbildung")
    parsed = V.parse_vcf(SAMPLE.encode("utf-8"))
    check_equal(len(parsed["persons"]), 4, "vier Personen geparst")

    by_unit = {h["apartment_unit"]: h for h in parsed["households"]}
    dreyer = by_unit.get("W.202")
    check(dreyer is not None, "Haushalt über Wohnungsnummer gebildet")
    if dreyer:
        check_equal(dreyer["name"], "Dreyer", "Haushaltsname aus Nachnamen")
        check(dreyer["is_resident"], "Haushalt ist Bewohner-Haushalt")
        check_equal(len(dreyer["persons"]), 4, "2 Mitglieder + 2 Kinder = 4 Personen")
        check_equal(
            sorted(p["role"] for p in dreyer["persons"]),
            ["child", "child", "member", "member"],
            "Rollen korrekt vergeben",
        )
        check_equal(
            sorted(p["name"] for p in dreyer["persons"] if p["role"] == "child"),
            ["Anton Bo Dreyer", "Jakob Finn Dreyer"],
            "von beiden Partnern genannte Kinder nur einmal angelegt",
        )
        check_equal(dreyer["rev"].isoformat(), "2026-01-23T21:08:30", "jüngste REV des Haushalts")

    nina = next(h for h in parsed["households"] if h["name"] == "Nina Beispiel")
    check(not nina["is_resident"], "ohne Wohnungsnummer kein Bewohner")
    check_equal(len(nina["persons"]), 1, "Elternbeziehung führt zu keiner Zusammenlegung")


def test_helpers():
    print("Hilfsfunktionen")
    check_equal(V.split_first_last("Maja Van Daal"), ("Maja", "Van Daal"),
                "Namenspartikel gehört zum Nachnamen")
    check_equal(V.parse_german_date("30.11. 19"), __import__("datetime").date(2019, 11, 30),
                "Datum mit Leerzeichen und zweistelligem Jahr")
    check_equal(V.parse_vcf_gender("O"), "d", "GENDER O = divers")
    check_equal(V.extract_member_since("Info + Aufnahmegespräch am 14.01.2023"),
                __import__("datetime").date(2023, 1, 14), "Aufnahmegespräch mit Präfix")


def run_tests():
    print("--- vCard-Import Tests ---")
    for test in (test_low_level_parsing, test_note_extraction,
                 test_household_building, test_helpers):
        test()
    print()
    if FAILURES:
        print("%d Prüfung(en) fehlgeschlagen." % len(FAILURES))
        return 1
    print("Alle Prüfungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())

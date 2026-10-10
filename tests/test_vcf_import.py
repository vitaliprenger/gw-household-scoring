# -*- coding: utf-8 -*-
"""Tests für den Parser der Mitgliederliste (vCard, ohne Datenbank).

Was die Mitgliederliste im Datenbestand bewirkt, steht in ``test_member_list.py``.

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
    check_equal(person["member_since"], "2023-03-11", "Mitglied seit = Aufnahmegespräch")
    # Zeilenfaltung (RFC 6350): die Kategorie steht ueber zwei Zeilen verteilt
    categories = next(prop.value for _group, prop in cards[0] if prop.name == "CATEGORIES")
    check("Mailingliste - newsletter" in categories, "gefaltete Zeile zusammengesetzt")


def test_member_since():
    print("Eintrittsdatum aus Notizfeld und Jahrestag")
    cards = V.parse_vcards(SAMPLE)

    nina = V.parse_vcard_person(cards[2])
    check_equal(nina["member_since"], "2018-12-01", "Datum vor dem Stichwort erkannt")

    olaf = V.parse_vcard_person(cards[3])
    check_equal(olaf["member_since"], None, "Label 'Todestag' wird nicht als Beitritt gewertet")


def test_one_person_per_card():
    print("Je Karte eine Person")
    parsed = V.parse_vcf(SAMPLE.encode("utf-8"))
    check_equal(parsed["total_cards"], 4, "vier Karten gezählt")
    check_equal(
        sorted(p["name"] for p in parsed["persons"]),
        sorted(prop.value for card in V.parse_vcards(SAMPLE)
               for _group, prop in card if prop.name == "FN"),
        "genau die Personen der Karten, niemand aus den Notizen",
    )


def test_helpers():
    print("Hilfsfunktionen")
    check_equal(V.parse_german_date("30.11. 19"), __import__("datetime").date(2019, 11, 30),
                "Datum mit Leerzeichen und zweistelligem Jahr")
    check_equal(V.parse_vcf_gender("O"), "d", "GENDER O = divers")
    check_equal(V.extract_member_since("Info + Aufnahmegespräch am 14.01.2023"),
                __import__("datetime").date(2023, 1, 14), "Aufnahmegespräch mit Präfix")


def run_tests():
    print("--- vCard-Import Tests ---")
    for test in (test_low_level_parsing, test_member_since,
                 test_one_person_per_card, test_helpers):
        test()
    print()
    if FAILURES:
        print("%d Prüfung(en) fehlgeschlagen." % len(FAILURES))
        return 1
    print("Alle Prüfungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())

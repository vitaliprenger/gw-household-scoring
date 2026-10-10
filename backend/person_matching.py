"""Sichere Personentreffer für die Importe.

Eine Importzeile wird nur dann automatisch einer Person zugeordnet, wenn die
Treffer-Art eindeutig ist (ADR 0007): gleiche Mitgliedsnummer oder gleicher
Name. Was hier als gleich gilt, steht in ADR 0011.
"""

import re
from datetime import date, datetime
from typing import Optional

#: Treffer-Arten, wie sie ``schemas.CERTAIN_MATCH_TYPES`` kennt.
MEMBER_NUMBER = "exact_member_nr"
SAME_NAME = "exact_name_dob"
#: Die Mitgliedsnummer passt, der sichere Treffer aber nicht: nur ein Vorschlag.
MEMBER_NUMBER_UNCONFIRMED = "member_nr_unconfirmed"


def normalize_member_number(raw) -> Optional[str]:
    """Mitgliedsnummer in kanonischer Form: mindestens dreistellig mit fuehrenden Nullen.

    Die Quellen schreiben Nummern mal mit, mal ohne fuehrende Nullen
    ("3" / "003", "20" / "020"); die vCard nutzt die dreistellige Form.
    Laengere Nummern bleiben unveraendert ("1234").
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    digits = re.findall(r"\d+", s)
    if digits:
        return f"{int(digits[0]):03d}"
    return None


def same_member_number(a, b) -> bool:
    """True, wenn beide Werte dieselbe Mitgliedsnummer bezeichnen (3 == 003).

    Normalisiert beide Seiten, damit auch vor der Vereinheitlichung
    gespeicherte Nummern ohne fuehrende Nullen wiedergefunden werden.
    """
    na = normalize_member_number(a)
    return na is not None and na == normalize_member_number(b)


def persons_with_member_number(people, member_number) -> list:
    """Alle Personen aus ``people``, die diese Mitgliedsnummer tragen."""
    return [p for p in people if same_member_number(p.member_number, member_number)]


def other_member_number_holder(people, member_number, person):
    """Wer außer ``person`` die Mitgliedsnummer schon trägt, sonst None.

    Kein Import speichert eine Nummer ein zweites Mal (ADR 0011): Sie wäre
    danach für beide Personen kein sicherer Treffer mehr.
    """
    others = (p for p in persons_with_member_number(people, member_number) if p is not person)
    return next(others, None)


def find_person_by_member_number(people, member_number):
    """Erste Person aus ``people`` mit derselben Mitgliedsnummer, sonst None."""
    return next(iter(persons_with_member_number(people, member_number)), None)


NAME_PARTICLES = {"von", "van", "de", "der", "dem", "den", "zu", "zum", "la", "le", "di", "da"}


def name_parts(first_name, last_name) -> frozenset[str]:
    """Bestandteile eines Namens, unabhängig von Reihenfolge und Aufteilung.

    Die Fragebögen schreiben Namen uneinheitlich ("Anna Maria Berger",
    "Berger, Anna Maria"), und ohne Komma rät der Parser, was Vor- und was
    Nachname ist. Verglichen wird deshalb die Menge der Bestandteile.
    """
    full = f"{first_name or ''} {last_name or ''}".lower()
    return frozenset(part for part in re.split(r"[\s,]+", full) if part)


def _as_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def birth_dates_conflict(a, b) -> bool:
    """Zwei bekannte, verschiedene Geburtsdaten; ein fehlendes widerspricht nicht."""
    first, second = _as_date(a), _as_date(b)
    return first is not None and second is not None and first != second


def find_certain_person(people, data: dict):
    """Sucht zu einem Import-Datensatz die sicher passende Person in ``people``.

    Gibt ``(person, treffer_art)`` zurück, ohne sicheren Treffer ``(None, None)``.
    """
    parts = name_parts(data.get("first_name"), data.get("last_name"))
    same_name = [p for p in people if parts and name_parts(p.first_name, p.last_name) == parts]

    # Mitgliedsnummern in den Fragebögen sind Selbstauskunft und manchmal
    # falsch; ohne gemeinsamen Namensbestandteil träfe ein Zahlendreher einen
    # fremden Menschen, ohne Blick aufs Geburtsdatum ein Kind den Elternteil,
    # dessen Nummer es eingetragen hat. Trägt eine andere Person genau den
    # Namen der Zeile, spricht der Name gegen die Nummer.
    holders = persons_with_member_number(people, data.get("member_number"))
    if (
        len(holders) == 1
        and (parts & name_parts(holders[0].first_name, holders[0].last_name)) - NAME_PARTICLES
        and not birth_dates_conflict(data.get("birth_date"), holders[0].birth_date)
        and (not same_name or holders[0] in same_name)
    ):
        return holders[0], MEMBER_NUMBER

    # Über den gesamten Bestand sind Namen nicht eindeutig; ein mehrdeutiger
    # Treffer würde zwei verschiedene Menschen verschmelzen.
    if len(same_name) != 1:
        return None, None
    if birth_dates_conflict(data.get("birth_date"), same_name[0].birth_date):
        return None, None
    return same_name[0], SAME_NAME

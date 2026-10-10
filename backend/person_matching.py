"""Sichere Personentreffer für die Importe.

Eine Importzeile wird nur dann automatisch einer Person zugeordnet, wenn die
Treffer-Art eindeutig ist (ADR 0007): gleiche Mitgliedsnummer oder gleicher
Name. Was hier als gleich gilt, steht in ADR 0011.
"""

import re
from dataclasses import dataclass, field
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


def _number_confirms(person, data: dict, parts: frozenset[str]) -> bool:
    """Die Mitgliedsnummer der Zeile gehört ``person``, und Name und Geburtsdatum passen."""
    return bool(
        same_member_number(person.member_number, data.get("member_number"))
        and (parts & name_parts(person.first_name, person.last_name)) - NAME_PARTICLES
        and not birth_dates_conflict(data.get("birth_date"), person.birth_date)
    )


def _same_name(person, data: dict) -> bool:
    parts = name_parts(data.get("first_name"), data.get("last_name"))
    return bool(parts) and name_parts(person.first_name, person.last_name) == parts


def _same_call_name(person, data: dict) -> bool:
    """Gleicher Rufname (erster Vorname) und gleicher Nachname."""
    last_name = (data.get("last_name") or "").strip().lower()
    call_name = (data.get("first_name") or "").strip().lower().split(" ")[0]
    return bool(
        last_name and call_name
        and (person.last_name or "").strip().lower() == last_name
        and (person.first_name or "").strip().lower().split(" ")[0] == call_name
    )


def match_household_persons(people, rows: list[dict]) -> list:
    """Ordnet den Zeilen eines Haushaltsbogens die Personen seines Haushalts zu.

    Gibt je Zeile die gemeinte Person zurück oder None. Jede Person nimmt
    höchstens eine Zeile auf, und jede Regel zählt nur, wenn genau eine noch
    freie Person passt und sich die Geburtsdaten nicht widersprechen.

    Die Regeln laufen nacheinander über den ganzen Bogen: erst der gleiche
    Name, dann die Mitgliedsnummer, dann der Rufname mit gleichem Nachnamen
    ("Jonas Sommer" für "Jonas Emil Sommer"). So nimmt der Elternteil seine
    eigene Zeile auf, bevor die Zeile eines Kindes mit seiner Nummer ihn
    trifft. Gleicher Nachname mit gleichem Geburtsdatum ist bewusst kein
    Treffer: Er verschmilzt Zwillinge (ADR 0011).
    """
    free = list(people)
    matched: list = [None] * len(rows)

    rules = (
        _same_name,
        lambda person, data: _number_confirms(
            person, data, name_parts(data.get("first_name"), data.get("last_name"))),
        _same_call_name,
    )
    for rule in rules:
        for index, data in enumerate(rows):
            if matched[index] is not None:
                continue
            hits = [
                person for person in free
                if rule(person, data)
                and not birth_dates_conflict(data.get("birth_date"), person.birth_date)
            ]
            if len(hits) == 1:
                matched[index] = hits[0]
                free.remove(hits[0])
    return matched


#: Was mit der Person einer Zeile des Haushaltsbogens geschieht.
IN_HOUSEHOLD = "in_household"        # steht schon im Haushalt
ASSIGN = "assign"                    # steht ohne Haushalt im Datenbestand, wird zugeordnet
OTHER_HOUSEHOLD = "other_household"  # steht in einem anderen Haushalt, bleibt dort
NEW = "new"                          # wird neu angelegt

#: Warum eine Person des Datenbestands einer neuen ähnlich ist.
SIMILAR_BY_MEMBER_NUMBER = "member_number"  # trägt die Nummer, aber Name oder Geburtsdatum passen nicht
SIMILAR_BY_NAME = "same_name"                # mehrere Personen tragen den Namen
SIMILAR_BY_BIRTH_DATE = "birth_date"         # gleiches Geburtsdatum, gemeinsamer Namensbestandteil


@dataclass
class RowResolution:
    """Ergebnis der Suche für eine Zeile des Haushaltsbogens."""
    status: str
    #: Gefundene Person; None, wenn die Person neu angelegt wird
    person: object = None
    #: Nur bei ``NEW``: ``(grund, person)`` für jede ähnliche Person
    similar: list = field(default_factory=list)
    #: Wer die Mitgliedsnummer der Zeile schon trägt, sodass sie nicht
    #: gespeichert wird
    number_holder: object = None


def _similar_persons(pool, data: dict) -> list:
    """Personen, die einer neu anzulegenden ähnlich sind (ADR 0011).

    Bewusst nur drei Fälle und kein Ähnlichkeitswert: Angehörige teilen den
    Nachnamen, ein Hinweis bei jedem gleichen Nachnamen sagte nichts.
    """
    parts = name_parts(data.get("first_name"), data.get("last_name"))
    birth_date = _as_date(data.get("birth_date"))
    same_name = [p for p in pool if parts and name_parts(p.first_name, p.last_name) == parts]

    similar: list = []

    def add(reason: str, people) -> None:
        for person in people:
            if all(person is not known for _, known in similar):
                similar.append((reason, person))

    add(SIMILAR_BY_MEMBER_NUMBER, persons_with_member_number(pool, data.get("member_number")))
    if len(same_name) > 1:
        add(SIMILAR_BY_NAME, same_name)
    if birth_date is not None:
        add(SIMILAR_BY_BIRTH_DATE, [
            p for p in pool
            if _as_date(p.birth_date) == birth_date
            and (parts & name_parts(p.first_name, p.last_name)) - NAME_PARTICLES
        ])
    return similar


def resolve_household_rows(household_people, rows: list[dict], all_people) -> list[RowResolution]:
    """Sucht zu jeder Zeile eines Haushaltsbogens die gemeinte Person.

    Erst im Haushalt (``household_people``, leer bei einem neuen Haushalt),
    dann im gesamten Datenbestand (``all_people``). Eine Person ohne Haushalt
    wird bei sicherem Treffer zugeordnet; eine Person aus einem anderen
    Haushalt bleibt dort. Jede Person nimmt höchstens eine Zeile auf.
    """
    members = list(household_people)
    in_household = match_household_persons(members, rows)
    claimed = [person for person in in_household if person is not None]

    def unclaimed() -> list:
        return [p for p in all_people if all(p is not c for c in claimed)]

    resolutions: list[RowResolution] = []
    for data, member in zip(rows, in_household):
        if member is not None:
            resolutions.append(RowResolution(IN_HOUSEHOLD, member))
            continue
        found, _ = find_certain_person(unclaimed(), data)
        if found is None:
            resolutions.append(RowResolution(NEW))
            continue
        claimed.append(found)
        if any(found is m for m in members):
            status = IN_HOUSEHOLD
        elif found.household_id is None:
            status = ASSIGN
        else:
            status = OTHER_HOUSEHOLD
        resolutions.append(RowResolution(status, found))

    pool = unclaimed()
    for data, resolution in zip(rows, resolutions):
        if resolution.status == NEW:
            resolution.similar = _similar_persons(pool, data)
        # Die Nummer wird nur gespeichert, wenn die Person noch keine hat.
        stores_number = resolution.status in (NEW, IN_HOUSEHOLD, ASSIGN) and not (
            resolution.person is not None and resolution.person.member_number
        )
        if stores_number:
            resolution.number_holder = other_member_number_holder(
                all_people, data.get("member_number"), resolution.person)
    return resolutions


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
        and _number_confirms(holders[0], data, parts)
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

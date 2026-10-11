"""Import der Mitgliederliste aus einer vCard-Datei (.vcf).

Die Mitgliederliste füllt nur leere Angaben vorhandener Personen (ADR 0011):
Sie legt nichts an, fasst keine Haushalte an und überschreibt nichts. Aus
jeder Karte werden gelesen:

* ``X-WEILERID``           -> Mitgliedsnummer
* ``N`` / ``FN``           -> Vor- und Nachname
* ``BDAY``                 -> Geburtsdatum
* ``GENDER`` / ``X-GENDER``-> Geschlecht
* ``NOTE``                 -> Datum des Aufnahmegesprächs (Mitglied seit),
                              sonst das Jahrestag-Feld der Karte
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas
from .import_service import (
    ImportSession,
    _cleanup_sessions,
    _household_name,
    import_sessions,
    normalize_name,
    parse_date,
)
from .person_matching import (
    find_certain_person,
    full_name,
    normalize_member_number,
    other_member_number_holder,
)

# ---------------------------------------------------------------------------
# vCard low-level parsing
# ---------------------------------------------------------------------------

def decode_vcf(file_contents: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return file_contents.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_contents.decode("utf-8", errors="replace")


def _unfold(text: str) -> str:
    """RFC 6350 line folding aufheben (Zeilenumbruch + Leerzeichen/Tab)."""
    return re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n"))


def _unescape(value: str) -> str:
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in ("n", "N"):
                out.append("\n")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_components(value: str) -> list[str]:
    """Strukturierten Wert (``;``-getrennt) zerlegen, Escapes beachten."""
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            buf.append(value[i:i + 2])
            i += 2
            continue
        if ch == ";":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [_unescape(p).strip() for p in parts]


class VCardProperty:
    def __init__(self, name: str, params: dict[str, list[str]], raw_value: str):
        self.name = name
        self.params = params
        self.raw_value = raw_value

    @property
    def value(self) -> str:
        return _unescape(self.raw_value).strip()

    @property
    def components(self) -> list[str]:
        return _split_components(self.raw_value)

    def has_type(self, *types: str) -> bool:
        present = {t.lower() for t in self.params.get("TYPE", [])}
        return any(t.lower() in present for t in types)


def _parse_property(line: str) -> Optional[VCardProperty]:
    if ":" not in line:
        return None
    head, raw_value = line.split(":", 1)
    segments = head.split(";")
    name = segments[0].strip().upper()
    # Gruppenpraefix entfernen: "ITEM1.X-ABDATE" -> "X-ABDATE"
    if "." in name:
        name = name.split(".", 1)[1]

    params: dict[str, list[str]] = {}
    for seg in segments[1:]:
        if "=" in seg:
            key, val = seg.split("=", 1)
        else:
            key, val = "TYPE", seg
        params.setdefault(key.strip().upper(), []).extend(
            v.strip().strip('"') for v in val.split(",") if v.strip()
        )

    if any(v.lower() == "quoted-printable" for v in params.get("ENCODING", [])):
        try:
            import quopri
            raw_value = quopri.decodestring(raw_value).decode("utf-8", errors="replace")
        except Exception:
            pass

    return VCardProperty(name, params, raw_value)


def _group_key(line: str) -> Optional[str]:
    """Gruppenpraefix einer Zeile (``ITEM1.X-ABDATE:...`` -> ``ITEM1``)."""
    head = line.split(":", 1)[0].split(";", 1)[0]
    return head.split(".", 1)[0].upper() if "." in head else None


def parse_vcards(text: str) -> list[list[tuple[Optional[str], VCardProperty]]]:
    """Zerlegt den Dateiinhalt in Karten aus (Gruppe, Property)-Paaren."""
    cards = []
    current: Optional[list[tuple[Optional[str], VCardProperty]]] = None
    for line in _unfold(text).split("\n"):
        line = line.rstrip()
        if not line.strip():
            continue
        upper = line.strip().upper()
        if upper.startswith("BEGIN:VCARD"):
            current = []
            continue
        if upper.startswith("END:VCARD"):
            if current is not None:
                cards.append(current)
            current = None
            continue
        if current is None:
            continue
        prop = _parse_property(line)
        if prop:
            current.append((_group_key(line), prop))
    return cards


# ---------------------------------------------------------------------------
# Feld-Konvertierung
# ---------------------------------------------------------------------------

VCF_GENDER_MAPPING = {
    "M": "m",
    "MALE": "m",
    "F": "f",
    "FEMALE": "f",
    "O": "d",
    "N": "d",
    "U": None,
    "": None,
}


def parse_vcf_gender(raw: str) -> Optional[str]:
    if not raw:
        return None
    # vCard 4.0: "M;man" -> nur die erste Komponente ist relevant
    token = raw.split(";", 1)[0].strip().upper()
    return VCF_GENDER_MAPPING.get(token, None)


def parse_vcf_date(raw: str) -> Optional[date]:
    """BDAY/ANNIVERSARY: ``YYYYMMDD``, ``YYYY-MM-DD`` oder ``--MMDD``."""
    if not raw:
        return None
    s = raw.strip().split("T", 1)[0]
    m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return parse_date(s)


def parse_german_date(raw: str) -> Optional[date]:
    """``28.01.2023``, ``21.01.23`` oder ``30.11. 19`` (mit Leerzeichen)."""
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2,4})", raw or "")
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 100:
        year += 2000 if year <= 69 else 1900
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Eintrittsdatum
# ---------------------------------------------------------------------------

DATE_RE = r"\d{1,2}\.\s*\d{1,2}\.\s*\d{2,4}"

# "Aufnahmegespräch am 28.01.2023", "Info + Aufnahmegespräch am 14.01.2023",
# "Aufnahmegespräch: 21.11.2021", "Aufnahmegespräch 30.11. 19 J"
MEMBER_SINCE_AFTER_RE = re.compile(
    r"Aufnahmegespr\w*\s*[:,]?\s*(?:am\s+)*(" + DATE_RE + r")", re.IGNORECASE
)
# "01.12.2018 Aufnahmegespräch", "26.05.2018Aufnahmegespräch"
MEMBER_SINCE_BEFORE_RE = re.compile(
    r"(" + DATE_RE + r")\s*[:,]?\s*(?:J\s+)?Aufnahmegespr", re.IGNORECASE
)


def extract_member_since(note: str) -> Optional[date]:
    """Datum des Aufnahmegespraechs = Beginn der Mitgliedschaft."""
    if not note:
        return None
    for regex in (MEMBER_SINCE_AFTER_RE, MEMBER_SINCE_BEFORE_RE):
        for match in regex.finditer(note):
            parsed = parse_german_date(match.group(1))
            if parsed:
                return parsed
    return None


ANNIVERSARY_LABELS = ("anniversary", "jahrestag", "beitritt", "aufnahme")
ANNIVERSARY_EXCLUDED_LABELS = ("todestag",)


def _props_by_name(card) -> dict[str, list[VCardProperty]]:
    out: dict[str, list[VCardProperty]] = {}
    for _group, prop in card:
        out.setdefault(prop.name, []).append(prop)
    return out


def _anniversary_date(card) -> Optional[date]:
    """Beitrittsdatum aus ``X-ANNIVERSARY`` bzw. gelabeltem ``X-ABDATE``."""
    labels: dict[Optional[str], list[str]] = {}
    for group, prop in card:
        if prop.name == "X-ABLABEL":
            labels.setdefault(group, []).append(prop.value.lower())

    for group, prop in card:
        if prop.name not in ("X-ANNIVERSARY", "ANNIVERSARY", "X-ABDATE"):
            continue
        group_labels = " ".join(labels.get(group, []))
        if any(bad in group_labels for bad in ANNIVERSARY_EXCLUDED_LABELS):
            continue
        if prop.name == "X-ABDATE" and group_labels and not any(
            good in group_labels for good in ANNIVERSARY_LABELS
        ):
            continue
        parsed = parse_vcf_date(prop.value)
        if parsed:
            return parsed
    return None


# ---------------------------------------------------------------------------
# Karte -> Person
# ---------------------------------------------------------------------------

def parse_vcard_person(card) -> Optional[dict]:
    """Die Angaben einer Karte; None, wenn sie keinen Namen trägt.

    Was das Notizfeld sonst nennt (Partner*innen, Kinder), wird nicht
    ausgewertet: Die Mitgliederliste legt keine Personen an.
    """
    props = _props_by_name(card)

    name_components = props["N"][0].components if props.get("N") else []
    last_name = name_components[0] if len(name_components) > 0 else ""
    # Weitere Vornamen stehen in einem eigenen Bestandteil und gehören zum Namen.
    first_name = " ".join(part for part in name_components[1:3] if part)
    display_name = props["FN"][0].value if props.get("FN") else ""

    if not first_name and not last_name:
        if not display_name:
            return None
        first_name, last_name = normalize_name(display_name)
    if not display_name:
        display_name = f"{first_name} {last_name}".strip()

    note = "\n".join(p.value for p in props.get("NOTE", []))

    gender_prop = props.get("GENDER") or props.get("X-GENDER") or []
    gender = parse_vcf_gender(gender_prop[0].value) if gender_prop else None

    birth = parse_vcf_date(props["BDAY"][0].value) if props.get("BDAY") else None
    member_since = extract_member_since(note) or _anniversary_date(card)

    member_number = None
    if props.get("X-WEILERID"):
        member_number = normalize_member_number(props["X-WEILERID"][0].value)

    return {
        "member_number": member_number,
        "first_name": first_name,
        "last_name": last_name,
        "name": display_name,
        "birth_date": birth.isoformat() if birth else None,
        "gender": gender,
        "member_since": member_since.isoformat() if member_since else None,
    }


def parse_vcf(file_contents: bytes) -> dict:
    cards = parse_vcards(decode_vcf(file_contents))
    persons: list[dict] = []
    skipped_no_name = 0
    for card in cards:
        person = parse_vcard_person(card)
        if person is None:
            skipped_no_name += 1
            continue
        persons.append(person)

    return {
        "total_cards": len(cards),
        "skipped_no_name": skipped_no_name,
        "persons": persons,
    }


# ---------------------------------------------------------------------------
# Abgleich mit dem Datenbestand
# ---------------------------------------------------------------------------

def _as_datetime(iso_value: Optional[str]) -> Optional[datetime]:
    parsed = parse_date(iso_value) if iso_value else None
    return datetime(parsed.year, parsed.month, parsed.day) if parsed else None


@dataclass
class CardPlan:
    """Was eine Karte bei der Person bewirkt, die sie sicher trifft."""
    card: dict
    #: Sicher getroffene Person; None, wenn die Karte niemanden trifft
    person: Optional[models.Person] = None
    #: Feld -> Wert für jede Angabe, die bei der Person noch fehlt
    fills: dict = field(default_factory=dict)
    #: Wer die Mitgliedsnummer der Karte schon trägt
    number_holder: Optional[models.Person] = None
    #: Eintrittsdatum der Karte, wenn es vom gespeicherten abweicht
    deviating_member_since: Optional[datetime] = None


def _plan(cards: list[dict], all_persons: list) -> list[CardPlan]:
    """Stellt je Karte fest, welche Lücken sie füllt.

    Vorhandene Werte bleiben, auch wenn die Karte etwas anderes nennt: Eine
    unveränderte Mitgliederliste darf keine Korrektur der Belegungskommission
    zurückdrehen.
    """
    hits = [find_certain_person(all_persons, card)[0] for card in cards]
    # Treffen zwei Karten dieselbe Person, ist offen, welche sie meint: keine gilt.
    cards_per_person = Counter(person.id for person in hits if person is not None)
    # Nummern, die eine frühere Karte desselben Durchgangs schon vergibt
    numbers_planned: dict[str, models.Person] = {}

    plans: list[CardPlan] = []
    for card, person in zip(cards, hits):
        if person is not None and cards_per_person[person.id] > 1:
            person = None
        plan = CardPlan(card, person)
        plans.append(plan)
        if person is None:
            continue

        member_since = _as_datetime(card.get("member_since"))
        offered = {
            "birth_date": _as_datetime(card.get("birth_date")),
            "gender": card.get("gender"),
            "member_since": member_since,
        }
        plan.fills = {
            field_name: value for field_name, value in offered.items()
            if value and not getattr(person, field_name)
        }
        if member_since and person.member_since and person.member_since.date() != member_since.date():
            plan.deviating_member_since = member_since

        number = card.get("member_number")
        if number and not person.member_number:
            holder = (other_member_number_holder(all_persons, number, person)
                      or numbers_planned.get(number))
            if holder is None:
                plan.fills["member_number"] = number
                numbers_planned[number] = person
            else:
                plan.number_holder = holder
    return plans


def _count_fills(plans: list[CardPlan]) -> schemas.MemberListFills:
    # Jede Person hat höchstens eine Karte, die bei ihr etwas füllt.
    fills = schemas.MemberListFills(persons=sum(1 for plan in plans if plan.fills))
    for plan in plans:
        for field_name in plan.fills:
            setattr(fills, field_name, getattr(fills, field_name) + 1)
    return fills


def _unmatched(plans: list[CardPlan]) -> int:
    return sum(1 for plan in plans if plan.person is None)


def _number_conflicts(plans: list[CardPlan]) -> list[schemas.MemberNumberConflict]:
    return [
        schemas.MemberNumberConflict(
            person=full_name(plan.person),
            member_number=plan.card["member_number"],
            holder=full_name(plan.number_holder),
        )
        for plan in plans if plan.number_holder is not None
    ]


def analyze_vcf(file_contents: bytes, db: Session) -> schemas.VcfAnalysisResponse:
    _cleanup_sessions()
    parsed = parse_vcf(file_contents)
    plans = _plan(parsed["persons"], db.query(models.Person).all())

    deviations = [
        schemas.MemberSinceDeviation(
            person=full_name(plan.person),
            household=_household_name(db, plan.person.household_id),
            stored=plan.person.member_since.date().isoformat(),
            member_list=plan.deviating_member_since.date().isoformat(),
            days=abs((plan.person.member_since.date() - plan.deviating_member_since.date()).days),
        )
        for plan in plans if plan.deviating_member_since is not None
    ]
    deviations.sort(key=lambda deviation: deviation.days, reverse=True)

    session = ImportSession("vcf", parsed["persons"], {})
    import_sessions[session.id] = session

    return schemas.VcfAnalysisResponse(
        session_id=session.id,
        total_cards=parsed["total_cards"],
        skipped_no_name=parsed["skipped_no_name"],
        unmatched_cards=_unmatched(plans),
        unchanged_cards=sum(1 for plan in plans if plan.person is not None and not plan.fills),
        fills=_count_fills(plans),
        member_since_deviations=deviations,
        member_numbers_not_stored=_number_conflicts(plans),
    )


def commit_vcf(request: schemas.VcfCommitRequest, db: Session) -> schemas.VcfCommitResponse:
    """Füllt die Lücken, die die Analyse gezählt hat.

    Der Plan entsteht gegen den jetzigen Datenbestand neu; was inzwischen von
    Hand eingetragen wurde, bleibt also stehen.
    """
    session = import_sessions.get(request.session_id)
    if not session:
        raise ValueError("Import-Session nicht gefunden oder abgelaufen")

    plans = _plan(session.raw_data, db.query(models.Person).all())
    for plan in plans:
        for field_name, value in plan.fills.items():
            setattr(plan.person, field_name, value)
        if plan.fills:
            plan.person.updated_at = datetime.utcnow()

    db.commit()
    del import_sessions[request.session_id]

    return schemas.VcfCommitResponse(
        fills=_count_fills(plans),
        unmatched_cards=_unmatched(plans),
        member_numbers_not_stored=_number_conflicts(plans),
    )

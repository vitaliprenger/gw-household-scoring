"""Import von Mitgliedsdaten aus einer vCard-Datei (.vcf).

Die vCard-Datei des Mitgliederverzeichnisses enthaelt pro Mitglied eine Karte.
Daraus werden abgeleitet:

* ``X-WEILERID``           -> Mitgliedsnummer
* ``N`` / ``FN``           -> Vor- und Nachname
* ``BDAY``                 -> Geburtsdatum
* ``GENDER`` / ``X-GENDER``-> Geschlecht
* ``ADR`` (Komponente 2)   -> Wohnungsnummer; gesetzt = aktueller Bewohner
* ``NOTE``                 -> Datum des Aufnahmegespraechs (Mitglied seit),
                              Partner*in sowie Kinder mit Geburtsdatum
* ``REV``                  -> Zeitstempel des Datensatzes (Idempotenz)

Haushalte entstehen primaer ueber die Wohnungsnummer (alle Personen derselben
Wohnung bilden einen Haushalt), sekundaer ueber die im ``NOTE``-Feld genannten
Partnerbeziehungen.
"""

import re
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas
from .import_service import (
    ImportSession,
    _cleanup_sessions,
    import_sessions,
    match_household,
    normalize_member_number,
    normalize_name,
    parse_date,
)

IMPORT_SOURCE = "VCF-Mitgliederliste"

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


def parse_vcf_timestamp(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    s = raw.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


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
# NOTE-Auswertung
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

NAME_TOKEN = r"[A-ZÄÖÜ][\wÄÖÜäöüß'\-]*\.?"
NAME_RE = (
    r"(" + NAME_TOKEN + r"(?:[ \t]+(?:von|van|de|der|dem|zu)\b)?"
    r"(?:[ \t]+" + NAME_TOKEN + r"){0,3})"
)

# "Partner: Jörn Berker", "Partnerin: Merle Hömberg", "Ehefrau Lina: 24.09.1985"
PARTNER_LABEL_RE = re.compile(
    r"\b(?:Partner|Partnerin|Ehemann|Ehefrau|Ehepartner|Ehepartnerin)\b\s*:?\s*" + NAME_RE,
    re.IGNORECASE,
)
# "Mann von Stefanie Krümpel", "Frau von Ilja Harjes", "Partner von Hannah Reimer",
# "gehört zu Hans Stuckenbrock"
PARTNER_VON_RE = re.compile(
    r"\b(?:Partner|Partnerin|Mann|Frau|Ehemann|Ehefrau)\s+von\s+" + NAME_RE
    + r"|\bgeh\w*rt\s+zu\s+" + NAME_RE,
    re.IGNORECASE,
)

CHILD_HEADER_RE = re.compile(
    r"^\s*(?:\d+\s+|ein\s+|eine\s+)?"
    # "Tochter von X" beschreibt die Eltern der Person, nicht ihr Kind
    r"(?:Kinder|Kind|S\whne|Sohn|T\wchter|Tochter|Zwillinge)\b(?![ \t]+von\b)\s*:?\s*",
    re.IGNORECASE,
)

# "Tochter von Heike Nigge", "Sohn von Sebastian und Tanja Danek"
PARENT_VON_RE = re.compile(
    r"\b(?:Kind|Sohn|Tochter)\s+von\s+" + NAME_RE, re.IGNORECASE
)
# "Kinder: Alva (24.05.2018; mit SBA80), Janna (18.01.2021)"
CHILD_ENTRY_SPLIT_RE = re.compile(r"\s*(?:,|;|\bund\b|/)\s*", re.IGNORECASE)

# Zeilen, die typischerweise Verwaltungsnotizen sind und keine Personendaten
NOISE_WORDS = (
    "infoveranstaltung", "aufnahmegespr", "beitritt", "mmz", "infos", "wegweiser",
    "mail", "e-mail", "gewerbe", "plenum", "stammtisch", "mitgliedstatus",
    "mitgliedsstatus", "vorstand", "erinnerung", "nachfrage", "geschickt",
    "gesendet", "gemailt",
)


def _looks_like_noise(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in NOISE_WORDS)


NON_NAME_WORDS = {
    "jahre", "jahr", "jung", "alt", "monate", "personen", "person", "erw",
    "kind", "kinder", "sohn", "tochter", "baby", "zwillinge", "schwanger",
    "geb", "geboren", "unbekannt", "ca", "n.n", "nn",
}


def _clean_person_name(raw: str) -> Optional[str]:
    # Satzende abschneiden ("Bohren-Harjes. Schauspieler"), Initialen ausnehmen
    raw = re.sub(r"(?<=[\wÄÖÜäöüß]{2})\.\s+\S.*$", "", raw or "")
    name = re.sub(r"\(.*?\)", " ", raw or "")
    name = re.sub(r"\d", " ", name)
    name = re.sub(r"[\"!?*]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" .,:;-")
    if not name:
        return None
    tokens = [t for t in name.split() if t]
    # Namen bestehen aus grossgeschriebenen Tokens; das erste klein geschriebene
    # Token beendet den Namen ("Heike Nigge Daniel macht" -> "Heike Nigge").
    # Ausnahme: Namenspartikel wie "van" oder "de" mitten im Namen.
    cleaned: list[str] = []
    for idx, tok in enumerate(tokens):
        if re.match(r"^[a-zäöüß]", tok):
            is_particle = tok.lower().strip(".") in NAME_PARTICLES
            if idx > 0 and is_particle and idx + 1 < len(tokens):
                cleaned.append(tok)
                continue
            break
        cleaned.append(tok)
    if not cleaned:
        return None
    # Nur Tokens, die wie Namen aussehen (beginnen mit Grossbuchstabe)
    if not re.match(r"^[A-ZÄÖÜ]", cleaned[0]):
        return None
    if cleaned[0].lower().strip(".") in NON_NAME_WORDS:
        return None
    name = " ".join(cleaned).strip(" .,:;-")
    if len(name) < 2 or len(name) > 60:
        return None
    return name


NAME_PARTICLES = {"von", "van", "de", "der", "dem", "den", "zu", "zum", "la", "le", "di", "da"}


def split_first_last(name: str, default_last_name: str = "") -> tuple[str, str]:
    """Zerlegt ``Maja Van Loey`` in ``("Maja", "Van Loey")``."""
    tokens = name.split()
    if not tokens:
        return ("", default_last_name)
    if len(tokens) == 1:
        return (tokens[0], default_last_name)
    split_at = len(tokens) - 1
    while split_at > 1 and tokens[split_at - 1].lower().strip(".") in NAME_PARTICLES:
        split_at -= 1
    return (" ".join(tokens[:split_at]), " ".join(tokens[split_at:]))


def extract_parent_names(note: str) -> list[str]:
    """Eltern, in deren Haushalt die Person gehoert ("Tochter von Heike Nigge")."""
    if not note:
        return []
    names: list[str] = []
    for match in PARENT_VON_RE.finditer(note):
        raw = next((g for g in match.groups() if g), None)
        # "Sohn von Sebastian und Tanja Danek" nennt zwei Elternteile
        parts = [_clean_person_name(p) for p in re.split(r"\s+und\s+", raw or "")]
        parts = [p for p in parts if p]
        # "Sebastian und Tanja Danek": der Nachname steht nur beim letzten Namen
        if len(parts) > 1 and " " in parts[-1]:
            shared_last = parts[-1].rsplit(" ", 1)[1]
            parts = [p if " " in p else f"{p} {shared_last}" for p in parts]
        for name in parts:
            if name not in names:
                names.append(name)
    return names


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


def extract_partner_names(note: str) -> list[str]:
    """Im NOTE-Feld genannte Partner*innen."""
    if not note:
        return []
    names: list[str] = []
    for line in note.split("\n"):
        line = line.strip()
        if not line:
            continue
        for regex in (PARTNER_VON_RE, PARTNER_LABEL_RE):
            for match in regex.finditer(line):
                raw = next((g for g in match.groups() if g), None)
                name = _clean_person_name(raw or "")
                if name and " " in name and name not in names:
                    names.append(name)
    return names


def extract_children(note: str, default_last_name: str) -> list[dict]:
    """Kinder samt Geburtsdatum aus dem NOTE-Feld.

    Erkannt werden u. a. ``Kind: Mats Yanis Vielhaus (08.12.2020)``,
    ``Kinder:\nMarlene Bleines, 07.04.2009`` und ``Tochter: Frieda 30.12.2018``.
    """
    if not note:
        return []

    lines = [l.strip() for l in note.split("\n")]
    entries: list[str] = []
    in_block = False

    for line in lines:
        if not line:
            in_block = False
            continue
        header = CHILD_HEADER_RE.match(line)
        if header:
            rest = line[header.end():].strip()
            if rest:
                entries.extend(_split_child_entries(rest))
                in_block = False
            else:
                # "Kinder:" als eigene Zeile -> Folgezeilen sind Eintraege
                in_block = True
            continue
        if in_block:
            if _looks_like_noise(line):
                in_block = False
                continue
            entries.extend(_split_child_entries(line))

    children: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        child = _parse_child_entry(entry, default_last_name)
        if not child:
            continue
        key = (child["first_name"] + "|" + child["last_name"] + "|"
               + (child["birth_date"] or "")).lower()
        if key in seen:
            continue
        seen.add(key)
        children.append(child)
    return children


def _split_child_entries(text: str) -> list[str]:
    """Trennt ``Alva (24.05.2018), Janna (18.01.2021)`` in Einzeleintraege.

    Kommata innerhalb von Klammern sowie ``Name, 07.04.2009`` bleiben erhalten.
    """
    protected = []

    def _protect(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    # Klammerausdruecke und "Name, TT.MM.JJJJ" vor dem Splitten schuetzen
    text = re.sub(r"\([^)]*\)", _protect, text)
    text = re.sub(r",\s*(" + DATE_RE + r")", _protect, text)

    parts = [p.strip() for p in CHILD_ENTRY_SPLIT_RE.split(text) if p.strip()]

    def _restore(value: str) -> str:
        return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], value)

    return [_restore(p) for p in parts]


def _parse_child_entry(entry: str, default_last_name: str) -> Optional[dict]:
    entry = entry.strip(" .,:;-")
    if not entry or _looks_like_noise(entry):
        return None

    birth = parse_german_date(entry)
    name = _clean_person_name(entry)
    if not name:
        return None
    if not birth and len(name.split()) > 3:
        return None

    first_name, last_name = split_first_last(name, default_last_name)

    return {
        "first_name": first_name,
        "last_name": last_name,
        "birth_date": birth.isoformat() if birth else None,
    }


# ---------------------------------------------------------------------------
# Karte -> Person
# ---------------------------------------------------------------------------

ANNIVERSARY_LABELS = ("anniversary", "jahrestag", "beitritt", "aufnahme")
ANNIVERSARY_EXCLUDED_LABELS = ("todestag",)


def _props_by_name(card) -> dict[str, list[VCardProperty]]:
    out: dict[str, list[VCardProperty]] = {}
    for _group, prop in card:
        out.setdefault(prop.name, []).append(prop)
    return out


def _pick_address(props: dict[str, list[VCardProperty]]) -> Optional[VCardProperty]:
    addresses = props.get("ADR", [])
    if not addresses:
        return None
    for adr in addresses:
        if adr.has_type("home"):
            return adr
    return addresses[0]


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


def parse_vcard_person(card) -> Optional[dict]:
    props = _props_by_name(card)

    name_parts = props["N"][0].components if props.get("N") else []
    last_name = name_parts[0] if len(name_parts) > 0 else ""
    first_name = name_parts[1] if len(name_parts) > 1 else ""
    display_name = props["FN"][0].value if props.get("FN") else ""

    if not first_name and not last_name:
        if not display_name:
            return None
        first_name, last_name = normalize_name(display_name)
    if not display_name:
        display_name = f"{first_name} {last_name}".strip()

    address = _pick_address(props)
    components = address.components if address else []
    apartment_unit = components[1].strip() if len(components) > 1 else ""
    street = components[2].strip() if len(components) > 2 else ""
    city = components[3].strip() if len(components) > 3 else ""
    postal_code = components[5].strip() if len(components) > 5 else ""

    note = "\n".join(p.value for p in props.get("NOTE", []))

    gender_prop = props.get("GENDER") or props.get("X-GENDER") or []
    gender = parse_vcf_gender(gender_prop[0].value) if gender_prop else None

    birth = parse_vcf_date(props["BDAY"][0].value) if props.get("BDAY") else None
    member_since = extract_member_since(note) or _anniversary_date(card)
    rev = parse_vcf_timestamp(props["REV"][0].value) if props.get("REV") else None

    member_number = None
    if props.get("X-WEILERID"):
        member_number = normalize_member_number(props["X-WEILERID"][0].value)

    categories: list[str] = []
    for prop in props.get("CATEGORIES", []):
        categories.extend(c.strip() for c in prop.value.split(",") if c.strip())

    return {
        "temp_id": str(uuid.uuid4()),
        "uid": props["UID"][0].value if props.get("UID") else None,
        "member_number": member_number,
        "first_name": first_name,
        "last_name": last_name,
        "name": display_name,
        "birth_date": birth.isoformat() if birth else None,
        "gender": gender,
        "member_since": member_since.isoformat() if member_since else None,
        "apartment_unit": apartment_unit or None,
        "address": ", ".join(x for x in (street, f"{postal_code} {city}".strip()) if x) or None,
        "is_resident": bool(apartment_unit),
        "rev": rev,
        "categories": categories,
        "note": note,
        "partner_names": extract_partner_names(note),
        "parent_names": extract_parent_names(note),
        "children": extract_children(note, last_name),
        "role": "member",
        "source": "vcard",
    }


# ---------------------------------------------------------------------------
# Haushaltsbildung
# ---------------------------------------------------------------------------

def _name_key(first_name: str, last_name: str) -> str:
    first = (first_name or "").strip().lower()
    last = (last_name or "").strip().lower()
    return first + "|" + last


def _find(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(parent: list[int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[max(ra, rb)] = min(ra, rb)


def build_households(persons: list[dict]) -> list[dict]:
    """Fasst Karten zu Haushalten zusammen.

    Primaer ueber die Wohnungsnummer (alle Bewohner*innen einer Wohnung bilden
    einen Haushalt), fuer Nicht-Bewohner*innen ueber die im NOTE-Feld genannten
    Partnerbeziehungen.

    Elternbeziehungen ("Tochter von X") werden bewusst *nicht* zum Gruppieren
    genutzt: erwachsene Kinder mit eigener Familie wuerden sonst mit dem
    Haushalt der Eltern verschmolzen. Sie erscheinen stattdessen als Hinweis
    in der Vorschau und koennen dort manuell zugeordnet werden.
    """
    parent = list(range(len(persons)))

    by_unit: dict[str, list[int]] = {}
    for idx, person in enumerate(persons):
        if person["apartment_unit"]:
            by_unit.setdefault(person["apartment_unit"], []).append(idx)
    for indices in by_unit.values():
        for other in indices[1:]:
            _union(parent, indices[0], other)

    by_name: dict[str, list[int]] = {}
    for idx, person in enumerate(persons):
        key = _name_key(person["first_name"], person["last_name"])
        by_name.setdefault(key, []).append(idx)

    for idx, person in enumerate(persons):
        for related_name in person["partner_names"]:
            related_first, related_last = split_first_last(related_name)
            matches = by_name.get(_name_key(related_first, related_last), [])
            if len(matches) != 1:
                continue  # nicht eindeutig aufloesbar
            other = matches[0]
            if other == idx:
                continue
            # Nur verbinden, wenn die Wohnsituation nicht widerspricht
            if person["apartment_unit"] or persons[other]["apartment_unit"]:
                continue
            _union(parent, idx, other)

    groups: dict[int, list[int]] = {}
    for idx in range(len(persons)):
        groups.setdefault(_find(parent, idx), []).append(idx)

    return [_build_household([persons[i] for i in groups[root]]) for root in sorted(groups)]


def _household_name(members: list[dict]) -> str:
    if len(members) == 1:
        return members[0]["name"] or "Unbekannt"
    last_names: list[str] = []
    for member in members:
        last = (member["last_name"] or "").strip()
        if last and last not in last_names:
            last_names.append(last)
    if last_names:
        return " / ".join(last_names)
    return members[0]["name"] or "Unbekannt"


def _note_person(first_name: str, last_name: str, birth_date, role: str, mentioned_by: str) -> dict:
    full_name = (first_name + " " + last_name).strip()
    return {
        "temp_id": str(uuid.uuid4()),
        "first_name": first_name,
        "last_name": last_name,
        "name": full_name,
        "birth_date": birth_date,
        "gender": None,
        "member_number": None,
        "member_since": None,
        "apartment_unit": None,
        "rev": None,
        "role": role,
        "source": "note",
        "mentioned_by": mentioned_by,
    }


def _build_household(members: list[dict]) -> dict:
    members = sorted(members, key=lambda m: (m["last_name"] or "", m["first_name"] or ""))

    units = [m["apartment_unit"] for m in members if m["apartment_unit"]]
    apartment_unit = units[0] if units else None

    known_names = {_name_key(m["first_name"], m["last_name"]) for m in members}
    warnings: list[str] = []
    extra_persons: list[dict] = []

    # Partner*innen ohne eigene Karte als Haushaltsmitglied ergaenzen
    for member in members:
        for partner_name in member["partner_names"]:
            first, last = split_first_last(partner_name, member["last_name"])
            key = _name_key(first, last)
            if key in known_names:
                continue
            known_names.add(key)
            extra_persons.append(_note_person(first, last, None, "partner", member["name"]))

    # Kinder aus den Notizen aller Haushaltsmitglieder (ohne Dubletten).
    # Nennen beide Partner*innen dasselbe Kind nur mit Vornamen, erhaelt es je
    # nach Karte einen anderen Nachnamen - daher zusaetzlich ueber
    # Vorname + Geburtsdatum entdoppeln.
    seen_birth = {
        (m["first_name"].strip().lower(), m["birth_date"])
        for m in members if m["birth_date"]
    }
    for member in members:
        for child in member["children"]:
            key = _name_key(child["first_name"], child["last_name"])
            birth_key = (child["first_name"].strip().lower(), child["birth_date"])
            if key in known_names or (child["birth_date"] and birth_key in seen_birth):
                continue
            known_names.add(key)
            seen_birth.add(birth_key)
            extra_persons.append(_note_person(
                child["first_name"], child["last_name"], child["birth_date"],
                "child", member["name"],
            ))
            if not child["birth_date"]:
                child_name = (child["first_name"] + " " + child["last_name"]).strip()
                warnings.append("Kind ohne Geburtsdatum: " + child_name)

    if len(set(units)) > 1:
        warnings.append("Unterschiedliche Wohnungsnummern: " + ", ".join(sorted(set(units))))

    revisions = [m["rev"] for m in members if m["rev"]]

    return {
        "temp_id": str(uuid.uuid4()),
        "name": _household_name(members),
        "apartment_unit": apartment_unit,
        "address": next((m["address"] for m in members if m["address"]), None),
        "is_resident": bool(apartment_unit),
        "rev": max(revisions) if revisions else None,
        "persons": members + extra_persons,
        "warnings": warnings,
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
        "households": build_households(persons),
    }


# ---------------------------------------------------------------------------
# Abgleich mit dem Datenbestand
# ---------------------------------------------------------------------------

VCF_FIELD_LABELS = {
    "name": "Haushaltsname",
    "apartment_unit": "Wohnungsnummer",
    "is_resident": "Aktueller Bewohner",
    "household_member_count": "Haushaltsgroesse",
}


def _display(value) -> str:
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)


def compute_vcf_changes(hh_data: dict, existing: models.Household) -> Optional[schemas.ExistingDataChanges]:
    """Welche Felder des bestehenden Haushalts wuerde der Import ueberschreiben?"""
    overwrites: list[schemas.DataChange] = []

    new_values = {
        "apartment_unit": hh_data.get("apartment_unit"),
        "is_resident": hh_data.get("is_resident", False),
        "household_member_count": len(hh_data.get("persons", [])),
    }
    for field, new_value in new_values.items():
        old_value = getattr(existing, field, None)
        if new_value is None:
            continue
        if old_value is None and not new_value:
            continue
        if _display(old_value) == _display(new_value):
            continue
        overwrites.append(schemas.DataChange(
            field=VCF_FIELD_LABELS.get(field, field),
            old_value=_display(old_value) if old_value is not None else None,
            new_value=_display(new_value),
        ))

    # Personen, die in der Datenbank stehen, aber nicht in der vCard vorkommen
    import_keys = {
        _name_key(p["first_name"], p["last_name"]) for p in hh_data.get("persons", [])
    }
    import_numbers = {p["member_number"] for p in hh_data.get("persons", []) if p["member_number"]}
    for person in existing.people:
        if person.archived:
            continue
        if person.member_number and person.member_number in import_numbers:
            continue
        if _name_key(person.first_name, person.last_name) in import_keys:
            continue
        overwrites.append(schemas.DataChange(
            field="Nur in der Datenbank",
            old_value=f"{person.first_name} {person.last_name}".strip(),
            new_value="bleibt unveraendert erhalten",
        ))

    return schemas.ExistingDataChanges(fields_to_overwrite=overwrites) if overwrites else None


def _to_person_preview(person: dict) -> schemas.VcfPersonPreview:
    return schemas.VcfPersonPreview(
        temp_id=person["temp_id"],
        name=person["name"],
        first_name=person["first_name"],
        last_name=person["last_name"],
        birth_date=person.get("birth_date"),
        gender=person.get("gender"),
        member_number=person.get("member_number"),
        member_since=person.get("member_since"),
        apartment_unit=person.get("apartment_unit"),
        role=person["role"],
        source=person["source"],
        mentioned_by=person.get("mentioned_by"),
    )


def analyze_vcf(file_contents: bytes, db: Session) -> schemas.VcfAnalysisResponse:
    _cleanup_sessions()
    parsed = parse_vcf(file_contents)

    previews: list[schemas.VcfHouseholdPreview] = []
    for hh_data in parsed["households"]:
        match_result = match_household(hh_data, db)

        already_imported = False
        data_changes = None
        if match_result.matched_household_id:
            existing = db.query(models.Household).get(match_result.matched_household_id)
            if existing:
                if (existing.vcf_import_timestamp and hh_data.get("rev")
                        and existing.vcf_import_timestamp == hh_data["rev"]):
                    already_imported = True
                else:
                    data_changes = compute_vcf_changes(hh_data, existing)

        previews.append(schemas.VcfHouseholdPreview(
            temp_id=hh_data["temp_id"],
            name=hh_data["name"],
            apartment_unit=hh_data.get("apartment_unit"),
            address=hh_data.get("address"),
            is_resident=hh_data.get("is_resident", False),
            timestamp=hh_data["rev"].isoformat() if hh_data.get("rev") else None,
            persons=[_to_person_preview(p) for p in hh_data["persons"]],
            match_result=match_result,
            already_imported=already_imported,
            warnings=hh_data.get("warnings", []),
            existing_data_changes=data_changes,
        ))

    # Treffen mehrere Import-Haushalte denselben bestehenden Haushalt, wuerde der
    # zweite den ersten ueberschreiben - darauf muss der Import hinweisen.
    target_counts: dict[int, int] = {}
    for preview in previews:
        target = preview.match_result.matched_household_id
        if target and not preview.already_imported:
            target_counts[target] = target_counts.get(target, 0) + 1
    for preview in previews:
        target = preview.match_result.matched_household_id
        if target and target_counts.get(target, 0) > 1:
            preview.warnings = preview.warnings + [
                "Mehrere Import-Haushalte zeigen auf denselben bestehenden Haushalt "
                f"\"{preview.match_result.matched_household_name}\" - bitte Zuordnung pruefen."
            ]

    session = ImportSession("vcf", parsed["households"], {})
    import_sessions[session.id] = session

    return schemas.VcfAnalysisResponse(
        session_id=session.id,
        total_cards=parsed["total_cards"],
        skipped_no_name=parsed["skipped_no_name"],
        total_persons=sum(len(h["persons"]) for h in parsed["households"]),
        resident_households=sum(1 for h in parsed["households"] if h["is_resident"]),
        households=previews,
    )


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

def _as_datetime(iso_value: Optional[str]) -> Optional[datetime]:
    parsed = parse_date(iso_value) if iso_value else None
    return datetime(parsed.year, parsed.month, parsed.day) if parsed else None


def _apply_person_fields(person: models.Person, data: dict) -> bool:
    """Uebertraegt vorhandene vCard-Werte; leere Werte loeschen nichts."""
    changed = False
    values = {
        "birth_date": _as_datetime(data.get("birth_date")),
        "member_since": _as_datetime(data.get("member_since")),
        "gender": data.get("gender"),
        "member_number": data.get("member_number"),
    }
    for field, value in values.items():
        if value in (None, "") or getattr(person, field) == value:
            continue
        setattr(person, field, value)
        changed = True
    if data.get("rev") is not None and person.vcf_import_timestamp != data["rev"]:
        person.vcf_import_timestamp = data["rev"]
        changed = True
    if changed:
        person.updated_at = datetime.utcnow()
    return changed


def _new_person(data: dict, household_id: Optional[int]) -> models.Person:
    return models.Person(
        household_id=household_id,
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        birth_date=_as_datetime(data.get("birth_date")),
        member_since=_as_datetime(data.get("member_since")),
        gender=data.get("gender"),
        member_number=data.get("member_number"),
        vcf_import_timestamp=data.get("rev"),
        updated_at=datetime.utcnow(),
    )


def _find_existing_person(data: dict, household: models.Household, db: Session) -> Optional[models.Person]:
    """Sucht die Person zuerst im Haushalt, dann global ueber die Mitgliedsnummer."""
    member_number = data.get("member_number")
    if member_number:
        for person in household.people:
            if person.member_number == member_number:
                return person

    key = _name_key(data.get("first_name"), data.get("last_name"))
    for person in household.people:
        if _name_key(person.first_name, person.last_name) == key:
            return person

    # Zweitnamen unterscheiden sich haeufig zwischen den Quellen
    # ("Jonathan Rye Matt" vs. "Jonathan Matt") -> Rufname + Nachname vergleichen
    birth = _as_datetime(data.get("birth_date"))
    last = (data.get("last_name") or "").strip().lower()
    first_token = (data.get("first_name") or "").strip().split(" ")[0].lower()
    for person in household.people:
        person_last = (person.last_name or "").strip().lower()
        if person_last != last:
            continue
        if birth and person.birth_date == birth:
            return person
        person_first = (person.first_name or "").strip().split(" ")[0].lower()
        if first_token and person_first == first_token:
            return person

    if member_number:
        return (
            db.query(models.Person)
            .filter(models.Person.member_number == member_number)
            .first()
        )
    return None


def _sync_household(hh: models.Household, hh_data: dict, persons: list[dict], db: Session) -> dict:
    hh.name = hh_data["name"]
    hh.apartment_unit = hh_data.get("apartment_unit")
    hh.is_resident = hh_data.get("is_resident", False)
    hh.household_member_count = len(persons)
    hh.vcf_import_timestamp = hh_data.get("rev")
    hh.updated_at = datetime.utcnow()

    created = updated = assigned = 0
    for data in persons:
        existing = _find_existing_person(data, hh, db)
        if existing is None:
            db.add(_new_person(data, hh.id))
            created += 1
            continue
        if existing.household_id is None:
            # Person war bisher keinem Haushalt zugeordnet
            existing.household_id = hh.id
            existing.updated_at = datetime.utcnow()
            assigned += 1
        if _apply_person_fields(existing, data):
            updated += 1

    return {"created": created, "updated": updated, "assigned": assigned}


def commit_vcf(request: schemas.VcfCommitRequest, db: Session) -> schemas.VcfCommitResponse:
    session = import_sessions.get(request.session_id)
    if not session:
        raise ValueError("Import-Session nicht gefunden oder abgelaufen")

    raw_map = {r["temp_id"]: r for r in session.raw_data}

    households_created = households_updated = households_skipped = 0
    persons_created = persons_updated = persons_assigned = 0
    created_ids: list[int] = []

    for decision in request.decisions:
        raw = raw_map.get(decision.temp_id)
        if decision.action == "skip" or raw is None:
            households_skipped += 1
            continue

        excluded = set(decision.excluded_person_temp_ids or [])
        persons = [p for p in raw["persons"] if p["temp_id"] not in excluded]
        if not persons:
            households_skipped += 1
            continue

        hh = None
        if decision.action == "update" and decision.target_household_id:
            hh = db.query(models.Household).get(decision.target_household_id)

        if hh is None:
            hh = models.Household(
                name=raw["name"],
                import_source=IMPORT_SOURCE,
                application_date=datetime.utcnow(),
            )
            db.add(hh)
            db.flush()
            created_ids.append(hh.id)
            households_created += 1
        else:
            households_updated += 1

        counts = _sync_household(hh, raw, persons, db)
        persons_created += counts["created"]
        persons_updated += counts["updated"]
        persons_assigned += counts["assigned"]

    db.commit()
    del import_sessions[request.session_id]

    return schemas.VcfCommitResponse(
        households_created=households_created,
        households_updated=households_updated,
        households_skipped=households_skipped,
        persons_created=persons_created,
        persons_updated=persons_updated,
        persons_assigned=persons_assigned,
        created_household_ids=created_ids,
    )

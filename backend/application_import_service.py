# -*- coding: utf-8 -*-
"""Import der gepflegten Bewerbungsliste (.xlsx).

Vierter Import der Kette. Anders als die Fragebogen-Importe darf er
**Haushalte anlegen**: Wartepool-Bewerber wohnen noch nicht im Projekt, der
vCard-Import legt für sie deshalb keinen Haushalt an (er tut das nur bei
erkannter Wohnungsnummer). Ohne diese Ausnahme bliebe der halbe Wartepool
außerhalb des Tools. Vorhandene Personen ohne Haushalt werden dabei
vorgeschlagen, damit keine Dubletten zu den vCard-Personen entstehen.

Erwartete Spalten (Kopfzeile, Schreibweise der gepflegten Liste)::

    Haushalt | Typ | Aktueller Typ | Aktuelle Wohnung | (Wechsel-)Wunsch
             | Mail / Info von | Status | neue Wohnung | Kommentar

"Aktueller Typ" und "Aktuelle Wohnung" werden **nicht** gespeichert — beides
ergibt sich aus der Wohnungszuordnung des Haushalts. Sie dienen im Assistenten
nur dem Abgleich; eine Abweichung wird als Warnung ausgewiesen.
"""

import io
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from . import models, schemas, wishes as wishes_mod
from .import_service import (
    ImportSession,
    import_sessions,
    _cleanup_sessions,
    match_household,
    normalize_name,
    parse_date,
)

# --- Spalten ---------------------------------------------------------------

COLUMNS = {
    "household": ("haushalt",),
    "kind": ("typ",),
    "current_type": ("aktueller typ",),
    "current_unit": ("aktuelle wohnung",),
    "wish": ("(wechsel-)wunsch", "wechselwunsch", "wunsch", "(wechsel)wunsch"),
    "requested_at": ("mail / info von", "mail / info vom", "mail/info von", "mail / info"),
    "status": ("status",),
    "new_unit": ("neue wohnung",),
    "note": ("kommentar",),
}

_UNIT_NUMBER = re.compile(r"\b[A-Za-z]\.\d{3}(?:\.\d)?\b")


def _norm_header(value) -> str:
    """Reduziert einen Spaltennamen auf Buchstaben und Ziffern.

    Die gepflegte Liste schreibt ihre Kopfzeile nicht buchstabengetreu:
    „(Wechsel-) Wunsch" trägt ein Leerzeichen nach dem Bindestrich, „Mail /
    Info vom" wechselt zwischen „vom" und „von". Ein Vergleich, der an
    Leerzeichen und Satzzeichen hängt, verliert dann **stillschweigend eine
    ganze Spalte** — genau so blieb der Wunsch beim Import leer. Deshalb
    entscheidet nur die Buchstabenfolge.
    """
    return re.sub(r"[^0-9a-zäöüß]+", "", str(value or "").lower())


def _column_map(df: pd.DataFrame) -> dict[str, str]:
    """Ordnet die Spaltennamen der Datei den bekannten Feldern zu."""
    normalized = {
        field: tuple(_norm_header(a) for a in aliases)
        for field, aliases in COLUMNS.items()
    }
    found: dict[str, str] = {}
    for column in df.columns:
        key = _norm_header(column)
        if not key:
            continue
        for field, aliases in normalized.items():
            if field in found:
                continue
            if key in aliases or any(key.startswith(a) for a in aliases):
                found[field] = column
                break
    return found


def _cell(row, columns: dict, field: str) -> str:
    column = columns.get(field)
    if column is None:
        return ""
    value = row.get(column)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


# --- Parser ----------------------------------------------------------------

def parse_kind(raw) -> Optional[str]:
    """"Wechselwunsch" / "Wartepool" / "Joker" -> Bewerbungsart."""
    text = str(raw or "").strip().lower().replace("\n", " ")
    if not text:
        return None
    if "joker" in text:
        return "joker"
    if "wechsel" in text:
        return "wechselwunsch"
    if "warte" in text:
        return "wartepool"
    return None


def parse_status(raw) -> Optional[str]:
    """"offen" / "erfüllt" / "zurück-gezogen" -> Bewerbungsstatus."""
    text = str(raw or "").strip().lower().replace("\n", "").replace("-", "").replace(" ", "")
    if not text:
        return None
    if text.startswith("offen"):
        return "offen"
    if text.startswith("erf"):
        return "erfuellt"
    if "zurueck" in text or "zurück" in text or text.startswith("zuruck"):
        return "zurueckgezogen"
    return None


def split_person_names(raw: str) -> list[str]:
    """Zerlegt die Spalte "Haushalt" in einzelne Personennamen.

    "Christine (Tine) und Simon Langkamp" -> ["Christine Langkamp", "Simon Langkamp"].
    Ein Vorname ohne Nachnamen erbt den Nachnamen des letzten vollständigen
    Namens der Zelle — so schreibt die Liste Paare.
    """
    text = re.sub(r"\([^)]*\)", " ", str(raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"\s+und\s+|\s*&\s*|\s*/\s*|\s*,\s*", text) if p.strip()]

    # Nachnamen von hinten nach vorn ergänzen: der letzte Teil trägt ihn.
    surname = None
    for part in reversed(parts):
        tokens = part.split()
        if len(tokens) > 1:
            surname = tokens[-1]
            break

    names = []
    for part in parts:
        tokens = part.split()
        if len(tokens) == 1 and surname:
            names.append(f"{tokens[0]} {surname}")
        elif tokens:
            names.append(part)
    return names


def parse_row(row, columns: dict, index: int) -> Optional[dict]:
    """Eine Zeile der Liste -> Rohdaten einer Bewerbung."""
    raw_household = _cell(row, columns, "household")
    raw_kind = _cell(row, columns, "kind")
    raw_wish = _cell(row, columns, "wish")
    raw_status = _cell(row, columns, "status")
    if not raw_household and not raw_kind and not raw_wish:
        return None

    wish_list, unparsed = wishes_mod.parse_wish(raw_wish)
    kind = parse_kind(raw_kind) or "wartepool"
    # Ein reiner Joker-Wunsch ist eine Joker-Bewerbung, auch wenn die
    # Typ-Spalte etwas anderes sagt.
    if kind != "joker" and wish_list and all(
        w.get("apartment_category") == wishes_mod.CATEGORY_JOKER for w in wish_list
    ):
        kind = "joker"

    requested = parse_date(_cell(row, columns, "requested_at"))
    names = split_person_names(raw_household)

    return {
        "temp_id": str(uuid.uuid4()),
        "row": index,
        "raw_household": raw_household,
        "person_names": names,
        "kind": kind,
        "raw_kind": raw_kind or None,
        "requested_at": datetime(requested.year, requested.month, requested.day) if requested else None,
        "wishes": wish_list,
        "unparsed_wishes": unparsed,
        "status": parse_status(raw_status) or "offen",
        "raw_status": raw_status or None,
        "note": _cell(row, columns, "note") or None,
        "raw_current_type": _cell(row, columns, "current_type") or None,
        "raw_current_unit": _normalize_unit(_cell(row, columns, "current_unit")),
        "raw_new_unit": _normalize_unit(_cell(row, columns, "new_unit")),
    }


def _normalize_unit(raw: str) -> Optional[str]:
    match = _UNIT_NUMBER.search(raw or "")
    return match.group(0).upper() if match else None


def parse_application_list(file_contents: bytes) -> dict:
    df = pd.read_excel(io.BytesIO(file_contents))
    columns = _column_map(df)
    if "household" not in columns:
        raise ValueError(
            "Spalte \"Haushalt\" nicht gefunden. Erwartet werden die Spalten der "
            "gepflegten Bewerbungsliste."
        )

    rows = []
    skipped_empty = 0
    for index, row in df.iterrows():
        parsed = parse_row(row, columns, int(index) + 2)  # +2: Kopfzeile und 1-basiert
        if parsed is None:
            skipped_empty += 1
            continue
        rows.append(parsed)
    return {"rows": rows, "total_rows": len(df), "skipped_empty": skipped_empty}


# --- Analyse ---------------------------------------------------------------

def _current_occupant(unit: str | None, db: Session) -> models.Household | None:
    """Haushalt, der **heute** in dieser Wohnung wohnt."""
    if not unit:
        return None
    apartment = (
        db.query(models.Apartment)
        .filter(models.Apartment.unit_number == unit)
        .first()
    )
    return apartment.household if apartment is not None else None


def _match_by_household_name(raw: dict, db: Session) -> schemas.MatchResult | None:
    """Fällt auf den Haushaltsnamen zurück (z. B. "Familie Meier").

    Nur ein **eindeutiger** Namensgleichstand zählt als sichere Zuordnung: der
    Name muss genau übereinstimmen und darf im Bestand nur einmal vorkommen.
    Alles andere bleibt ein Vorschlag.
    """
    wanted = (raw.get("raw_household") or "").strip().lower()
    if not wanted:
        return None

    households = db.query(models.Household).all()
    identical = [hh for hh in households if (hh.name or "").strip().lower() == wanted]
    if len(identical) == 1:
        return schemas.MatchResult(
            type="exact_household_name",
            matched_household_id=identical[0].id,
            matched_household_name=identical[0].name,
            confidence=1.0,
        )

    best, best_score = None, 0.0
    for hh in households:
        score = SequenceMatcher(None, wanted, (hh.name or "").lower()).ratio()
        if score > best_score:
            best, best_score = hh, score
    if best is not None and best_score >= 0.8:
        return schemas.MatchResult(
            type="household_name",
            matched_household_id=best.id,
            matched_household_name=best.name,
            confidence=round(best_score, 3),
        )
    return None


def _match_row(raw: dict, db: Session) -> schemas.MatchResult:
    """Findet den Haushalt zur Zeile.

    **Der Name der Spalte "Haushalt" benennt den Bewerber, die Wohnungsnummer
    bestätigt ihn nur.** Die Reihenfolge ist wichtig: Die Spalte "Aktuelle
    Wohnung" hält den Stand zum Zeitpunkt der Bewerbung fest. Bei einer
    erfüllten Zeile ist der Haushalt längst ausgezogen, und in der genannten
    Wohnung wohnt inzwischen jemand anderes — wer heute dort wohnt, ist dann
    gerade **nicht** der Bewerber.

    Deshalb:

    1. Namenstreffer **und** aktueller Bewohner sind derselbe Haushalt: sicher.
    2. Eindeutiger Namenstreffer (Mitgliedsnummer, exakter Name, eindeutiger
       Haushaltsname): sicher.
    3. In der Wohnung wohnt jemand, dessen Name nicht zur Zeile passt: das ist
       ein **Hinweis**, keine Zuordnung (``apartment_occupant``) — etwa wenn
       jemand unter anderem Namen geführt wird. Ein Mensch entscheidet.
    4. Sonst der unscharfe Namensvorschlag bzw. kein Treffer.
    """
    persons = []
    for name in raw.get("person_names", []):
        first_name, last_name = normalize_name(name)
        persons.append({"first_name": first_name, "last_name": last_name, "name": name})
    by_person = match_household({"persons": persons}, db)
    if not by_person.is_certain:
        # Hat der Haushalt keine Personen, vergleicht ``match_household`` bereits
        # gegen den Haushaltsnamen -- aber als unscharfen Treffer. Eine exakte,
        # im Bestand eindeutige Namensgleichheit ist mehr als das.
        by_name = _match_by_household_name(raw, db)
        if by_name is not None and (by_name.is_certain
                                    or by_person.matched_household_id is None):
            by_person = by_name.model_copy(
                update={"fuzzy_candidates": by_person.fuzzy_candidates}
            )

    occupant = _current_occupant(raw.get("raw_current_unit"), db)

    if occupant is not None and by_person.matched_household_id == occupant.id:
        return schemas.MatchResult(
            type="apartment_unit",
            matched_household_id=occupant.id,
            matched_household_name=occupant.name,
            confidence=1.0,
            fuzzy_candidates=by_person.fuzzy_candidates,
        )

    if by_person.is_certain:
        return by_person

    if occupant is not None:
        return schemas.MatchResult(
            type="apartment_occupant",
            matched_household_id=occupant.id,
            matched_household_name=occupant.name,
            confidence=0.5,
            fuzzy_candidates=by_person.fuzzy_candidates,
        )
    return by_person


def _find_existing_application(
    household_id: int, raw: dict, db: Session, claimed: set[int] | None = None
) -> models.Application | None:
    """Die Bewerbung, die diese Zeile der Liste bereits beschreibt — falls vorhanden.

    Die Liste wird weiter außerhalb gepflegt und wiederholt eingelesen. Würde
    nur eine **offene** Bewerbung als vorhanden gelten, erzeugte jeder erneute
    Import für jede erfüllte oder zurückgezogene Zeile eine Dublette. Als
    Kennung dient deshalb Haushalt + Art + Zeitpunkt des Wunsches („Mail / Info
    von") — die Angaben, über die die Liste eine Bewerbung selbst identifiziert.

    Der Status entscheidet nur als Feinheit: Zuerst zählt die Bewerbung mit
    demselben Status (ein Haushalt kann mehrere erledigte Bewerbungen ohne Datum
    haben), erst danach dieselbe Kennung mit abweichendem Status — sonst würde
    eine Zeile, die in der Liste von „offen" auf „erfüllt" gewandert ist, als
    neue Bewerbung gelten.

    ``claimed`` sind die Bewerbungen, die in diesem Durchlauf schon einer Zeile
    zugeschlagen wurden. Ohne diese Sperre würden mehrere gleichartige Zeilen
    desselben Haushalts **ohne Datum** dieselbe Bewerbung überschreiben und sich
    dabei gegenseitig auslöschen; so entsteht für die zweite Zeile stattdessen
    eine zweite Bewerbung — was sie ja auch ist.

    Fällt der Zeitpunkt weg, greift zuletzt die offene Bewerbung derselben Art:
    so findet die Zeile auch die Bewerbung, die der Haushaltsbogen angelegt hat.
    """
    claimed = claimed or set()
    candidates = [
        application
        for application in (
            db.query(models.Application)
            .filter(models.Application.household_id == household_id)
            .filter(models.Application.kind == raw["kind"])
            .filter(models.Application.archived == False)  # noqa: E712
            .order_by(models.Application.id)
            .all()
        )
        if application.id not in claimed
    ]
    wanted = raw.get("requested_at")

    def same_requested_at(application: models.Application) -> bool:
        existing = application.requested_at
        if wanted is None or existing is None:
            return wanted is None and existing is None
        return existing.date() == wanted.date()

    for application in candidates:
        if same_requested_at(application) and application.status == raw["status"]:
            return application
    for application in candidates:
        if same_requested_at(application):
            return application
    for application in candidates:
        if application.status == "offen":
            return application
    return None


def _person_candidates(raw: dict, db: Session) -> list[schemas.ApplicationPersonCandidate]:
    """Vorhandene Personen ohne Haushalt, die zu den Namen der Zeile passen.

    So entstehen beim Anlegen eines Haushalts keine Dubletten zu den Personen,
    die der vCard-Import bereits angelegt hat.
    """
    names = raw.get("person_names") or []
    if not names:
        return []
    unassigned = (
        db.query(models.Person)
        .filter(models.Person.household_id.is_(None))
        .filter(models.Person.archived == False)
        .all()
    )
    candidates = []
    for person in unassigned:
        full = f"{person.first_name or ''} {person.last_name or ''}".strip().lower()
        if not full:
            continue
        score = max(SequenceMatcher(None, name.lower(), full).ratio() for name in names)
        if score >= 0.75:
            candidates.append(schemas.ApplicationPersonCandidate(
                person_id=person.id,
                name=f"{person.first_name} {person.last_name}".strip(),
                member_number=person.member_number,
                score=round(score, 3),
            ))
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:10]


def analyze_application_list(file_contents: bytes, db: Session) -> schemas.ApplicationAnalysisResponse:
    _cleanup_sessions()
    parsed = parse_application_list(file_contents)

    known_units = {
        row[0] for row in db.query(models.Apartment.unit_number).all() if row[0]
    }

    previews = []
    # Jede vorhandene Bewerbung gehört zu höchstens einer Zeile der Liste.
    claimed: set[int] = set()
    for raw in parsed["rows"]:
        match_result = _match_row(raw, db)

        existing_id = None
        apartment_mismatch = False
        if match_result.matched_household_id:
            hh = db.query(models.Household).get(match_result.matched_household_id)
            if hh:
                existing = _find_existing_application(hh.id, raw, db, claimed)
                if existing is not None:
                    existing_id = existing.id
                    # Belegt wird nur, was auch ohne Rückfrage aktualisiert
                    # wird. Eine Zeile mit unsicherem Treffer entscheidet ein
                    # Mensch -- sie darf der nächsten Zeile nicht vorweg die
                    # Bewerbung wegnehmen.
                    if match_result.is_certain:
                        claimed.add(existing.id)
                # Welche Wohnung die Zeile für den Haushalt behauptet: bei einer
                # erfüllten Bewerbung die neue, sonst die aktuelle. Sonst wäre
                # jeder erfüllte Wechsel fälschlich eine Abweichung.
                listed = (
                    raw.get("raw_new_unit") if raw.get("status") == "erfuellt"
                    else raw.get("raw_current_unit")
                ) or raw.get("raw_current_unit")
                if listed and hh.assigned_apartment_unit and listed != hh.assigned_apartment_unit:
                    apartment_mismatch = True

        unknown_apartment = any(
            unit and unit not in known_units
            for unit in (raw.get("raw_current_unit"), raw.get("raw_new_unit"))
        )

        previews.append(schemas.ApplicationImportPreview(
            temp_id=raw["temp_id"],
            row=raw["row"],
            raw_household=raw["raw_household"],
            kind=raw["kind"],
            raw_kind=raw["raw_kind"],
            requested_at=raw["requested_at"].date().isoformat() if raw["requested_at"] else None,
            wishes=[schemas.ApplicationWish(**w) for w in raw["wishes"]],
            unparsed_wishes=raw["unparsed_wishes"],
            status=raw["status"],
            raw_status=raw["raw_status"],
            note=raw["note"],
            raw_current_type=raw["raw_current_type"],
            raw_current_unit=raw["raw_current_unit"],
            raw_new_unit=raw["raw_new_unit"],
            match_result=match_result,
            apartment_mismatch=apartment_mismatch,
            unknown_apartment=unknown_apartment,
            existing_application_id=existing_id,
            person_candidates=(
                [] if match_result.matched_household_id else _person_candidates(raw, db)
            ),
            suggested_household_name=raw["raw_household"],
        ))

    session = ImportSession("applications", parsed["rows"], {})
    import_sessions[session.id] = session

    return schemas.ApplicationAnalysisResponse(
        session_id=session.id,
        total_rows=parsed["total_rows"],
        skipped_empty=parsed["skipped_empty"],
        households=previews,
    )


# --- Commit ----------------------------------------------------------------

def commit_application_list(
    request: schemas.ApplicationCommitRequest,
    db: Session,
) -> schemas.ApplicationCommitResponse:
    session = import_sessions.get(request.session_id)
    if not session:
        raise ValueError("Import-Session nicht gefunden oder abgelaufen")

    raw_map = {r["temp_id"]: r for r in session.raw_data}
    response = schemas.ApplicationCommitResponse()
    # Wie in der Analyse: keine Bewerbung wird von zwei Zeilen überschrieben.
    claimed: set[int] = set()

    for decision in request.decisions:
        raw = raw_map.get(decision.temp_id)
        # Nur die bekannten Aktionen wirken; eine im Assistenten nicht
        # entschiedene Zeile wird übersprungen.
        if raw is None or decision.action not in ("update", "create", "create_household"):
            response.skipped += 1
            continue

        household = None
        if decision.action == "create_household":
            household = _create_household(decision, raw, db, response)
        elif decision.target_household_id:
            household = db.query(models.Household).get(decision.target_household_id)

        if household is None:
            response.skipped_no_match += 1
            continue

        application = None
        if decision.action == "update":
            application = _find_existing_application(household.id, raw, db, claimed)
            if application is not None:
                claimed.add(application.id)

        if application is None:
            application = models.Application(
                household_id=household.id,
                created_at=datetime.utcnow(),
            )
            db.add(application)
            response.applications_created += 1
        else:
            response.applications_updated += 1

        _apply_raw(application, raw, db)

    db.commit()
    del import_sessions[request.session_id]
    return response


def _create_household(
    decision: schemas.ApplicationDecision,
    raw: dict,
    db: Session,
    response: schemas.ApplicationCommitResponse,
) -> models.Household:
    """Legt den Haushalt der Zeile an und ordnet die gewählten Personen zu."""
    household = models.Household(
        name=(decision.household_name or raw["raw_household"] or "Unbenannt").strip(),
        import_source="Bewerbungsliste",
        updated_at=datetime.utcnow(),
    )
    db.add(household)
    db.flush()
    response.households_created += 1
    response.created_household_ids.append(household.id)

    assigned = 0
    for person_id in decision.person_ids:
        person = db.query(models.Person).get(person_id)
        if person is None or person.household_id is not None:
            continue
        person.household_id = household.id
        person.updated_at = datetime.utcnow()
        assigned += 1
    response.persons_assigned += assigned
    household.household_member_count = assigned or None
    return household


def _apply_raw(application: models.Application, raw: dict, db: Session) -> None:
    application.kind = raw["kind"]
    application.requested_at = raw["requested_at"]
    application.wishes = wishes_mod.normalize_wishes(raw["wishes"])
    application.status = raw["status"]
    application.note = raw["note"]
    # Die Kommentarspalte trägt die Gründe, aus denen von der Regel abgewichen
    # werden soll. Ob das zutrifft, entscheidet ein Mensch — der Import setzt
    # das Kennzeichen deshalb nicht selbst, sondern übernimmt nur den Text.
    application.updated_at = datetime.utcnow()

    if raw["status"] == "erfuellt" and raw.get("raw_new_unit"):
        apartment = (
            db.query(models.Apartment)
            .filter(models.Apartment.unit_number == raw["raw_new_unit"])
            .first()
        )
        if apartment:
            application.fulfilled_apartment_id = apartment.id
            application.fulfilled_at = application.fulfilled_at or raw["requested_at"]

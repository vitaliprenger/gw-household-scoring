import re
import uuid
import io
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from . import models, schemas

# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

class ImportSession:
    def __init__(self, session_type: str, raw_data: list[dict], analysis: dict):
        self.id = str(uuid.uuid4())
        self.session_type = session_type
        self.raw_data = raw_data
        self.analysis = analysis
        self.created_at = datetime.utcnow()

import_sessions: dict[str, ImportSession] = {}

SESSION_TTL = timedelta(minutes=30)

def _cleanup_sessions():
    now = datetime.utcnow()
    expired = [k for k, v in import_sessions.items() if now - v.created_at > SESSION_TTL]
    for k in expired:
        del import_sessions[k]

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def normalize_name(raw: str) -> tuple[str, str]:
    if not raw or not raw.strip():
        return ("", "")
    raw = raw.strip()
    # Replace semicolon or period acting as separator
    if ";" in raw:
        raw = raw.replace(";", ",", 1)
    elif "." in raw and "," not in raw:
        parts = raw.split(".", 1)
        if len(parts) == 2 and len(parts[0].strip()) > 1 and len(parts[1].strip()) > 1:
            raw = f"{parts[0].strip()}, {parts[1].strip()}"

    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        last_name = parts[0]
        first_name = parts[1] if len(parts) > 1 else ""
    else:
        tokens = raw.split()
        if len(tokens) == 1:
            return (tokens[0], "")
        first_name = tokens[0]
        last_name = " ".join(tokens[1:])

    return (first_name.strip(), last_name.strip())


def normalize_member_number(raw) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    digits = re.findall(r"\d+", s)
    if digits:
        return digits[0]
    return None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date(raw) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    # Excel serial number
    if s.isdigit() and len(s) <= 6:
        try:
            serial = int(s)
            if 1 < serial < 100000:
                return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
        except Exception:
            pass
    # ISO format YYYY-MM-DD (possibly with time)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    # German format DD.MM.YYYY
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except Exception:
        pass
    return None


def parse_timestamp(raw) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    # With timezone offset
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # Try just date
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# HH-Bogen parsing
# ---------------------------------------------------------------------------

SUBMIT_PREFIXES = ("ja", "Ja")

def _is_submitted(val) -> bool:
    if val is None:
        return False
    return str(val).strip().lower().startswith("ja")

def _has_privacy_consent(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return "klar" in s or "akzeptiere" in s or len(s) > 10

def _normalize_wbs(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    low = s.lower()
    if "kein" in low:
        return "kein WBS"
    if "einkommensgruppe a" in low:
        return "WBS Einkommensgruppe A"
    if "einkommensgruppe b" in low:
        return "WBS Einkommensgruppe B"
    return s

def _normalize_financial(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    low = s.lower()
    if "problem" in low or "nicht" in low:
        return "kann Anteile nicht übernehmen"
    return "kann Anteile übernehmen"

APARTMENT_TYPE_OPTIONS = [
    "Standard Wohnungstypen",
    "Clusterwohnung",
    "Ausbauwohnung",
    "Atelierwohnung",
    "Gartencluster",
]

def _parse_apartment_types(val) -> list[str] | None:
    if val is None:
        return None
    raw = str(val).strip()
    if not raw:
        return None
    parts = [p.strip() for p in re.split(r"[,;]+", raw) if p.strip()]
    return parts if parts else None

def _parse_wheelchair(val) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() == "ja"

def _parse_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def parse_household_bogen(file_contents: bytes) -> dict:
    df = pd.read_excel(io.BytesIO(file_contents), dtype=str, keep_default_na=False)
    cols = list(df.columns)
    is_old_format = len(cols) >= 36 and "Dublette" in cols

    total_rows = len(df)
    skipped_not_submitted = 0
    skipped_duplicates = 0
    privacy_warnings: list[dict] = []
    parsed: list[dict] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # Excel row (1-indexed header + data)

        # Skip Dubletten in old format
        if is_old_format:
            dub_val = row.get("Dublette", "")
            if str(dub_val).strip() == "Dublette":
                skipped_duplicates += 1
                continue

        # Skip not submitted
        submit_val = row.get("Absenden?", "")
        if not _is_submitted(submit_val):
            skipped_not_submitted += 1
            continue

        # Privacy check — old format has empty privacy column, treat as consented
        privacy_col = "Datenschutzhinweis" if "Datenschutzhinweis" in cols else "Datenschutz"
        privacy_val = str(row.get(privacy_col, "")).strip()
        if not privacy_val and is_old_format:
            pass
        elif privacy_val and not _has_privacy_consent(privacy_val):
            p1_name = str(row.get("Person 1 (Name)", "")).strip()
            privacy_warnings.append({"row": row_num, "name": p1_name})
            continue

        timestamp_str = str(row.get("Zeitstempel", "")).strip()
        timestamp = parse_timestamp(timestamp_str)

        # Parse persons 1-6
        persons = []
        for i in range(1, 7):
            name_col = f"Person {i} (Name)"
            nr_col = f"Person {i} (Mitgliedsnummer)"
            dob_col = f"Person {i} (Geburtsdatum)"
            name_raw = str(row.get(name_col, "")).strip()
            if not name_raw:
                continue
            first_name, last_name = normalize_name(name_raw)
            member_nr = normalize_member_number(row.get(nr_col, ""))
            dob = parse_date(row.get(dob_col, ""))
            persons.append({
                "name": name_raw,
                "first_name": first_name,
                "last_name": last_name,
                "member_number": member_nr,
                "birth_date": dob.isoformat() if dob else None,
            })

        declared_count = _parse_int(row.get("Haushaltsmitglieder", "0"))

        parsed.append({
            "temp_id": str(uuid.uuid4()),
            "timestamp_str": timestamp_str,
            "timestamp": timestamp,
            "wbs_status": _normalize_wbs(row.get("Wohnberechtigungsschein", "")),
            "financial_status": _normalize_financial(row.get("Finanzielle Rahmenbedingungen", "")),
            "declared_member_count": declared_count,
            "wheelchair_accessible": _parse_wheelchair(row.get("Rollstuhlgerecht?", "")),
            "desired_apartment_type": _parse_apartment_types(row.get("Wohnungsart", "")),
            "desired_apartment_size": str(row.get("Wohnungsgröße", "")).strip() or None,
            "pets_count": _parse_int(row.get("Haustiere 1", "0")),
            "pets_info": str(row.get("Haustiere 2", "")).strip() or None,
            "persons": persons,
        })

    # Deduplicate: group by Person 1 name (normalized), keep newest
    deduped = _deduplicate_hh(parsed)

    return {
        "total_rows": total_rows,
        "skipped_not_submitted": skipped_not_submitted,
        "skipped_duplicates": skipped_duplicates,
        "privacy_warnings": privacy_warnings,
        "households": deduped,
    }


def _deduplicate_hh(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        if not row["persons"]:
            continue
        p1 = row["persons"][0]
        key = (p1.get("first_name", "") + " " + p1.get("last_name", "")).strip().lower()
        if p1.get("member_number"):
            key = f"nr_{p1['member_number']}"
        groups.setdefault(key, []).append(row)

    result = []
    for key, items in groups.items():
        items.sort(key=lambda r: r["timestamp"] or datetime.min, reverse=True)
        result.append(items[0])
    return result


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_household(hh_data: dict, db: Session) -> schemas.MatchResult:
    persons = hh_data.get("persons", [])
    all_households = db.query(models.Household).all()

    # Step 1: Exact match on member number
    for p in persons:
        if not p.get("member_number"):
            continue
        matched_person = (
            db.query(models.Person)
            .filter(models.Person.member_number == p["member_number"])
            .first()
        )
        if matched_person and matched_person.household_id:
            hh = db.query(models.Household).get(matched_person.household_id)
            if hh:
                return schemas.MatchResult(
                    type="exact_member_nr",
                    matched_household_id=hh.id,
                    matched_household_name=hh.name,
                    confidence=1.0,
                )

    # Step 2: Exact match on normalized name + birth date
    for p in persons:
        fn = (p.get("first_name") or "").strip().lower()
        ln = (p.get("last_name") or "").strip().lower()
        dob_str = p.get("birth_date")
        if not fn or not ln:
            continue
        for hh in all_households:
            for db_person in hh.people:
                db_fn = (db_person.first_name or "").strip().lower()
                db_ln = (db_person.last_name or "").strip().lower()
                name_match = (fn == db_fn and ln == db_ln) or (fn == db_ln and ln == db_fn)
                if not name_match:
                    continue
                if dob_str and db_person.birth_date:
                    db_dob = db_person.birth_date.date() if isinstance(db_person.birth_date, datetime) else db_person.birth_date
                    try:
                        import_dob = date.fromisoformat(dob_str)
                        if import_dob == db_dob:
                            return schemas.MatchResult(
                                type="exact_name_dob",
                                matched_household_id=hh.id,
                                matched_household_name=hh.name,
                                confidence=1.0,
                            )
                    except Exception:
                        pass
                elif name_match and not dob_str:
                    return schemas.MatchResult(
                        type="exact_name_dob",
                        matched_household_id=hh.id,
                        matched_household_name=hh.name,
                        confidence=0.9,
                    )

    # Step 3: Fuzzy matching
    candidates = _fuzzy_match(persons, all_households)
    top = candidates[0] if candidates else None
    return schemas.MatchResult(
        type="fuzzy" if top else "none",
        matched_household_id=top.household_id if top else None,
        matched_household_name=top.name if top else None,
        confidence=top.score if top else 0.0,
        fuzzy_candidates=candidates[:10],
    )


def _fuzzy_match(persons: list[dict], all_households: list[models.Household]) -> list[schemas.FuzzyCandidate]:
    import_names = " ".join(
        f"{p.get('first_name', '')} {p.get('last_name', '')}" for p in persons
    ).strip().lower()

    candidates = []
    for hh in all_households:
        hh_names = " ".join(
            f"{p.first_name or ''} {p.last_name or ''}" for p in hh.people
        ).strip().lower()
        if not hh_names:
            hh_names = (hh.name or "").lower()

        score = SequenceMatcher(None, import_names, hh_names).ratio()

        member_nrs = [p.member_number for p in hh.people if p.member_number]
        for p in persons:
            if p.get("member_number") and p["member_number"] in member_nrs:
                score = max(score, 0.8)

        candidates.append(schemas.FuzzyCandidate(
            household_id=hh.id,
            name=hh.name,
            score=round(score, 3),
            member_numbers=member_nrs,
        ))

    candidates = [c for c in candidates if c.score >= 0.7]
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Diff detection
# ---------------------------------------------------------------------------

FIELD_LABELS = {
    "wbs_status": "WBS-Status",
    "pets_count": "Haustiere (Anzahl)",
    "pets_info": "Haustiere (Info)",
    "desired_apartment_size": "Gewünschte Wohnungsgröße",
    "desired_apartment_type": "Wohnungsart",
    "wheelchair_accessible": "Rollstuhlgerecht?",
    "financial_status": "Finanzielle Rahmenbedingungen",
    "household_member_count": "Deklarierte Mitglieder",
}

def compute_data_changes(new_data: dict, existing: models.Household) -> Optional[schemas.ExistingDataChanges]:
    overwrites = []
    removals = []

    mapping = {
        "wbs_status": new_data.get("wbs_status"),
        "pets_count": new_data.get("pets_count"),
        "pets_info": new_data.get("pets_info"),
        "desired_apartment_size": new_data.get("desired_apartment_size"),
        "desired_apartment_type": new_data.get("desired_apartment_type"),
        "wheelchair_accessible": new_data.get("wheelchair_accessible"),
        "financial_status": new_data.get("financial_status"),
        "household_member_count": new_data.get("declared_member_count"),
    }

    def _display(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val)

    for field, new_val in mapping.items():
        old_val = getattr(existing, field, None)
        label = FIELD_LABELS.get(field, field)

        if old_val is not None and new_val is not None and _display(old_val) != _display(new_val):
            overwrites.append(schemas.DataChange(
                field=label, old_value=_display(old_val), new_value=_display(new_val)
            ))
        elif old_val is not None and (new_val is None or new_val == "" or new_val == 0 or new_val == []):
            if field in ("pets_count",) and old_val == 0:
                continue
            removals.append(schemas.DataChange(
                field=label, old_value=_display(old_val)
            ))

    if not overwrites and not removals:
        return None
    return schemas.ExistingDataChanges(
        fields_to_overwrite=overwrites,
        data_removals=removals,
    )


# ---------------------------------------------------------------------------
# HH Analyze
# ---------------------------------------------------------------------------

def analyze_household_bogen(file_contents: bytes, db: Session) -> schemas.HHAnalysisResponse:
    _cleanup_sessions()
    parsed = parse_household_bogen(file_contents)

    previews = []
    for hh_data in parsed["households"]:
        match_result = match_household(hh_data, db)

        # Check timestamp
        already_imported = False
        if match_result.matched_household_id:
            existing = db.query(models.Household).get(match_result.matched_household_id)
            if existing and existing.import_timestamp and hh_data.get("timestamp"):
                if existing.import_timestamp == hh_data["timestamp"]:
                    already_imported = True

        # Diff
        data_changes = None
        if match_result.matched_household_id and not already_imported:
            existing = db.query(models.Household).get(match_result.matched_household_id)
            if existing:
                data_changes = compute_data_changes(hh_data, existing)

        member_count_mismatch = (
            hh_data["declared_member_count"] > 0
            and len(hh_data["persons"]) != hh_data["declared_member_count"]
        )

        previews.append(schemas.HouseholdImportPreview(
            temp_id=hh_data["temp_id"],
            timestamp=hh_data.get("timestamp_str", ""),
            wbs_status=hh_data.get("wbs_status"),
            financial_status=hh_data.get("financial_status"),
            declared_member_count=hh_data.get("declared_member_count", 0),
            wheelchair_accessible=hh_data.get("wheelchair_accessible", False),
            desired_apartment_type=hh_data.get("desired_apartment_type"),
            desired_apartment_size=hh_data.get("desired_apartment_size"),
            pets_count=hh_data.get("pets_count", 0),
            pets_info=hh_data.get("pets_info"),
            persons=[schemas.ImportPersonPreview(**p) for p in hh_data["persons"]],
            match_result=match_result,
            member_count_mismatch=member_count_mismatch,
            already_imported=already_imported,
            existing_data_changes=data_changes,
        ))

    session = ImportSession("household", parsed["households"], {})
    import_sessions[session.id] = session

    return schemas.HHAnalysisResponse(
        session_id=session.id,
        total_rows=parsed["total_rows"],
        skipped_not_submitted=parsed["skipped_not_submitted"],
        skipped_duplicates=parsed["skipped_duplicates"],
        privacy_warnings=[schemas.PrivacyWarning(**w) for w in parsed["privacy_warnings"]],
        households=previews,
    )


# ---------------------------------------------------------------------------
# HH Commit
# ---------------------------------------------------------------------------

def commit_household_bogen(request: schemas.HHCommitRequest, db: Session) -> schemas.HHCommitResponse:
    session = import_sessions.get(request.session_id)
    if not session:
        raise ValueError("Import-Session nicht gefunden oder abgelaufen")

    raw_map = {r["temp_id"]: r for r in session.raw_data}

    imported = 0
    updated = 0
    skipped = 0
    created_ids = []

    for dec in request.decisions:
        if dec.action == "skip":
            skipped += 1
            continue

        raw = raw_map.get(dec.temp_id)
        if not raw:
            skipped += 1
            continue

        if dec.action == "create":
            hh = _create_household_from_raw(raw, db)
            created_ids.append(hh.id)
            imported += 1

        elif dec.action == "update" and dec.target_household_id:
            existing = db.query(models.Household).get(dec.target_household_id)
            if existing:
                _update_household_from_raw(existing, raw, db)
                updated += 1
            else:
                hh = _create_household_from_raw(raw, db)
                created_ids.append(hh.id)
                imported += 1

    db.commit()

    del import_sessions[request.session_id]

    return schemas.HHCommitResponse(
        imported=imported,
        updated=updated,
        skipped=skipped,
        created_household_ids=created_ids,
    )


def _create_household_from_raw(raw: dict, db: Session) -> models.Household:
    p1 = raw["persons"][0] if raw["persons"] else {}
    name = f"{p1.get('first_name', '')} {p1.get('last_name', '')}".strip() or "Unbekannt"

    hh = models.Household(
        name=name,
        wbs_status=raw.get("wbs_status"),
        pets_count=raw.get("pets_count", 0),
        pets_info=raw.get("pets_info"),
        desired_apartment_size=raw.get("desired_apartment_size"),
        desired_apartment_type=raw.get("desired_apartment_type"),
        wheelchair_accessible=raw.get("wheelchair_accessible", False),
        financial_status=raw.get("financial_status"),
        import_timestamp=raw.get("timestamp"),
        import_source="HH-Fragebogen",
        household_member_count=raw.get("declared_member_count"),
    )
    db.add(hh)
    db.flush()

    for p_data in raw["persons"]:
        dob = parse_date(p_data.get("birth_date"))
        person = models.Person(
            household_id=hh.id,
            first_name=p_data.get("first_name", ""),
            last_name=p_data.get("last_name", ""),
            birth_date=datetime(dob.year, dob.month, dob.day) if dob else None,
            member_number=p_data.get("member_number"),
        )
        db.add(person)

    return hh


def _update_household_from_raw(hh: models.Household, raw: dict, db: Session):
    hh.wbs_status = raw.get("wbs_status")
    hh.pets_count = raw.get("pets_count", 0)
    hh.pets_info = raw.get("pets_info")
    hh.desired_apartment_size = raw.get("desired_apartment_size")
    hh.desired_apartment_type = raw.get("desired_apartment_type")
    hh.wheelchair_accessible = raw.get("wheelchair_accessible", False)
    hh.financial_status = raw.get("financial_status")
    hh.import_timestamp = raw.get("timestamp")
    hh.import_source = "HH-Fragebogen"
    hh.household_member_count = raw.get("declared_member_count")

    existing_persons = {
        (p.first_name or "").lower() + "|" + (p.last_name or "").lower(): p
        for p in hh.people
    }

    for p_data in raw["persons"]:
        fn = (p_data.get("first_name") or "").lower()
        ln = (p_data.get("last_name") or "").lower()
        key = fn + "|" + ln

        dob = parse_date(p_data.get("birth_date"))
        dob_dt = datetime(dob.year, dob.month, dob.day) if dob else None

        if key in existing_persons:
            ep = existing_persons[key]
            if p_data.get("member_number"):
                ep.member_number = p_data["member_number"]
            if dob_dt:
                ep.birth_date = dob_dt
        else:
            person = models.Person(
                household_id=hh.id,
                first_name=p_data.get("first_name", ""),
                last_name=p_data.get("last_name", ""),
                birth_date=dob_dt,
                member_number=p_data.get("member_number"),
            )
            db.add(person)


# ---------------------------------------------------------------------------
# Individual-Bogen parsing
# ---------------------------------------------------------------------------

OCCUPATION_MAPPING = {
    "Organisation, Verwaltung, Recht, Buchhaltung": "1",
    "Pädagogik, Psychologie, Soziales, Gesundheit, Lehre": "2",
    "Geistes-, Gesellschafts-, Wirtschaftswissenschaft": "3",
    "Handwerk": "4",
    "Dienstleistung": "5",
    "Kunst und Kultur, Unterhaltung, Medien": "6",
    "Landwirtschaft, Gartenbau, Tier-, Forstwirtschaft": "7",
    "Architektur, Bauplanung": "8",
    "Naturwissenschaft, Geographie, Informatik, Technik": "9",
    "Verkehr, Logistik, Schutz, Sicherheit": "10",
    "Schüler*in, (noch) keine Zuordnung möglich": "0",
}

GENDER_MAPPING = {
    "männlich": "m",
    "weiblich": "f",
    "divers": "d",
    "male": "m",
    "female": "f",
    "m": "m",
    "f": "f",
    "d": "d",
    "w": "f",
}

EDUCATION_MAPPING = {
    "Berufsausbildungsvorbereitung": "1",
    "Hauptschulabschluss": "2",
    "Zweijährige Berufsausbildung, Mittlerer Schulabschluss": "3",
    "Dreijährige Berufsausbildung, Hochschulreife (inkl. Fachabitur)": "4",
    "Erste berufliche Fortbildungsqualifikation": "5",
    "Bachelor, FH-Diplom, Staatsexamen, Fachwirt, Operativer Professional, Meister, Fachschule, Berufsakademie": "6",
    "Master, Uni-Diplom, Magister, Staatsexamen, Betriebswirt, Strategischer Professional": "7",
    "Promotion": "8",
    "Keine Antwort": "0",
}


def parse_individual_bogen(file_contents: bytes) -> dict:
    df = pd.read_excel(io.BytesIO(file_contents), dtype=str, keep_default_na=False)
    cols = list(df.columns)
    is_old_format = "Benutzer-ID" in cols or "Quellreiter" in cols

    total_rows = len(df)
    skipped_not_submitted = 0
    privacy_warnings: list[dict] = []
    parsed: list[dict] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2

        if not _is_submitted(row.get("Absenden?", "")):
            skipped_not_submitted += 1
            continue

        privacy_col = "Datenschutz"
        if privacy_col in df.columns:
            privacy_val = str(row.get(privacy_col, "")).strip()
            if not privacy_val and is_old_format:
                pass
            elif privacy_val and not _has_privacy_consent(privacy_val):
                name = str(row.get("Nachname, Vorname", "")).strip()
                privacy_warnings.append({"row": row_num, "name": name})
                continue

        name_raw = str(row.get("Nachname, Vorname", "")).strip()
        first_name, last_name = normalize_name(name_raw)
        member_nr = normalize_member_number(row.get("Mitgliedsnummer", ""))
        dob = parse_date(row.get("Geburtsdatum", ""))
        timestamp_str = str(row.get("Zeitstempel", "")).strip()
        timestamp = parse_timestamp(timestamp_str)

        gender_raw = str(row.get("Geschlecht", "")).strip().lower()
        gender = GENDER_MAPPING.get(gender_raw, gender_raw if gender_raw else None)

        occupation_raw = str(row.get("Berufe", "")).strip()
        occupation = OCCUPATION_MAPPING.get(occupation_raw, occupation_raw if occupation_raw else None)

        education_raw = str(row.get("Bildungsabschluss", "")).strip()
        education = EDUCATION_MAPPING.get(education_raw, education_raw if education_raw else None)
        life_situation = str(row.get("Lebenslage", "")).strip() or None
        social_diversity = str(row.get("Soziodemografisches / Soziale Vielfalt", "")).strip() or None

        if social_diversity and social_diversity.lower() == "nein":
            social_diversity = None

        parsed.append({
            "temp_id": str(uuid.uuid4()),
            "name": name_raw,
            "first_name": first_name,
            "last_name": last_name,
            "member_number": member_nr,
            "birth_date": dob.isoformat() if dob else None,
            "timestamp_str": timestamp_str,
            "timestamp": timestamp,
            "gender": gender,
            "occupation": occupation,
            "education": education,
            "life_situation": life_situation,
            "social_diversity": social_diversity,
        })

    # Deduplicate by member_number or name, keep newest
    deduped = _deduplicate_individual(parsed)

    return {
        "total_rows": total_rows,
        "skipped_not_submitted": skipped_not_submitted,
        "skipped_duplicates": total_rows - skipped_not_submitted - len(privacy_warnings) - len(deduped),
        "privacy_warnings": privacy_warnings,
        "individuals": deduped,
    }


def _deduplicate_individual(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("member_number"):
            key = f"nr_{row['member_number']}"
        else:
            key = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip().lower()
        if not key:
            continue
        groups.setdefault(key, []).append(row)

    result = []
    for key, items in groups.items():
        items.sort(key=lambda r: r.get("timestamp") or datetime.min, reverse=True)
        result.append(items[0])
    return result


# ---------------------------------------------------------------------------
# Individual Matching
# ---------------------------------------------------------------------------

def match_individual_to_person(ind_data: dict, db: Session) -> schemas.MatchResult:
    member_nr = ind_data.get("member_number")
    fn = (ind_data.get("first_name") or "").strip().lower()
    ln = (ind_data.get("last_name") or "").strip().lower()
    dob_str = ind_data.get("birth_date")

    # Step 1: exact member number
    if member_nr:
        matched = (
            db.query(models.Person)
            .filter(models.Person.member_number == member_nr)
            .first()
        )
        if matched and matched.household_id:
            hh = db.query(models.Household).get(matched.household_id)
            return schemas.MatchResult(
                type="exact_member_nr",
                matched_household_id=matched.id,
                matched_household_name=hh.name if hh else None,
                confidence=1.0,
            )

    # Step 2: exact name + DOB
    all_persons = db.query(models.Person).filter(models.Person.household_id.isnot(None)).all()
    for p in all_persons:
        p_fn = (p.first_name or "").strip().lower()
        p_ln = (p.last_name or "").strip().lower()
        name_match = (fn == p_fn and ln == p_ln) or (fn == p_ln and ln == p_fn)
        if not name_match:
            continue
        if dob_str and p.birth_date:
            p_dob = p.birth_date.date() if isinstance(p.birth_date, datetime) else p.birth_date
            try:
                import_dob = date.fromisoformat(dob_str)
                if import_dob == p_dob:
                    hh = db.query(models.Household).get(p.household_id) if p.household_id else None
                    return schemas.MatchResult(
                        type="exact_name_dob",
                        matched_household_id=p.id,
                        matched_household_name=hh.name if hh else None,
                        confidence=1.0,
                    )
            except Exception:
                pass
        elif name_match and not dob_str:
            hh = db.query(models.Household).get(p.household_id) if p.household_id else None
            return schemas.MatchResult(
                type="exact_name_dob",
                matched_household_id=p.id,
                matched_household_name=hh.name if hh else None,
                confidence=0.9,
            )

    # Step 3: fuzzy
    import_name = f"{fn} {ln}".strip()
    candidates = []
    for p in all_persons:
        p_name = f"{(p.first_name or '').lower()} {(p.last_name or '').lower()}".strip()
        score = SequenceMatcher(None, import_name, p_name).ratio()
        hh = db.query(models.Household).get(p.household_id) if p.household_id else None
        candidates.append(schemas.FuzzyCandidate(
            household_id=p.id,
            name=f"{p.first_name} {p.last_name}" + (f" ({hh.name})" if hh else ""),
            score=round(score, 3),
            member_numbers=[p.member_number] if p.member_number else [],
        ))
    candidates = [c for c in candidates if c.score >= 0.7]
    candidates.sort(key=lambda c: c.score, reverse=True)

    top = candidates[0] if candidates else None
    return schemas.MatchResult(
        type="fuzzy" if top else "none",
        matched_household_id=top.household_id if top else None,
        matched_household_name=top.name if top else None,
        confidence=top.score if top else 0.0,
        fuzzy_candidates=candidates[:10],
    )


# ---------------------------------------------------------------------------
# Individual Analyze & Commit
# ---------------------------------------------------------------------------

def analyze_individual_bogen(file_contents: bytes, db: Session) -> schemas.IndividualAnalysisResponse:
    _cleanup_sessions()
    parsed = parse_individual_bogen(file_contents)

    hh_imported = db.query(models.Household).filter(models.Household.import_source.isnot(None)).count() > 0

    previews = []
    for ind_data in parsed["individuals"]:
        match_result = match_individual_to_person(ind_data, db)

        already_imported = False
        is_older = False
        if match_result.matched_household_id and ind_data.get("timestamp"):
            matched_person = db.query(models.Person).get(match_result.matched_household_id)
            if matched_person and matched_person.individual_import_timestamp:
                if matched_person.individual_import_timestamp == ind_data["timestamp"]:
                    already_imported = True
                elif matched_person.individual_import_timestamp > ind_data["timestamp"]:
                    is_older = True

        previews.append(schemas.IndividualImportPreview(
            temp_id=ind_data["temp_id"],
            name=ind_data["name"],
            first_name=ind_data["first_name"],
            last_name=ind_data["last_name"],
            birth_date=ind_data.get("birth_date"),
            member_number=ind_data.get("member_number"),
            timestamp=ind_data.get("timestamp_str", ""),
            gender=ind_data.get("gender"),
            occupation=ind_data.get("occupation"),
            education=ind_data.get("education"),
            life_situation=ind_data.get("life_situation"),
            social_diversity=ind_data.get("social_diversity"),
            match_result=match_result,
            already_imported=already_imported,
            is_older=is_older,
        ))

    session = ImportSession("individual", parsed["individuals"], {})
    import_sessions[session.id] = session

    return schemas.IndividualAnalysisResponse(
        session_id=session.id,
        total_rows=parsed["total_rows"],
        skipped_not_submitted=parsed["skipped_not_submitted"],
        skipped_duplicates=parsed.get("skipped_duplicates", 0),
        privacy_warnings=[schemas.PrivacyWarning(**w) for w in parsed["privacy_warnings"]],
        hh_import_warning=not hh_imported,
        individuals=previews,
    )


def commit_individual_bogen(request: schemas.IndividualCommitRequest, db: Session) -> schemas.IndividualCommitResponse:
    session = import_sessions.get(request.session_id)
    if not session:
        raise ValueError("Import-Session nicht gefunden oder abgelaufen")

    raw_map = {r["temp_id"]: r for r in session.raw_data}

    updated_count = 0
    created_count = 0
    skipped_count = 0

    for dec in request.decisions:
        if dec.action == "skip":
            skipped_count += 1
            continue

        raw = raw_map.get(dec.temp_id)
        if not raw:
            skipped_count += 1
            continue

        if dec.action == "update" and dec.target_person_id:
            person = db.query(models.Person).get(dec.target_person_id)
            if person:
                _update_person_from_individual(person, raw)
                updated_count += 1
            else:
                skipped_count += 1

        elif dec.action == "create":
            person = _create_person_from_individual(raw, dec.target_household_id, db)
            created_count += 1

    db.commit()

    del import_sessions[request.session_id]

    return schemas.IndividualCommitResponse(
        updated=updated_count,
        created=created_count,
        skipped=skipped_count,
    )


def _update_person_from_individual(person: models.Person, raw: dict):
    if raw.get("gender"):
        person.gender = raw["gender"]
    if raw.get("occupation"):
        person.occupation_type = raw["occupation"]
    if raw.get("education"):
        person.education_level = raw["education"]
    if raw.get("social_diversity"):
        person.cultural_background = raw["social_diversity"]
    if raw.get("life_situation"):
        val = raw["life_situation"].strip()
        person.special_needs = None if val.lower() in ("nein", "", "keine") else val
    if raw.get("member_number") and not person.member_number:
        person.member_number = raw["member_number"]
    if raw.get("timestamp"):
        person.individual_import_timestamp = raw["timestamp"]


def _create_person_from_individual(raw: dict, household_id: Optional[int], db: Session) -> models.Person:
    dob = parse_date(raw.get("birth_date"))
    person = models.Person(
        household_id=household_id,
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        birth_date=datetime(dob.year, dob.month, dob.day) if dob else None,
        member_number=raw.get("member_number"),
        gender=raw.get("gender"),
        occupation_type=raw.get("occupation"),
        education_level=raw.get("education"),
        cultural_background=raw.get("social_diversity"),
        special_needs=(lambda v: None if v.lower() in ("nein", "", "keine") else v)(raw["life_situation"].strip()) if raw.get("life_situation") else None,
        individual_import_timestamp=raw.get("timestamp"),
    )
    db.add(person)
    return person

from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.orm import Session
from . import models
import pandas as pd
import numpy as np

AGE_GROUPS = ["20_29", "30_39", "40_49", "50_59", "60_69", "70_79", "80_89", "over_89"]

# "unter 20" ist keine Zielgruppe der Durchmischung (§3 Abs. 1a): die
# Bevoelkerungsanteile beziehen sich auf ab 20 Jahre. Gezaehlt wird die Gruppe
# trotzdem; die Ist-Statistik weist sie ausserhalb der Bezugsgroesse aus
# (``EXCLUDED_GROUPS``).
AGE_GROUPS_ALL = ["under_20"] + AGE_GROUPS

AGE_LABELS = {
    "under_20": "unter 20",
    "20_29": "20 bis 29",
    "30_39": "30 bis 39",
    "40_49": "40 bis 49",
    "50_59": "50 bis 59",
    "60_69": "60 bis 69",
    "70_79": "70 bis 79",
    "80_89": "80 bis 89",
    "over_89": "über 89",
}

GENDER_GROUPS = ["f", "m", "d"]

GENDER_LABELS = {
    "f": "weiblich",
    "m": "männlich",
    "d": "divers",
}

# Personen ohne gepflegte Angabe zaehlen in keiner fachlichen Gruppe mit und
# bleiben bei den Anteilen des Merkmals aussen vor (s. ``basis_totals``).
UNKNOWN_GROUP = "unknown"

# Warum eine Person bei einem Merkmal ohne Angabe ist -- fuer die Pruefliste.
MISSING_EMPTY = "empty"                # Feld leer
MISSING_CATEGORY_0 = "category_0"      # Kategorie 0: bewusst keine Zuordnung
MISSING_UNRECOGNIZED = "unrecognized"  # Wert vorhanden, aber keiner Gruppe zuzuordnen

OCCUPATION_GROUPS = [str(i) for i in range(1, 11)]

OCCUPATION_LABELS = {
    "1": "Organisation, Verwaltung, Recht",
    "2": "Pädagogik, Psychologie, Soziales",
    "3": "Geistes-, Gesellschafts-, Wirtschaftswissenschaften",
    "4": "Handwerk",
    "5": "Dienstleistung",
    "6": "Kunst und Kultur, Unterhaltung",
    "7": "Landwirtschaft, Gartenbau, Tierpflege",
    "8": "Architektur, Bauplanung",
    "9": "Naturwissenschaft, Geographie",
    "10": "Verkehr, Logistik, Schutz, Sicherheit",
}

EDUCATION_GROUPS = [str(i) for i in range(1, 9)]

EDUCATION_LABELS = {
    "1": "Berufsausbildungsvorbereitung",
    "2": "Hauptschulabschluss",
    "3": "Zweijährige Berufsausbildung, Mittlerer Schulabschluss",
    "4": "Dreijährige Berufsausbildung, Hochschulreife (inkl. Fachabitur)",
    "5": "Erste berufliche Fortbildungsqualifikation",
    "6": "Bachelor, FH-Diplom, Staatsexamen, Fachwirt, Operativer Professional, Meister, Fachschule, Berufsakademie",
    "7": "Master, Uni-Diplom, Magister, Staatsexamen, Betriebswirt, Strategischer Professional",
    "8": "Promotion",
}

# Personenbezogene Merkmale der Durchmischung und ihre fachlichen Gruppen --
# die Auspraegungen, aus denen sich die Bezugsgroesse der Anteile ergibt.
DIMENSION_GROUPS = {
    "age": AGE_GROUPS,
    "gender": GENDER_GROUPS,
    "occupation": OCCUPATION_GROUPS,
    "education": EDUCATION_GROUPS,
}

# Auspraegungen, die zwar eine Angabe sind, aber ausserhalb der Bezugsgroesse
# bleiben: die Zielwerte der Altersstruktur beziehen sich auf die Bevoelkerung
# ab 20 Jahren, Personen unter 20 wuerden die Altersanteile sonst verzerren.
EXCLUDED_GROUPS = {
    "age": {"under_20": AGE_LABELS["under_20"]},
}

# Personenfeld, aus dem ein Merkmal gelesen wird.
DIMENSION_FIELDS = {
    "age": "birth_date",
    "gender": "gender",
    "occupation": "occupation_type",
    "education": "education_level",
}

# Merkmale, die der Individualbogen liefert: bleiben sie trotz Import leer,
# ist beim Import vermutlich etwas schiefgegangen.
INDIVIDUAL_BOGEN_DIMENSIONS = ("gender", "occupation", "education")

DEFAULT_CONFIG = {
    "weight_diversity_age":            {"value": 2.0, "description": "Gewicht: Durchmischung – Altersstruktur (§3 Abs. 1a)"},
    "weight_diversity_gender":         {"value": 2.0, "description": "Gewicht: Durchmischung – Geschlechterverhältnis (§3 Abs. 1b)"},
    "weight_diversity_cultural":       {"value": 1.0, "description": "Gewicht: Durchmischung – Kulturelle Vielfalt (§3 Abs. 1c)"},
    "weight_diversity_occupation":     {"value": 1.0, "description": "Gewicht: Durchmischung – Berufliche Tätigkeiten (§3 Abs. 1d)"},
    "weight_diversity_education":      {"value": 1.0, "description": "Gewicht: Durchmischung – Bildungsabschlüsse (§3 Abs. 1e)"},
    "weight_diversity_special_needs":  {"value": 1.0, "description": "Gewicht: Durchmischung – Besondere Lebenslagen (§3 Abs. 1f)"},
    "weight_membership":       {"value": 2.0, "description": "Gewicht: Dauer der Mitgliedschaft (§3 Abs. 3)"},
    "weight_engagement":       {"value": 5.0, "description": "Gewicht: Engagement für die Genossenschaft (§3 Abs. 5)"},
    "weight_occupancy":        {"value": 2.0, "description": "Gewicht: Wohnraumausnutzung (§3 Abs. 2)"},

    # Formelparameter. Teilscores sind auf 1 normiert; nur das Gewicht skaliert.
    "max_membership_years": {"value": 10.0, "description": "Maximale Mitgliedsjahre: ab so vielen Jahren gibt es den vollen Punkt (anteilig davor)"},

    **{f"target_occupation_{k}": {"value": 0.10, "description": f"Zielwert Beruf: {v}"} for k, v in OCCUPATION_LABELS.items()},
    **{f"target_education_{k}": {"value": 0.125, "description": f"Zielwert Bildung: {v}"} for k, v in EDUCATION_LABELS.items()},

    "target_age_20_29":   {"value": 0.24350445, "description": "Zielwert Altersgruppe: 20 bis 29"},
    "target_age_30_39":   {"value": 0.17529197, "description": "Zielwert Altersgruppe: 30 bis 39"},
    "target_age_40_49":   {"value": 0.14465144, "description": "Zielwert Altersgruppe: 40 bis 49"},
    "target_age_50_59":   {"value": 0.16662092, "description": "Zielwert Altersgruppe: 50 bis 59"},
    "target_age_60_69":   {"value": 0.11703398, "description": "Zielwert Altersgruppe: 60 bis 69"},
    "target_age_70_79":   {"value": 0.08753001, "description": "Zielwert Altersgruppe: 70 bis 79"},
    "target_age_80_89":   {"value": 0.05380455, "description": "Zielwert Altersgruppe: 80 bis 89"},
    "target_age_over_89": {"value": 0.01156268, "description": "Zielwert Altersgruppe: über 89"},

    "target_gender_f":         {"value": 0.5199, "description": "Zielwert Geschlecht: weiblich"},
    "target_gender_m":         {"value": 0.4799, "description": "Zielwert Geschlecht: männlich"},
    "target_gender_d":         {"value": 0.0002, "description": "Zielwert Geschlecht: divers"},
}

def initialize_config(db: Session):
    """Seeds missing config keys and removes obsolete ones."""
    existing_keys = {c.key for c in db.query(models.ScoringConfig).all()}
    default_keys = set(DEFAULT_CONFIG.keys())

    for key in default_keys - existing_keys:
        entry = DEFAULT_CONFIG[key]
        db.add(models.ScoringConfig(
            key=key,
            value=entry["value"],
            description=entry["description"],
        ))

    for key in existing_keys - default_keys:
        db.query(models.ScoringConfig).filter(models.ScoringConfig.key == key).delete()

    if default_keys - existing_keys or existing_keys - default_keys:
        db.commit()

def get_config_dict(db: Session):
    """Returns configuration as a dictionary."""
    configs = db.query(models.ScoringConfig).all()
    return {c.key: c.value for c in configs}


def config_value(config: dict, key: str) -> float:
    """Wert aus der Konfiguration; fehlt er, gilt der Standardwert aus ``DEFAULT_CONFIG``."""
    value = config.get(key)
    return DEFAULT_CONFIG[key]["value"] if value is None else value


def system_now() -> pd.Timestamp:
    """Aktuelle Uhrzeit -- eigene Funktion, damit Tests sie festsetzen koennen."""
    return pd.Timestamp.now()


# Stichtag, zu dem gerade gerechnet wird. Eine ContextVar statt einer globalen
# Variable, damit parallele Anfragen (Threadpool) sich nicht beeinflussen.
_reference_date: ContextVar[pd.Timestamp | None] = ContextVar("scoring_reference_date", default=None)


def now() -> pd.Timestamp:
    """Stichtag fuer Alter und Mitgliedsdauer: der gesetzte Stichtag, sonst jetzt."""
    return _reference_date.get() or system_now()


@contextmanager
def at_reference_date(date):
    """Rechnet innerhalb des Blocks zum angegebenen Stichtag (``None`` = jetzt)."""
    token = _reference_date.set(pd.Timestamp(date) if date is not None else None)
    try:
        yield
    finally:
        _reference_date.reset(token)

def calculate_age_group(age):
    if age < 20: return "under_20"
    if age < 30: return "20_29"
    if age < 40: return "30_39"
    if age < 50: return "40_49"
    if age < 60: return "50_59"
    if age < 70: return "60_69"
    if age < 80: return "70_79"
    if age < 90: return "80_89"
    return "over_89"


def person_age(person: models.Person) -> float | None:
    """Alter in Jahren, ``None`` wenn kein Geburtsdatum gepflegt ist."""
    if not person.birth_date:
        return None
    return (now() - pd.to_datetime(person.birth_date)).days / 365.25


def person_age_group(person: models.Person) -> str:
    age = person_age(person)
    return UNKNOWN_GROUP if age is None else calculate_age_group(age)


def person_gender_group(person: models.Person) -> str:
    gender = (person.gender or "").strip().lower()
    if gender in ['f', 'w', 'female', 'weiblich']:
        return "f"
    if gender in ['m', 'male', 'männlich']:
        return "m"
    if gender in ['d', 'divers', 'diverse', 'non-binary']:
        return "d"
    return UNKNOWN_GROUP


def person_occupation_group(person: models.Person) -> str:
    """Berufskategorie 1--10; Kategorie 0 und Leereintrag gelten als keine Angabe."""
    occ = (person.occupation_type or "").strip()
    return occ if occ in OCCUPATION_GROUPS else UNKNOWN_GROUP


def person_education_group(person: models.Person) -> str:
    """Bildungsstufe 1--8; Kategorie 0 und Leereintrag gelten als keine Angabe."""
    edu = (person.education_level or "").strip()
    return edu if edu in EDUCATION_GROUPS else UNKNOWN_GROUP


PERSON_GROUP = {
    "age": person_age_group,
    "gender": person_gender_group,
    "occupation": person_occupation_group,
    "education": person_education_group,
}


def missing_value(person: models.Person, dimension: str) -> dict | None:
    """Warum eine Person bei einem Merkmal als "keine Angabe" gilt; ``None``, wenn sie mitzaehlt.

    Unterschieden werden ein leeres Feld, die Kategorie 0 (bewusst keine
    Zuordnung, z. B. Schueler*in oder "Keine Antwort") und ein gespeicherter,
    aber keiner Gruppe zuzuordnender Wert. Letzteres entsteht typischerweise,
    wenn ein Import einen Wert nicht uebersetzen konnte und ihn roh uebernommen
    hat -- ebenso verdaechtig ist ein leeres Feld trotz Individualbogen-Import.
    """
    if PERSON_GROUP[dimension](person) != UNKNOWN_GROUP:
        return None

    raw = getattr(person, DIMENSION_FIELDS[dimension])
    text = "" if raw is None else str(raw).strip()
    if not text:
        reason = MISSING_EMPTY
    elif text == "0" and dimension in ("occupation", "education"):
        reason = MISSING_CATEGORY_0
    else:
        reason = MISSING_UNRECOGNIZED

    suspected = reason == MISSING_UNRECOGNIZED or (
        reason == MISSING_EMPTY
        and dimension in INDIVIDUAL_BOGEN_DIMENSIONS
        and person.individual_import_timestamp is not None
    )
    return {
        "dimension": dimension,
        "reason": reason,
        "raw_value": text or None,
        "suspected_import_error": suspected,
    }


def count_people(people) -> dict:
    """Absolute Haeufigkeiten je Merkmalsauspraegung ueber die uebergebenen Personen.

    Personen ohne gepflegte Angabe landen in ``<merkmal>_unknown`` und damit in
    keiner fachlichen Gruppe -- ein fehlendes Geburtsdatum ist keine Altersgruppe.
    Ueber alle Gruppen eines Merkmals summiert ergibt sich stets die Personenzahl.
    """
    counts = {f"age_{g}": 0 for g in AGE_GROUPS_ALL}
    counts.update({f"gender_{g}": 0 for g in GENDER_GROUPS})
    counts.update({f"occupation_{g}": 0 for g in OCCUPATION_GROUPS})
    counts.update({f"education_{g}": 0 for g in EDUCATION_GROUPS})
    counts.update({f"{dim}_{UNKNOWN_GROUP}": 0
                   for dim in ("age", "gender", "occupation", "education")})

    for p in people:
        counts[f"age_{person_age_group(p)}"] += 1
        counts[f"gender_{person_gender_group(p)}"] += 1
        counts[f"occupation_{person_occupation_group(p)}"] += 1
        counts[f"education_{person_education_group(p)}"] += 1

    return counts


def resident_households(db: Session):
    """Nicht archivierte Haushalte, die aktuell eine Wohnung bewohnen."""
    return db.query(models.Household).filter(
        models.Household.is_resident == True,
        models.Household.archived == False,
    ).all()


def resident_people(db: Session):
    """Nicht archivierte Personen der Bewohner-Haushalte.

    Das ist die Referenzmenge der IST-Verteilung (Durchmischung, §3 Abs. 1).
    """
    return [p for h in resident_households(db) for p in h.people if not p.archived]

# --- Punkteaufschluesselung -------------------------------------------------
#
# ``explain_household`` ist die *einzige* Berechnung der Grundpunktzahl: sie
# liefert jeden Teilscore samt Eingangswerten, ``run_scoring`` speichert nur ihre
# Summe. Anzeige, Excel-Export und gespeicherter Score koennen deshalb nicht
# auseinanderlaufen.

# Zielwert-Kriterien der Durchmischung: Schluessel, Beschriftung, Gruppenlabels.
TARGET_CRITERIA = [
    ("age", "diversity_age", "Altersstruktur", AGE_LABELS),
    ("gender", "diversity_gender", "Geschlechterverhältnis", GENDER_LABELS),
    ("occupation", "diversity_occupation", "Berufliche Tätigkeiten",
     {k: f"{k} – {v}" for k, v in OCCUPATION_LABELS.items()}),
    ("education", "diversity_education", "Bildungsabschlüsse",
     {k: f"{k} – {v}" for k, v in EDUCATION_LABELS.items()}),
]

# Manuell bewertete Kriterien: Schluessel, Haushaltsfeld, Kategorie, Beschriftung.
MANUAL_CRITERIA = [
    ("diversity_cultural", "cultural_diversity_score", "Durchmischung", "Kulturelle Vielfalt"),
    ("diversity_special_needs", "special_needs_score", "Durchmischung", "Besondere Lebenslagen"),
    ("engagement", "engagement_score", "Engagement", "Engagement"),
]

# Ab dieser Abweichung gilt der gespeicherte Score als veraltet.
STALE_TOLERANCE = 0.005

IGNORED_REASON_LABELS = {
    MISSING_EMPTY: "keine Angabe",
    MISSING_CATEGORY_0: "Kategorie 0 – keine Zuordnung",
    MISSING_UNRECOGNIZED: "Wert nicht erkannt",
    "excluded": "unter 20 – nicht Teil der Altersstruktur",
}


def person_name(person: models.Person) -> str:
    return " ".join(part for part in (person.first_name, person.last_name) if part) or f"Person {person.id}"


def calculate_resident_reference(db: Session) -> dict:
    """IST-Verteilung samt absoluter Zaehler: ``ratios``, ``counts`` und ``basis`` je Merkmal.

    ``ratios`` entspricht ``calculate_resident_stats``; die Zaehler machen jeden
    Anteil als "Personen der Gruppe / Personen mit Angabe" nachrechenbar.
    """
    people = resident_people(db)
    counts = count_people(people)
    basis = basis_totals(counts, len(people))
    ratios = {
        f"ratio_{dim}_{g}": counts[f"{dim}_{g}"] / basis[dim] if basis[dim] else 0.0
        for dim, groups in DIMENSION_GROUPS.items()
        for g in groups
    }
    return {"ratios": ratios, "counts": counts, "basis": basis}


def _clamp01(value) -> float:
    return max(0.0, min(1.0, value or 0.0))


def _explain_target_criterion(dimension: str, key: str, label: str, labels: dict,
                              people: list, reference: dict, config: dict) -> dict:
    """Zielwert-Kriterium: Teilscore = Σ je Person (Ziel − Ist) / Ziel, nur wo Ist < Ziel.

    Jede Person traegt hoechstens 1 bei (Ist = 0, die Gruppe fehlt ganz) und 0,
    sobald ihre Gruppe den Zielwert erreicht. Die Beitraege werden ueber alle
    Personen addiert und nicht gekappt: jede Person traegt einzeln zur
    Durchmischung bei.
    """
    weight = config_value(config, f"weight_{key}")
    ratios = reference["ratios"]

    by_group: dict[str, list] = {}
    ignored = []
    for p in people:
        group = PERSON_GROUP[dimension](p)
        if group in EXCLUDED_GROUPS.get(dimension, {}):
            ignored.append({"name": person_name(p), "reason": IGNORED_REASON_LABELS["excluded"]})
        elif group == UNKNOWN_GROUP:
            reason = missing_value(p, dimension)["reason"]
            ignored.append({"name": person_name(p), "reason": IGNORED_REASON_LABELS[reason]})
        else:
            by_group.setdefault(group, []).append(person_name(p))

    terms = []
    for group in DIMENSION_GROUPS[dimension]:
        if group not in by_group:
            continue
        count = len(by_group[group])
        target = config.get(f"target_{dimension}_{group}", 0.0)
        current = ratios.get(f"ratio_{dimension}_{group}", 0.0)
        applies = current < target
        gap = target - current
        relative_gap = gap / target if applies else 0.0
        terms.append({
            "group": group,
            "label": labels.get(group, group),
            "persons": by_group[group],
            "count": count,
            "target": target,
            "resident_count": reference["counts"].get(f"{dimension}_{group}"),
            "resident_basis": reference["basis"].get(dimension),
            "current": current,
            "gap": gap,
            "applies": applies,
            "relative_gap": relative_gap,   # Beitrag je Person: (Ziel − Ist) / Ziel
            "value": relative_gap * count,
        })

    subscore = sum(t["value"] for t in terms)
    return {
        "key": key,
        "category": "Durchmischung",
        "label": label,
        "kind": "target",
        "manual": False,
        "weight": weight,
        "value": None,
        "subscore": subscore,
        "points": subscore * weight,
        "terms": terms,
        "ignored_persons": ignored,
        "membership": None,
    }


def _explain_membership(people: list, config: dict) -> dict:
    """Mitgliedsdauer je Person: min(Jahre; maximale Jahre) / maximale Jahre, summiert.

    Jede Person mit Eintrittsdatum erhaelt anteilige Punkte bis zu den maximalen
    Mitgliedsjahren; wer sie erreicht, erhaelt genau 1. Wie bei der Durchmischung
    werden die Beitraege aller Personen addiert und nicht gekappt. Personen ohne
    Eintrittsdatum tragen nichts bei und werden ausgewiesen.
    """
    max_years = config_value(config, "max_membership_years")
    weight = config_value(config, "weight_membership")

    persons = []
    ignored = []
    for p in sorted(people, key=lambda p: (p.member_since is None, p.member_since or 0)):
        if not p.member_since:
            ignored.append({"name": person_name(p), "reason": "kein Eintrittsdatum"})
            continue
        years = (now() - pd.to_datetime(p.member_since)).days / 365.25
        capped = max(0.0, min(years, max_years))
        persons.append({
            "person_name": person_name(p),
            "member_since": p.member_since,
            "years": years,
            "capped_years": capped,
            "value": capped / max_years if max_years > 0 else 0.0,
        })
    subscore = sum(entry["value"] for entry in persons)
    membership = {
        "reference_date": now().to_pydatetime(),
        "max_years": max_years,
        "persons": persons,
    }
    return {
        "key": "membership",
        "category": "Mitgliedsdauer",
        "label": "Dauer der Mitgliedschaft",
        "kind": "membership",
        "manual": False,
        "weight": weight,
        "value": None,
        "subscore": subscore,
        "points": subscore * weight,
        "terms": [],
        "ignored_persons": ignored,
        "membership": membership,
    }


def _explain_manual(key: str, field: str, category: str, label: str,
                    household: models.Household, config: dict, overrides: dict) -> dict:
    """Manuell bewertetes Kriterium: Punkte = Erfuellungsgrad (0–1) × Gewicht."""
    weight = config_value(config, f"weight_{key}")
    raw = overrides.get(field)
    value = _clamp01(getattr(household, field) if raw is None else raw)
    return {
        "key": key,
        "category": category,
        "label": label,
        "kind": "manual",
        "manual": True,
        "field": field,
        "weight": weight,
        "value": value,
        "subscore": value,
        "points": value * weight,
        "terms": [],
        "ignored_persons": [],
        "membership": None,
    }


def explain_household(household: models.Household, reference: dict, config: dict,
                      overrides: dict | None = None) -> dict:
    """Grundpunktzahl eines Haushalts, aufgeschluesselt nach Kriterien.

    ``reference`` stammt aus ``calculate_resident_reference``. Die Summe der
    ``points`` aller Kriterien ist die Grundpunktzahl (``base_score``).

    ``overrides`` ersetzt manuelle Bewertungen (Haushaltsfeld → Wert) fuer eine
    Simulation, ohne den Haushalt zu veraendern. ``is_stale`` bezieht sich dann
    auf die simulierte Summe; fuer die Pruefung auf Veraltung ohne Overrides rechnen.
    """
    overrides = {k: v for k, v in (overrides or {}).items() if v is not None}
    people = [p for p in household.people if not p.archived]
    criteria = [
        _explain_target_criterion(dim, key, label, labels, people, reference, config)
        for dim, key, label, labels in TARGET_CRITERIA
    ]
    criteria += [
        _explain_manual(key, field, category, label, household, config, overrides)
        for key, field, category, label in MANUAL_CRITERIA if category == "Durchmischung"
    ]
    criteria.append(_explain_membership(people, config))
    criteria += [
        _explain_manual(key, field, category, label, household, config, overrides)
        for key, field, category, label in MANUAL_CRITERIA if category != "Durchmischung"
    ]

    base_score = sum(c["points"] for c in criteria)
    stored = household.total_score or 0.0
    return {
        "household_id": household.id,
        "name": household.name,
        "member_count": len(people),
        "calculated_at": now().to_pydatetime(),
        "score_calculated_at": household.score_calculated_at,
        "base_score": base_score,
        "stored_score": stored,
        "is_stale": abs(base_score - stored) > STALE_TOLERANCE,
        "criteria": criteria,
    }


def explain_as_calculated(db: Session, household: models.Household, config: dict,
                          reference_cache: dict, overrides: dict | None = None) -> dict:
    """``explain_household`` zum Stichtag der letzten Berechnung des Haushalts.

    So reproduziert die Aufschluesselung genau die gespeicherte Grundpunktzahl,
    die auch die Rangliste zeigt; ``is_stale`` bedeutet dann: die Daten haben
    sich seit der Berechnung geaendert. Ohne gespeicherten Stichtag (noch nie
    berechnet) wird zum heutigen Tag gerechnet. ``reference_cache`` haelt die
    IST-Verteilung je Stichtag, damit sie bei vielen Haushalten nur einmal entsteht.
    """
    date = household.score_calculated_at
    with at_reference_date(date):
        if date not in reference_cache:
            reference_cache[date] = calculate_resident_reference(db)
        return explain_household(household, reference_cache[date], config, overrides)


def explain_occupancy(members: int, size_rooms: int | None, config: dict) -> dict:
    """Wohnraumausnutzung fuer eine Zimmerzahl: Erfuellungsgrad × Gewicht."""
    weight = config_value(config, "weight_occupancy")
    fulfilled = calculate_occupancy_subscore(members, size_rooms)
    return {
        "size_rooms": size_rooms,
        "members": members,
        "fulfilled": fulfilled,
        "weight": weight,
        "points": fulfilled * weight,
    }


def calculate_diversity_subscores(household: models.Household, current_stats: dict, config: dict) -> dict:
    """Teilscores je Durchmischungs-Dimension (§3 Abs. 1a–f) aus ``explain_household``."""
    reference = {"ratios": current_stats, "counts": {}, "basis": {}}
    explanation = explain_household(household, reference, config)
    return {c["key"]: c["subscore"] for c in explanation["criteria"]
            if c["key"].startswith("diversity_")}


def calculate_membership_score(household: models.Household, config: dict | None = None) -> float:
    people = [p for p in household.people if not p.archived]
    return _explain_membership(people, config or {})["subscore"]

def calculate_occupancy_subscore(members: int, size_rooms: int | None) -> float:
    """Erfuellungsgrad der Wohnraumausnutzung (§3 Abs. 2) fuer *eine* Wohnungsgroesse.

    Ein Haushalt nutzt eine Wohnung aus, wenn er sie mit seinen Mitgliedern
    *ausfuellt*: die Mitgliederzahl erreicht oder uebersteigt die Zimmerzahl.
    Sonst gibt es 0 Punkte -- ein Haushalt mit 3 Mitgliedern erhaelt fuer eine
    4-Zimmer-Wohnung also nichts, fuer eine 3-Zimmer-Wohnung die volle Punktzahl.

    Wohnungen ohne Zimmerangabe (gleich welcher Wohnungsart) kennen keine
    Zimmerschranke; dort ist das Kriterium mit der Mindestbelegung erfuellt, die
    die Eignungspruefung (``services.is_eligible``) bereits sicherstellt.
    """
    if size_rooms is None:
        return 1.0
    return 1.0 if members >= size_rooms else 0.0


def calculate_occupancy_score(members: int, size_rooms: int | None, config: dict) -> float:
    """Gewichtete Punkte fuer die Wohnraumausnutzung in einer Wohnungsgroesse."""
    return explain_occupancy(members, size_rooms, config)["points"]


def calculate_engagement_score(household: models.Household) -> float:
    return _clamp01(household.engagement_score)

def basis_totals(counts: dict, total: int) -> dict:
    """Bezugsgroesse der Anteile je Merkmal: Personen in einer der ``DIMENSION_GROUPS``.

    Datensaetze ohne Angabe werden ignoriert: sie gehoeren zu keiner Gruppe und
    wuerden als Teil der Bezugsgroesse jede Gruppe kleiner erscheinen lassen,
    als sie ist. Ebenso bleiben die ``EXCLUDED_GROUPS`` (Personen unter 20)
    aussen vor, damit die Anteile zu den Zielwerten passen.
    """
    return {
        dim: total
        - counts[f"{dim}_{UNKNOWN_GROUP}"]
        - sum(counts[f"{dim}_{g}"] for g in EXCLUDED_GROUPS.get(dim, {}))
        for dim in DIMENSION_GROUPS
    }


def calculate_resident_stats(db: Session) -> dict:
    """IST-Verteilung der aktuellen Bewohner als Anteile je Merkmalsauspraegung.

    Bezugsgroesse ist je Merkmal die Zahl der Bewohner-Personen mit Angabe,
    bei den Altersgruppen nur ab 20 Jahren (``basis_totals``). Die Anteile sind
    die Vergleichswerte fuer die Zielwerte der Durchmischung (§3 Abs. 1).
    """
    return calculate_resident_reference(db)["ratios"]


def _statistics_groups(dimension: str, groups, labels: dict, counts: dict,
                       total: int, config: dict, target_prefix=None) -> list:
    """Eine Merkmalsauspraegung je Zeile: absolute Zahl, Anteil und Zielwert.

    Ohne ``target_prefix`` (oder ohne hinterlegten Zielwert) bleiben die
    Soll-Felder leer.
    """
    entries = []
    for group in groups:
        count = counts.get(f"{dimension}_{group}", 0)
        target = config.get(f"{target_prefix}_{group}") if target_prefix else None
        entries.append({
            "key": group,
            "label": labels.get(group, group),
            "count": count,
            "ratio": count / total if total else 0.0,
            "target_ratio": target,
            "target_count": target * total if target is not None else None,
        })
    return entries


def calculate_resident_statistics(db: Session) -> dict:
    """Ist-Statistik der aktuellen Bewohner -- absolut und relativ.

    Grundlage sind dieselben Personen, aus denen die IST-Verteilung der
    Durchmischung entsteht (``resident_people``). Je Merkmal zaehlen nur die
    Personen mit Angabe, bei den Altersgruppen nur ab 20 Jahren. Wie viele ohne
    Angabe ignoriert wurden, steht in ``unknown_count``; die Personen unter 20
    stehen nachrichtlich in ``excluded_groups``. Der Zielwert aus der
    Bewertungskonfiguration wird mitgeliefert, damit Ist und Soll direkt
    vergleichbar sind.
    """
    config = get_config_dict(db)

    households = resident_households(db)
    people = [p for h in households for p in h.people if not p.archived]
    counts = count_people(people)

    person_total = len(people)
    household_total = len(households)
    basis = basis_totals(counts, person_total)

    numbered = lambda labels: {k: f"{k} – {v}" for k, v in labels.items()}

    def person_category(dim: str, label: str, groups: list) -> dict:
        return {
            "key": dim,
            "label": label,
            "basis": "person",
            "total": basis[dim],
            "unknown_count": counts[f"{dim}_{UNKNOWN_GROUP}"],
            "excluded_groups": [
                {"key": g, "label": g_label, "count": counts[f"{dim}_{g}"]}
                for g, g_label in EXCLUDED_GROUPS.get(dim, {}).items()
            ],
            "groups": groups,
        }

    categories = [
        person_category(
            "age", "Altersgruppen",
            _statistics_groups("age", AGE_GROUPS, AGE_LABELS, counts, basis["age"],
                               config, "target_age"),
        ),
        person_category(
            "gender", "Geschlecht",
            _statistics_groups("gender", GENDER_GROUPS, GENDER_LABELS, counts,
                               basis["gender"], config, "target_gender"),
        ),
        person_category(
            "occupation", "Haupttätigkeit",
            _statistics_groups("occupation", OCCUPATION_GROUPS, numbered(OCCUPATION_LABELS),
                               counts, basis["occupation"], config, "target_occupation"),
        ),
        person_category(
            "education", "Bildungsabschluss",
            _statistics_groups("education", EDUCATION_GROUPS, numbered(EDUCATION_LABELS),
                               counts, basis["education"], config, "target_education"),
        ),
    ]

    # Haushaltsgroesse: Bezugsgroesse sind die Haushalte, nicht die Personen.
    size_counts = {}
    for h in households:
        members = len([p for p in h.people if not p.archived])
        size_counts[members] = size_counts.get(members, 0) + 1

    categories.append({
        "key": "household_size",
        "label": "Haushaltsgröße",
        "basis": "household",
        "total": household_total,
        "unknown_count": 0,
        "excluded_groups": [],
        "groups": [
            {
                "key": str(size),
                "label": "1 Person" if size == 1 else f"{size} Personen",
                "count": count,
                "ratio": count / household_total if household_total else 0.0,
                "target_ratio": None,
                "target_count": None,
            }
            for size, count in sorted(size_counts.items())
        ],
    })

    return {
        "household_count": household_total,
        "person_count": person_total,
        "incomplete_person_count": sum(
            1 for p in people if any(missing_value(p, dim) for dim in DIMENSION_GROUPS)
        ),
        "categories": categories,
    }


def resident_people_missing_data(db: Session) -> list:
    """Bewohner-Personen, die bei mindestens einem Merkmal ohne Angabe sind.

    Das sind genau die Datensaetze, die ``calculate_resident_statistics`` beim
    jeweiligen Merkmal ignoriert. Die Liste dient der Kontrolle der Importe:
    je Merkmal stehen Grund und gespeicherter Rohwert dabei (``missing_value``).
    """
    entries = []
    for h in resident_households(db):
        unit = h.apartment.unit_number if h.apartment else h.apartment_unit
        for p in h.people:
            if p.archived:
                continue
            missing = [m for dim in DIMENSION_GROUPS if (m := missing_value(p, dim))]
            if not missing:
                continue
            age = person_age(p)
            entries.append({
                "person_id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "member_number": p.member_number,
                "household_id": h.id,
                "household_name": h.name,
                "apartment_unit": unit,
                "age": int(age) if age is not None else None,
                "individual_import_timestamp": p.individual_import_timestamp,
                "missing": missing,
            })

    entries.sort(key=lambda e: ((e["household_name"] or "").lower(),
                                (e["last_name"] or "").lower(),
                                (e["first_name"] or "").lower()))
    return entries


def run_scoring(db: Session):
    """Berechnet die *Grundpunktzahl* je Haushalt und legt sie in ``total_score`` ab.

    Die Grundpunktzahl umfasst alle Kriterien, die allein vom Haushalt abhaengen.
    Die Wohnraumausnutzung (§3 Abs. 2) haengt zusaetzlich von der Zimmerzahl der
    Wohnung ab und ist deshalb *nicht* enthalten: sie wird je Wohnungskategorie
    in ``services.build_ranking`` aufgeschlagen.
    """
    initialize_config(db)
    config = get_config_dict(db)

    households = db.query(models.Household).filter(
        models.Household.is_resident == False,
        models.Household.archived == False,
    ).all()

    stichtag = system_now()
    with at_reference_date(stichtag):
        reference = calculate_resident_reference(db)
        for h in households:
            # Ohne Wohnraumausnutzung -- die kommt je Wohnungsgroesse im Ranking dazu.
            h.total_score = explain_household(h, reference, config)["base_score"]
            h.score_calculated_at = stichtag.to_pydatetime()

    db.commit()
    return {"message": "Bewertung für alle Haushalte aktualisiert."}

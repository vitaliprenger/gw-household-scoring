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
    return (pd.Timestamp.now() - pd.to_datetime(person.birth_date)).days / 365.25


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

def calculate_diversity_subscores(household: models.Household, current_stats: dict, config: dict) -> dict:
    """Returns individual sub-scores per diversity dimension (§3 Abs. 1a–f)."""
    subscores = {
        "diversity_age": 0.0,
        "diversity_gender": 0.0,
        "diversity_cultural": 0.0,
        "diversity_occupation": 0.0,
        "diversity_education": 0.0,
        "diversity_special_needs": 0.0,
    }

    subscores["diversity_cultural"] = max(0.0, min(1.0, household.cultural_diversity_score or 0.0))
    subscores["diversity_special_needs"] = max(0.0, min(1.0, household.special_needs_score or 0.0))

    people = [p for p in household.people if not p.archived]
    if not people:
        return subscores

    hh_stats = count_people(people)

    for group in AGE_GROUPS:
        target = config.get(f"target_age_{group}", 0.0)
        current = current_stats.get(f"ratio_age_{group}", 0.0)
        if current < target and hh_stats[f"age_{group}"] > 0:
            gap = target - current
            subscores["diversity_age"] += gap * hh_stats[f"age_{group}"] * 10

    for group in OCCUPATION_GROUPS:
        target = config.get(f"target_occupation_{group}", 0.0)
        current = current_stats.get(f"ratio_occupation_{group}", 0.0)
        if current < target and hh_stats[f"occupation_{group}"] > 0:
            gap = target - current
            subscores["diversity_occupation"] += gap * hh_stats[f"occupation_{group}"] * 10

    for group in EDUCATION_GROUPS:
        target = config.get(f"target_education_{group}", 0.0)
        current = current_stats.get(f"ratio_education_{group}", 0.0)
        if current < target and hh_stats[f"education_{group}"] > 0:
            gap = target - current
            subscores["diversity_education"] += gap * hh_stats[f"education_{group}"] * 10

    for g in ["f", "m", "d"]:
        target = config.get(f"target_gender_{g}", 0.0)
        current = current_stats.get(f"ratio_gender_{g}", 0.0)
        if current < target and hh_stats[f"gender_{g}"] > 0:
            gap = target - current
            subscores["diversity_gender"] += gap * hh_stats[f"gender_{g}"] * 10

    return subscores

def calculate_membership_score(household: models.Household) -> float:
    dates = [p.member_since for p in household.people if p.member_since]
    if not dates:
        return 0.0

    earliest = min(dates)
    years = (pd.Timestamp.now() - pd.to_datetime(earliest)).days / 365.25
    return min(years, 10.0) * 2.0

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
    weight = config.get("weight_occupancy", DEFAULT_CONFIG["weight_occupancy"]["value"])
    return calculate_occupancy_subscore(members, size_rooms) * weight


def calculate_engagement_score(household: models.Household) -> float:
    return max(0.0, min(1.0, household.engagement_score or 0.0))

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
    people = resident_people(db)
    counts = count_people(people)
    basis = basis_totals(counts, len(people))

    return {
        f"ratio_{dim}_{g}": counts[f"{dim}_{g}"] / basis[dim] if basis[dim] else 0.0
        for dim, groups in DIMENSION_GROUPS.items()
        for g in groups
    }


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

    current_stats = calculate_resident_stats(db)

    for h in households:
        subscores = calculate_diversity_subscores(h, current_stats, config)
        div_total = sum(
            subscores[dim] * config.get(f"weight_{dim}", 1.0)
            for dim in subscores
        )

        mem_score = calculate_membership_score(h)
        eng_score = calculate_engagement_score(h)

        w_mem = config.get("weight_membership", 1.0)
        w_eng = config.get("weight_engagement", 1.0)

        # Ohne Wohnraumausnutzung -- die kommt je Wohnungsgroesse im Ranking dazu.
        h.total_score = div_total + (mem_score * w_mem) + (eng_score * w_eng)

    db.commit()
    return {"message": "Bewertung für alle Haushalte aktualisiert."}

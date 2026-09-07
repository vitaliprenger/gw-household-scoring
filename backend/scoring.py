from sqlalchemy.orm import Session
from . import models
import pandas as pd
import numpy as np

AGE_GROUPS = ["20_29", "30_39", "40_49", "50_59", "60_69", "70_79", "80_89", "over_89"]

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

    people = household.people
    if not people:
        return subscores

    hh_stats = {f"age_{g}": 0 for g in ["under_20"] + AGE_GROUPS}
    hh_stats.update({f"occupation_{g}": 0 for g in OCCUPATION_GROUPS})
    hh_stats.update({f"education_{g}": 0 for g in EDUCATION_GROUPS})
    hh_stats.update({"gender_f": 0, "gender_m": 0, "gender_d": 0})

    for p in people:
        age = (pd.Timestamp.now() - pd.to_datetime(p.birth_date)).days / 365.25
        hh_stats[f"age_{calculate_age_group(age)}"] += 1

        if p.gender.lower() in ['f', 'w', 'female', 'weiblich']:
            hh_stats["gender_f"] += 1
        elif p.gender.lower() in ['m', 'male', 'männlich']:
            hh_stats["gender_m"] += 1
        elif p.gender.lower() in ['d', 'divers', 'diverse', 'non-binary']:
            hh_stats["gender_d"] += 1

        occ = (p.occupation_type or "").strip()
        if occ in OCCUPATION_GROUPS:
            hh_stats[f"occupation_{occ}"] += 1

        edu = (p.education_level or "").strip()
        if edu in EDUCATION_GROUPS:
            hh_stats[f"education_{edu}"] += 1

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
    if not household.member_since:
        return 0.0
    
    # Years of membership
    years = (pd.Timestamp.now() - pd.to_datetime(household.member_since)).days / 365.25
    # Example: 1 point per year, max 10
    return min(years, 10.0) * 2.0 

def calculate_engagement_score(household: models.Household) -> float:
    return max(0.0, min(1.0, household.engagement_score or 0.0))

def calculate_resident_stats(db: Session) -> dict:
    residents = db.query(models.Household).filter(models.Household.is_resident == True).all()
    people = [p for h in residents for p in h.people]
    total = len(people)

    if total == 0:
        result = {f"ratio_age_{g}": 0.0 for g in AGE_GROUPS}
        result.update({f"ratio_occupation_{g}": 0.0 for g in OCCUPATION_GROUPS})
        result.update({f"ratio_education_{g}": 0.0 for g in EDUCATION_GROUPS})
        result.update({"ratio_gender_f": 0.0, "ratio_gender_m": 0.0, "ratio_gender_d": 0.0})
        return result

    counts = {f"age_{g}": 0 for g in ["under_20"] + AGE_GROUPS}
    counts.update({f"occupation_{g}": 0 for g in OCCUPATION_GROUPS})
    counts.update({f"education_{g}": 0 for g in EDUCATION_GROUPS})
    counts.update({"gender_f": 0, "gender_m": 0, "gender_d": 0})

    for p in people:
        age = (pd.Timestamp.now() - pd.to_datetime(p.birth_date)).days / 365.25
        counts[f"age_{calculate_age_group(age)}"] += 1

        if p.gender.lower() in ['f', 'w', 'female', 'weiblich']:
            counts["gender_f"] += 1
        elif p.gender.lower() in ['m', 'male', 'männlich']:
            counts["gender_m"] += 1
        elif p.gender.lower() in ['d', 'divers', 'diverse', 'non-binary']:
            counts["gender_d"] += 1

        occ = (p.occupation_type or "").strip()
        if occ in OCCUPATION_GROUPS:
            counts[f"occupation_{occ}"] += 1

        edu = (p.education_level or "").strip()
        if edu in EDUCATION_GROUPS:
            counts[f"education_{edu}"] += 1

    return {f"ratio_{k}": v / total for k, v in counts.items()}


def run_scoring(db: Session):
    initialize_config(db)
    config = get_config_dict(db)

    households = db.query(models.Household).filter(models.Household.is_resident == False).all()

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

        h.total_score = div_total + (mem_score * w_mem) + (eng_score * w_eng)
    
    db.commit()
    return {"message": "Bewertung für alle Haushalte aktualisiert."}

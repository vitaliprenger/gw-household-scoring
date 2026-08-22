from sqlalchemy.orm import Session
from . import models
import pandas as pd
import numpy as np

# Default Configuration
DEFAULT_CONFIG = {
    # Weights (0-100 range for example)
    "weight_diversity": 40.0,
    "weight_membership": 20.0,
    "weight_engagement": 20.0,
    "weight_occupancy": 20.0,
    
    # Targets (Percentages 0.0 - 1.0)
    "target_age_child": 0.20, # 0-18
    "target_age_young_adult": 0.10, # 19-30
    "target_age_adult": 0.40, # 31-60
    "target_age_senior": 0.30, # 60+
    
    "target_gender_f": 0.50,
    "target_gender_m": 0.50,
    
    # Simple bonus points for binary criteria
    "bonus_special_needs": 10.0,
    "bonus_cultural_background": 5.0
}

def initialize_config(db: Session):
    """Seeds the database with default scoring configuration if empty."""
    if db.query(models.ScoringConfig).first() is None:
        for key, value in DEFAULT_CONFIG.items():
            db.add(models.ScoringConfig(key=key, value=value))
        db.commit()

def get_config_dict(db: Session):
    """Returns configuration as a dictionary."""
    configs = db.query(models.ScoringConfig).all()
    return {c.key: c.value for c in configs}

def calculate_age_group(age):
    if age < 18: return "child"
    if age < 30: return "young_adult"
    if age < 60: return "adult"
    return "senior"

def calculate_diversity_score(household: models.Household, current_stats: dict, config: dict) -> float:
    """
    Calculates diversity score based on how much the household helps achieve targets.
    Simplified logic: If a group is underrepresented (Current < Target), give points.
    """
    score = 0.0
    people = household.people
    if not people:
        return 0.0

    # Analyze household composition
    hh_stats = {
        "age_child": 0, "age_young_adult": 0, "age_adult": 0, "age_senior": 0,
        "gender_f": 0, "gender_m": 0,
        "special_needs": 0, "cultural_background": 0
    }
    
    for p in people:
        # Age
        age = (pd.Timestamp.now() - pd.to_datetime(p.birth_date)).days / 365.25
        age_group = calculate_age_group(age)
        hh_stats[f"age_{age_group}"] += 1
        
        # Gender
        if p.gender.lower() in ['f', 'w', 'female', 'weiblich']:
            hh_stats["gender_f"] += 1
        elif p.gender.lower() in ['m', 'male', 'männlich']:
            hh_stats["gender_m"] += 1
            
        # Special Needs
        if p.special_needs:
            hh_stats["special_needs"] += 1
            
        # Cultural Background (check if not empty)
        if p.cultural_background:
            hh_stats["cultural_background"] += 1

    # Calculate Score based on Gaps
    # 1. Age Targets
    for group in ["child", "young_adult", "adult", "senior"]:
        target = config.get(f"target_age_{group}", 0.25)
        current = current_stats.get(f"ratio_age_{group}", 0.0)
        
        # If current is below target, we award points for bringing people of this group
        if current < target and hh_stats[f"age_{group}"] > 0:
            gap = target - current
            # Points = Gap * Count * Factor
            score += gap * hh_stats[f"age_{group}"] * 10 # Arbitrary multiplier
            
    # 2. Gender Targets
    for g in ["f", "m"]:
        target = config.get(f"target_gender_{g}", 0.5)
        current = current_stats.get(f"ratio_gender_{g}", 0.0)
        if current < target and hh_stats[f"gender_{g}"] > 0:
            gap = target - current
            score += gap * hh_stats[f"gender_{g}"] * 10

    # 3. Special Needs & Cultural (Fixed Bonuses)
    if hh_stats["special_needs"] > 0:
        score += config.get("bonus_special_needs", 0.0)
    
    if hh_stats["cultural_background"] > 0:
        score += config.get("bonus_cultural_background", 0.0)

    return score

def calculate_membership_score(household: models.Household) -> float:
    if not household.member_since:
        return 0.0
    
    # Years of membership
    years = (pd.Timestamp.now() - pd.to_datetime(household.member_since)).days / 365.25
    # Example: 1 point per year, max 10
    return min(years, 10.0) * 2.0 

def calculate_engagement_score(household: models.Household) -> float:
    # Engagement score is 0-1 in DB, scale it to e.g. 0-20 points
    return household.engagement_score * 20.0

def calculate_resident_stats(db: Session) -> dict:
    residents = db.query(models.Household).filter(models.Household.is_resident == True).all()
    people = [p for h in residents for p in h.people]
    total = len(people)

    if total == 0:
        return {
            "ratio_age_child": 0.0, "ratio_age_young_adult": 0.0,
            "ratio_age_adult": 0.0, "ratio_age_senior": 0.0,
            "ratio_gender_f": 0.0, "ratio_gender_m": 0.0,
        }

    counts = {
        "age_child": 0, "age_young_adult": 0, "age_adult": 0, "age_senior": 0,
        "gender_f": 0, "gender_m": 0,
    }

    for p in people:
        age = (pd.Timestamp.now() - pd.to_datetime(p.birth_date)).days / 365.25
        counts[f"age_{calculate_age_group(age)}"] += 1

        if p.gender.lower() in ['f', 'w', 'female', 'weiblich']:
            counts["gender_f"] += 1
        elif p.gender.lower() in ['m', 'male', 'männlich']:
            counts["gender_m"] += 1

    return {f"ratio_{k}": v / total for k, v in counts.items()}


def run_scoring(db: Session):
    initialize_config(db)
    config = get_config_dict(db)

    households = db.query(models.Household).filter(models.Household.is_resident == False).all()

    current_stats = calculate_resident_stats(db)

    # 2. Calculate Score per Household
    for h in households:
        # Diversity
        div_score = calculate_diversity_score(h, current_stats, config)
        
        # Membership
        mem_score = calculate_membership_score(h)
        
        # Engagement
        eng_score = calculate_engagement_score(h)
        
        # Weighted Sum
        w_div = config.get("weight_diversity", 1.0)
        w_mem = config.get("weight_membership", 1.0)
        w_eng = config.get("weight_engagement", 1.0)
        
        # Normalize weights if needed, or just sum up
        total = (div_score * w_div) + (mem_score * w_mem) + (eng_score * w_eng)
        
        h.total_score = total
    
    db.commit()
    return {"message": "Bewertung für alle Haushalte aktualisiert."}

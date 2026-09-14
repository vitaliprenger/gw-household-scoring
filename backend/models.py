from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from .database import Base
from datetime import datetime

class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    application_date = Column(DateTime, default=datetime.utcnow)

    # Scoring specific fields
    engagement_score = Column(Float, default=0.0)
    cultural_diversity_score = Column(Float, default=0.0)
    special_needs_score = Column(Float, default=0.0)
    is_resident = Column(Boolean, default=False)

    # Calculated Score (cached)
    total_score = Column(Float, default=0.0)
    # Stichtag der letzten Berechnung: Alter und Mitgliedsdauer haengen am Datum,
    # die Aufschluesselung rechnet zu diesem Stichtag nach (``scoring.explain_household``).
    score_calculated_at = Column(DateTime, nullable=True)

    # Import fields
    wbs_status = Column(String, nullable=True)
    pets_count = Column(Integer, default=0)
    pets_info = Column(String, nullable=True)
    # Der Wohnungswunsch liegt nicht mehr am Haushalt, sondern strukturiert an
    # der Bewerbung (``Application.wishes``).
    wheelchair_accessible = Column(Boolean, default=False)
    financial_status = Column(String, nullable=True)
    import_source = Column(String, nullable=True)
    import_timestamp = Column(DateTime, nullable=True)
    household_member_count = Column(Integer, nullable=True)
    apartment_unit = Column(String, nullable=True)
    vcf_import_timestamp = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, nullable=True)
    archived = Column(Boolean, default=False)

    # Relationships
    people = relationship("Person", back_populates="household")
    applications = relationship("Application", back_populates="household")
    apartment = relationship(
        "Apartment",
        back_populates="household",
        foreign_keys="Apartment.household_id",
        uselist=False,
    )

    @property
    def assigned_apartment_unit(self):
        return self.apartment.unit_number if self.apartment else None

class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=True)

    first_name = Column(String)
    last_name = Column(String)
    birth_date = Column(DateTime, nullable=True)
    gender = Column(String, nullable=True)
    occupation_type = Column(String, nullable=True)
    education_level = Column(String, nullable=True)
    cultural_background = Column(String, nullable=True)
    special_needs = Column(String, nullable=True)
    member_number = Column(String, nullable=True)
    member_since = Column(DateTime, nullable=True)
    individual_import_timestamp = Column(DateTime, nullable=True)
    vcf_import_timestamp = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    archived = Column(Boolean, default=False)

    household = relationship("Household", back_populates="people")

class Apartment(Base):
    __tablename__ = "apartments"

    id = Column(Integer, primary_key=True, index=True)
    unit_number = Column(String, unique=True, index=True)  # z. B. "W.002", "P.108.1"
    size_rooms = Column(Integer, nullable=True)  # ganze Zahl, bei jeder Wohnungsart moeglich; None = ohne Zimmerangabe
    funding_type = Column(String)  # "freifinanziert", "WBS A", "WBS B"

    # Wohnungsdaten (Stammdaten, im Frontend editierbar)
    apartment_category = Column(String, nullable=True)   # Wohnungsart
    is_small = Column(Boolean, default=False)            # klein für ihre Zimmerzahl
    area_shares = Column(Float, nullable=True)           # qm Anteile
    area_rent = Column(Float, nullable=True)             # qm mietwirksam
    area_utilities = Column(Float, nullable=True)        # qm Nebenkosten
    min_occupants = Column(Integer, nullable=True)       # mind. Bewohner

    # Ist-Belegung: Haushalt, der in dieser Wohnung wohnt
    household_id = Column(Integer, ForeignKey("households.id"), nullable=True)

    household = relationship("Household", back_populates="apartment")
    #: Bewerbungen, die mit dieser Wohnung erfüllt wurden (Historie)
    applications = relationship("Application", back_populates="fulfilled_apartment")

#: Bewerbungsarten. ``wartepool`` sind Haushalte, die noch nicht im Projekt
#: wohnen -- sie werden per Scoring gereiht. ``wechselwunsch`` und ``joker``
#: stellen bestehende Bewohner-Haushalte; dort entscheidet die Reihenfolge des
#: Wunsches (``requested_at``), nicht das Scoring.
APPLICATION_KINDS = ("wartepool", "wechselwunsch", "joker")

#: Bewerbungsstatus. Erfüllte und zurückgezogene Bewerbungen bleiben erhalten,
#: damit rückwirkend einsehbar ist, welche Bewerbungen es gab und warum sie
#: endeten.
APPLICATION_STATUSES = ("offen", "erfuellt", "zurueckgezogen")


class Application(Base):
    """Bewerbung eines Haushalts auf eine oder mehrere Wohnungskategorien.

    Eine Bewerbung richtet sich **nicht** auf eine konkrete Wohnung, sondern auf
    Wunschkategorien (Zimmerzahl x Förderungsart, ggf. Wohnungsart). Die
    konkrete Wohnung entsteht erst bei der Erfüllung
    (``fulfilled_apartment_id``) und wird beim Einzug automatisch gesetzt
    (``services.close_open_applications``).
    """

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), index=True)

    kind = Column(String, default="wartepool", index=True)   # siehe APPLICATION_KINDS
    requested_at = Column(DateTime, nullable=True)           # "Mail / Info von"

    #: Wunschkategorien als Liste von Objekten
    #: ``{"size_rooms": int|None, "funding_type": str|None, "apartment_category": str|None}``.
    #: ``None`` in einem Feld heißt "egal". Validiert über ``schemas.ApplicationWish``.
    wishes = Column(JSON, nullable=True)

    status = Column(String, default="offen", index=True)     # siehe APPLICATION_STATUSES
    status_note = Column(String, nullable=True)              # z. B. warum zurückgezogen

    #: Kennzeichen, dass von der Regelvergabe abgewichen werden sollte, samt Begründung.
    special_case = Column(Boolean, default=False)
    special_case_note = Column(String, nullable=True)

    note = Column(String, nullable=True)                     # allgemeiner Kommentar

    fulfilled_apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True)
    fulfilled_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    archived = Column(Boolean, default=False)

    household = relationship("Household", back_populates="applications")
    fulfilled_apartment = relationship("Apartment", back_populates="applications")

class ScoringConfig(Base):
    """Stores weights and target values"""
    __tablename__ = "scoring_config"
    
    key = Column(String, primary_key=True, index=True) # e.g., "weight_age", "target_gender_f"
    value = Column(Float)
    description = Column(String, nullable=True)

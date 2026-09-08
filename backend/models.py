from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship
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

    # Import fields
    wbs_status = Column(String, nullable=True)
    pets_count = Column(Integer, default=0)
    pets_info = Column(String, nullable=True)
    desired_apartment_size = Column(String, nullable=True)
    desired_apartment_type = Column(JSON, nullable=True)
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
    unit_number = Column(String, unique=True, index=True)
    size_rooms = Column(Float) # 1.5 to 5.5
    funding_type = Column(String) # "freifinanziert", "WBS A", "WBS B"
    
    applications = relationship("Application", back_populates="apartment")

class Application(Base):
    """Link between Household and Apartment (Many-to-Many with extra data if needed)"""
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"))
    apartment_id = Column(Integer, ForeignKey("apartments.id"))
    status = Column(String, default="applied") # applied, offered, rejected
    
    household = relationship("Household", back_populates="applications")
    apartment = relationship("Apartment", back_populates="applications")

class ScoringConfig(Base):
    """Stores weights and target values"""
    __tablename__ = "scoring_config"
    
    key = Column(String, primary_key=True, index=True) # e.g., "weight_age", "target_gender_f"
    value = Column(Float)
    description = Column(String, nullable=True)

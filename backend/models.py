from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # e.g., "Family Smith"
    application_date = Column(DateTime, default=datetime.utcnow)
    
    # Scoring specific fields
    member_since = Column(DateTime, nullable=True) # For membership duration
    engagement_score = Column(Float, default=0.0) # 0-1 score for engagement
    is_resident = Column(Boolean, default=False)

    # Calculated Score (cached)
    total_score = Column(Float, default=0.0)
    
    # Relationships
    people = relationship("Person", back_populates="household")
    applications = relationship("Application", back_populates="household")

class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"))
    
    first_name = Column(String)
    last_name = Column(String)
    birth_date = Column(DateTime)
    gender = Column(String) # m, f, d, etc.
    occupation_type = Column(String) # e.g., "employed", "student", "retired"
    education_level = Column(String) # e.g., "university", "vocational", "none"
    cultural_background = Column(String, nullable=True)
    special_needs = Column(Boolean, default=False) # For "besondere Lebenslagen"
    
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

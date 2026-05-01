from sqlalchemy import Column, Integer, String, Float, Boolean, JSON
from db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contract_type = Column(String, nullable=False)  # EPC or ITEM_RATE
    scp_days = Column(Integer, nullable=False)
    contract_value_inr = Column(Float, nullable=False)
    day_number = Column(Integer, default=0)
    contractor_name = Column(String, nullable=True)
    appointed_date = Column(String, nullable=True)
    last_actual_pct = Column(Float, default=0.0)
    last_reporting_period = Column(String, nullable=True)
class RuleStore(Base):
    __tablename__ = "rule_store"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, index=True, nullable=False)
    rules = Column(JSON, nullable=False)

class ComplianceEvent(Base):
    __tablename__ = "compliance_events"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, index=True, nullable=False)
    reporting_period = Column(String, nullable=False)
    event_data = Column(JSON, nullable=False)

class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True, nullable=False)
    project_id = Column(String, index=True, nullable=False)
    contract_type = Column(String, nullable=False)
    current_tier = Column(String, nullable=False)          # NONE / NOTICE_OF_INTENT / etc.
    tier_entered_date = Column(String, nullable=False)
    tier_deadline = Column(String, nullable=True)
    responsible_party = Column(String, nullable=True)
    next_action = Column(String, nullable=True)
    clause = Column(String, nullable=True)
    notice_text = Column(String, nullable=True)
    is_final = Column(Boolean, default=False)
    created_at = Column(String, nullable=True)
    history = Column(JSON, nullable=True, default=list)

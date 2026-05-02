from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime
from sqlalchemy.sql import func
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
    name = Column(String, index=True)
    contract_type = Column(String)  # e.g., "EPC", "HAM", "BOT"
    scp_days = Column(Integer)
    contract_value_inr = Column(Float)
    day_number = Column(Integer, default=0)
    contractor_name = Column(String, nullable=True)
    
    # Snapshot of last received MPR state (Phase 2 additions)
    last_reporting_period = Column(String, nullable=True)
    last_actual_pct = Column(Float, nullable=True)
    last_risk_score = Column(Float, nullable=True)
    last_risk_label = Column(String, nullable=True)
    last_ld_accrued_inr = Column(Float, nullable=True)



class MPRRecord(Base):
    __tablename__ = "mpr_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, index=True, nullable=False)
    reporting_period = Column(String, nullable=False)  # e.g. "2025-05"
    day_number = Column(Integer, default=0)
    actual_physical_pct = Column(Float, default=0.0)
    planned_physical_pct = Column(Float, default=0.0)
    risk_score = Column(Float, nullable=True)
    risk_label = Column(String, nullable=True)
    total_ld_accrued_inr = Column(Float, default=0.0)
    critical_event_count = Column(Integer, default=0)
    high_event_count = Column(Integer, default=0)
    total_event_count = Column(Integer, default=0)
    
    exec_data_json = Column(JSON, nullable=True)
    compliance_json = Column(JSON, nullable=True)
    risk_json = Column(JSON, nullable=True)
    
    audience = Column(String, nullable=True)
    uploaded_filename = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

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

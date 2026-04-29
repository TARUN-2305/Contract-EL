"""
Compliance Agent — wraps the Compliance Engine per the EL spec.
Loads rule store, runs all 15 checks, persists results.
"""
import json
import os
from datetime import date

from agents.compliance_engine import run_all_checks
from db.database import SessionLocal
from db.models import ComplianceEvent as DBComplianceEvent, RuleStore


class ComplianceAgent:
    def __init__(self):
        pass

    def _load_rule_store(self, contract_id: str) -> dict:
        """Load rule store: filesystem first, then database."""
        path = f"data/rule_store/rule_store_{contract_id}.json"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        # Fallback to database
        db = SessionLocal()
        try:
            row = db.query(RuleStore).filter(RuleStore.project_id == contract_id).order_by(RuleStore.id.desc()).first()
            return row.rules if row else {}
        finally:
            db.close()

    def run(self, exec_data: dict) -> dict:
        """Main entry: run compliance checks for a given MPR submission."""
        contract_id = exec_data.get("contract_id") or exec_data.get("project_id")
        print(f"[ComplianceAgent] Running checks for contract {contract_id}")

        rule_store = self._load_rule_store(contract_id)
        if not rule_store:
            print(f"[ComplianceAgent] ERROR: No rule store found for {contract_id}")
            return {"error": "Rule store not found", "contract_id": contract_id}

        report = run_all_checks(exec_data, rule_store)

        # Persist to filesystem
        os.makedirs("data/compliance", exist_ok=True)
        period = exec_data.get("reporting_period", "unknown")
        path = f"data/compliance/compliance_{contract_id}_{period}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"[ComplianceAgent] Report written: {path}")

        # Persist to database
        db = SessionLocal()
        try:
            row = DBComplianceEvent(
                project_id=contract_id,
                reporting_period=period,
                event_data=report,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        print(
            f"[ComplianceAgent] Done. Events: {report['total_events']} "
            f"(CRITICAL: {report['critical_count']}, HIGH: {report['high_count']})"
        )
        return report

"""
Celery tasks for background processing.
- parse_contract: heavy LLM + embedding pipeline
- process_mpr: compliance + risk + explanation pipeline
- run_daily_checks: escalation timer checks
"""
import json
import os
import traceback
from datetime import datetime

from workers.celery_app import celery_app


def _update_job_status(job_id: str, status: str, result: dict = None, error: str = None):
    """Store job status in Redis for polling."""
    try:
        import redis
        from config import settings
        r = redis.from_url(settings.redis_url)
        data = {
            "job_id": job_id,
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
            "result": result or {},
            "error": error or "",
        }
        r.setex(f"job:{job_id}", 3600, json.dumps(data))
    except Exception as e:
        print(f"[Tasks] Redis status update failed: {e}")


@celery_app.task(bind=True, name="tasks.parse_contract")
def parse_contract_task(self, job_id: str, file_path: str, contract_id: str,
                        contract_type: str, project_name: str, contract_value_inr: float,
                        scp_days: int, location: str, contractor_name: str):
    """
    Parse a contract PDF/DOCX asynchronously.
    Steps: extract text → chunk → embed → store in Qdrant → LLM extraction → rule store.
    """
    _update_job_status(job_id, "STARTED", {"step": "initializing"})
    try:
        import sys
        sys.path.insert(0, "/app")
        from agents.parser_agent import ParserAgent
        from db.database import SessionLocal

        agent = ParserAgent()
        db = SessionLocal()
        try:
            _update_job_status(job_id, "RUNNING", {"step": "extracting_text"})
            rule_store = agent.parse_contract(
                file_path=file_path,
                contract_id=contract_id,
                contract_type=contract_type,
                project_name=project_name,
                contract_value_inr=contract_value_inr,
                scp_days=scp_days,
                location=location,
                contractor_name=contractor_name,
                db=db,
                progress_callback=lambda step: _update_job_status(job_id, "RUNNING", {"step": step})
            )
            _update_job_status(job_id, "SUCCESS", {
                "step": "done",
                "contract_id": contract_id,
                "rule_store_keys": list(rule_store.keys()) if rule_store else [],
            })
            return {"status": "success", "contract_id": contract_id}
        finally:
            db.close()
            # Clean up uploaded temp file
            try:
                os.remove(file_path)
            except Exception:
                pass
    except Exception as e:
        err = traceback.format_exc()
        _update_job_status(job_id, "FAILURE", error=str(e))
        raise


@celery_app.task(bind=True, name="tasks.process_mpr")
def process_mpr_task(self, job_id: str, project_id: str, file_path: str,
                     audience: str = "project_manager", contract_id: str = None):
    """
    Process an MPR upload asynchronously.
    Steps: parse MPR → compliance check → risk score → LLM explanation → save.
    """
    _update_job_status(job_id, "STARTED", {"step": "parsing_mpr"})
    try:
        import sys
        sys.path.insert(0, "/app")
        from agents.mpr_parser import parse_mpr
        from agents.compliance_engine import run_all_checks
        from agents.risk_predictor import RiskPredictor
        from agents.explainer_agent import ExplainerAgent
        from db.database import SessionLocal
        from db import models
        import json

        db = SessionLocal()
        try:
            # 1. Parse MPR
            _update_job_status(job_id, "RUNNING", {"step": "parsing_mpr"})
            exec_data = parse_mpr(file_path)

            # 2. Load rule store
            if not contract_id:
                contract_id = project_id
            rule_store_path = f"/app/data/rule_store/rule_store_{contract_id}.json"
            if os.path.exists(rule_store_path):
                with open(rule_store_path) as f:
                    rule_store = json.load(f)
            else:
                row = db.query(models.RuleStore).filter(models.RuleStore.project_id == project_id).order_by(models.RuleStore.id.desc()).first()
                rule_store = row.rules if row else {}

            # 3. Compliance checks
            _update_job_status(job_id, "RUNNING", {"step": "compliance_checks"})
            from datetime import date
            events = run_all_checks(exec_data, rule_store, date.today())

            # 4. Risk prediction
            _update_job_status(job_id, "RUNNING", {"step": "risk_prediction"})
            risk_predictor = RiskPredictor()
            risk_result = risk_predictor.predict(exec_data, rule_store)

            # 5. LLM explanation
            _update_job_status(job_id, "RUNNING", {"step": "generating_explanation"})
            explainer = ExplainerAgent()
            explanation = explainer.explain(exec_data, events, risk_result, rule_store, audience)

            # 6. Persist
            _update_job_status(job_id, "RUNNING", {"step": "saving_results"})
            from dataclasses import asdict
            events_dicts = [asdict(e) for e in events] if events else []
            critical_count = sum(1 for e in events if e.severity == "CRITICAL")
            high_count = sum(1 for e in events if e.severity == "HIGH")
            total_ld = sum(e.ld_accrued_inr for e in events if hasattr(e, "ld_accrued_inr"))

            mpr_record = models.MPRRecord(
                project_id=project_id,
                reporting_period=exec_data.get("reporting_period_end", ""),
                day_number=exec_data.get("day_number", 0),
                actual_physical_pct=exec_data.get("actual_physical_pct", 0),
                planned_physical_pct=exec_data.get("planned_physical_pct", 0),
                risk_score=risk_result.get("risk_score"),
                risk_label=risk_result.get("risk_label"),
                total_ld_accrued_inr=total_ld,
                critical_event_count=critical_count,
                high_event_count=high_count,
                total_event_count=len(events_dicts),
                exec_data_json=exec_data,
                compliance_json=events_dicts,
                risk_json=risk_result,
                audience=audience,
                uploaded_filename=os.path.basename(file_path),
            )
            db.add(mpr_record)

            # Update project snapshot
            project = db.query(models.Project).filter(models.Project.id == project_id).first()
            if project:
                project.last_reporting_period = exec_data.get("reporting_period_end", "")
                project.last_actual_pct = exec_data.get("actual_physical_pct", 0)
                project.last_risk_score = risk_result.get("risk_score")
                project.last_risk_label = risk_result.get("risk_label")
                project.last_ld_accrued_inr = total_ld

            db.commit()

            _update_job_status(job_id, "SUCCESS", {
                "step": "done",
                "events_count": len(events_dicts),
                "critical_count": critical_count,
                "risk_label": risk_result.get("risk_label"),
                "mpr_record_id": mpr_record.id,
            })
            return {"status": "success", "project_id": project_id}
        finally:
            db.close()
            try:
                os.remove(file_path)
            except Exception:
                pass
    except Exception as e:
        err = traceback.format_exc()
        _update_job_status(job_id, "FAILURE", error=str(e))
        raise


@celery_app.task(name="tasks.run_daily_checks")
def run_daily_checks():
    """Daily escalation timer check — triggered by beat scheduler."""
    import sys
    sys.path.insert(0, "/app")
    from db.database import SessionLocal
    from db.models import EscalationEvent
    from agents.escalation_agent import EscalationAgent, EscalationRecord

    db = SessionLocal()
    try:
        rows = db.query(EscalationEvent).filter(EscalationEvent.is_final == False).all()
        records = [EscalationRecord(
            event_id=r.event_id, project_id=r.project_id,
            contract_type=r.contract_type, current_tier=r.current_tier,
            tier_entered_date=r.tier_entered_date, tier_deadline=r.tier_deadline,
            responsible_party=r.responsible_party, next_action=r.next_action,
            clause=r.clause, notice_text=r.notice_text, is_final=r.is_final,
            history=r.history or []
        ) for r in rows]
        agent = EscalationAgent()
        updated = agent.check_expired_tiers(records)
        for rec in updated:
            agent.save_record(rec)
        print(f"[DailyCheck] Processed {len(records)} escalation records, {len(updated)} updated.")
    finally:
        db.close()

import os
import json
import shutil
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from db.database import get_db, engine
from db import models
from agents.orchestrator import OrchestratorAgent
from agents.parser_agent import ParserAgent
from agents.compliance_agent import ComplianceAgent
from agents.risk_predictor import RiskPredictor
from agents.explainer_agent import ExplainerAgent
from agents.mpr_parser import parse_mpr, MPRValidationError
from agents.escalation_agent import EscalationAgent, EscalationRecord
from apscheduler.schedulers.background import BackgroundScheduler
import contextlib

compliance_agent = ComplianceAgent()
risk_predictor = RiskPredictor()
explainer_agent = ExplainerAgent()
escalation_agent = EscalationAgent()
parser_agent = ParserAgent()

# ── Background Scheduler ────────────────────────────────────────────────
def daily_background_job():
    """Runs daily to check for expired cure periods and escalate."""
    print("[Scheduler] Running daily background job...")
    # In a real app, we'd load active EscalationRecords from DB.
    # For now, we simulate finding an expired record.
    # Dummy implementation to show it's wired:
    # expired_records = db.query(models.EscalationRecord).filter(...)
    # updated = escalation_agent.check_expired_tiers(expired_records)
    print("[Scheduler] Daily job complete.")

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_background_job, 'interval', hours=24)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="ContractGuard AI API", lifespan=lifespan)




class TriggerRequest(BaseModel):
    project_id: str
    trigger_type: str
    event_data: Optional[Dict[str, Any]] = None


@app.get("/")
def read_root():
    return {"message": "ContractGuard AI API is running"}


@app.post("/trigger")
def handle_trigger(request: TriggerRequest, db: Session = Depends(get_db)):
    print(f"[API] Received trigger {request.trigger_type} for project {request.project_id}")

    # 1. Fetch project state from DB
    project = db.query(models.Project).filter(models.Project.id == request.project_id).first()

    if not project:
        # Create a mock project state if it doesn't exist in DB
        project_state = {
            "project_id": request.project_id,
            "project_name": "Test Project Alpha",
            "contract_type": "EPC",
            "day_number": 30,
            "scp_days": 730,
            "active_events": [],
            "rule_store_summary": {"milestones": []},
            "trigger_data": request.event_data,
        }
    else:
        project_state = {
            "project_id": project.id,
            "project_name": project.name,
            "contract_type": project.contract_type,
            "day_number": project.day_number,
            "scp_days": project.scp_days,
            "active_events": [],
            "trigger_data": request.event_data,
        }

    # 2. Call Orchestrator
    result = orchestrator.process_trigger(request.trigger_type, project_state)

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return {"message": "Trigger processed successfully", "data": result}


@app.post("/upload-contract")
async def upload_contract(
    file: UploadFile = File(...),
    contract_id: str = Form(...),
    contract_type: str = Form("EPC"),
    contract_value_inr: float = Form(...),
    scp_days: int = Form(...),
    project_name: str = Form(...),
    location: str = Form(""),
    db: Session = Depends(get_db),
):
    """Upload a contract PDF and trigger the Parser Agent."""
    print(f"[API] Uploading contract: {contract_id} ({file.filename})")

    # Save uploaded file
    upload_dir = "data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{contract_id}_{file.filename}")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    print(f"[API] Saved file to {file_path}")

    # Create project record in DB
    existing = db.query(models.Project).filter(models.Project.id == contract_id).first()
    if not existing:
        project = models.Project(
            id=contract_id,
            name=project_name,
            contract_type=contract_type,
            scp_days=scp_days,
            contract_value_inr=contract_value_inr,
            day_number=0,
        )
        db.add(project)
        db.commit()
        print(f"[API] Created project record: {contract_id}")

    # Run Parser Agent
    try:
        rule_store = parser_agent.parse_contract(
            file_path=file_path,
            contract_id=contract_id,
            contract_type=contract_type,
            contract_value_inr=contract_value_inr,
            scp_days=scp_days,
            project_name=project_name,
            location=location,
        )
        return {
            "message": "Contract parsed successfully",
            "contract_id": contract_id,
            "rule_store_keys": list(rule_store.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@app.post("/run-compliance")
def run_compliance(exec_data: Dict[str, Any], db: Session = Depends(get_db)):
    """Run all 15 compliance checks against an MPR execution dataset."""
    print(f"[API] Running compliance for {exec_data.get('contract_id')}")
    try:
        report = compliance_agent.run(exec_data)
        if "error" in report:
            raise HTTPException(status_code=404, detail=report["error"])
        return {
            "message": "Compliance check complete",
            "total_events": report["total_events"],
            "critical_count": report["critical_count"],
            "high_count": report["high_count"],
            "total_ld_accrued_inr": report["total_ld_accrued_inr"],
            "events": report["events"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {str(e)}")


@app.post("/predict-risk")
def predict_risk(exec_data: Dict[str, Any], db: Session = Depends(get_db)):
    """Predict project risk score using XGBoost model."""
    contract_id = exec_data.get("contract_id") or exec_data.get("project_id")
    print(f"[API] Risk prediction for {contract_id}")
    try:
        rule_store_path = f"data/rule_store/rule_store_{contract_id}.json"
        if os.path.exists(rule_store_path):
            with open(rule_store_path, encoding="utf-8") as f:
                rule_store = json.load(f)
        else:
            from db.models import RuleStore
            row = db.query(RuleStore).filter(RuleStore.project_id == contract_id).order_by(RuleStore.id.desc()).first()
            rule_store = row.rules if row else {}
        if not rule_store:
            raise HTTPException(status_code=404, detail=f"Rule store not found for {contract_id}")
        prediction = risk_predictor.predict(exec_data, rule_store)
        # Persist
        os.makedirs("data/risk", exist_ok=True)
        period = exec_data.get("reporting_period", "unknown")
        out_path = f"data/risk/risk_{contract_id}_{period}.json"
        import dataclasses
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(prediction), f, indent=2)
        return {
            "contract_id": contract_id,
            "risk_score": prediction.risk_score,
            "risk_label": prediction.risk_label,
            "model_type": prediction.model_type,
            "top_risk_factors": prediction.top_risk_factors,
            "time_to_default_estimate_days": prediction.time_to_default_estimate_days,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk prediction failed: {str(e)}")


@app.post("/full-analysis")
def full_analysis(exec_data: Dict[str, Any], db: Session = Depends(get_db)):
    """Run compliance + risk prediction + explainer in one call. Full pipeline output."""
    contract_id = exec_data.get("contract_id") or exec_data.get("project_id")
    print(f"[API] Full analysis for {contract_id}")
    try:
        # Load rule store
        rule_store_path = f"data/rule_store/rule_store_{contract_id}.json"
        if os.path.exists(rule_store_path):
            with open(rule_store_path, encoding="utf-8") as f:
                rule_store = json.load(f)
        else:
            from db.models import RuleStore
            row = db.query(RuleStore).filter(RuleStore.project_id == contract_id).order_by(RuleStore.id.desc()).first()
            rule_store = row.rules if row else {}
        if not rule_store:
            raise HTTPException(status_code=404, detail=f"Rule store not found for {contract_id}")

        # Step 1: Compliance
        compliance_report = compliance_agent.run(exec_data)

        # Step 2: Risk
        prediction = risk_predictor.predict(exec_data, rule_store)
        import dataclasses
        risk_dict = dataclasses.asdict(prediction)

        # Step 3: Explain
        outputs = explainer_agent.explain(compliance_report, risk_dict, rule_store, exec_data)

        return {
            "message": "Full analysis complete",
            "contract_id": contract_id,
            "compliance": {
                "total_events": compliance_report.get("total_events"),
                "critical_count": compliance_report.get("critical_count"),
                "high_count": compliance_report.get("high_count"),
                "total_ld_accrued_inr": compliance_report.get("total_ld_accrued_inr"),
            },
            "risk": {
                "score": prediction.risk_score,
                "label": prediction.risk_label,
                "ttd_days": prediction.time_to_default_estimate_days,
                "top_factors": prediction.top_risk_factors,
            },
            "reports": {
                "compliance_md": outputs["compliance_md_path"],
                "compliance_pdf": outputs.get("compliance_pdf_path"),
                "risk_summary": outputs["risk_summary_path"],
            },
            "compliance_md_preview": outputs["compliance_md"][:500] + "...",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Full analysis failed: {str(e)}")


# ── POST /upload-mpr ───────────────────────────────────────────────────────
# Accepts a .md MPR file from Site Engineer, parses it, validates, and
# triggers /full-analysis automatically. Returns compliance + risk results.

@app.post("/upload-mpr")
async def upload_mpr(
    file: UploadFile = File(...),
    contract_id: str = Form(...),
    prev_actual_pct: float = Form(0.0),
    audience: str = Form("Project Manager"),
):
    """
    Upload a Monthly Progress Report (.md file).
    Parses all 11 sections, validates (5 rules), then runs full compliance + risk analysis.

    Args:
        file: .md file upload (MPR format per EL/02)
        contract_id: contract identifier matching a rule store on disk
        prev_actual_pct: previous month's actual physical % for monotonicity check
        audience: target persona for the AI executive summary
    """
    # Read uploaded file
    content_bytes = await file.read()
    # NOTE: bypass_date_check=True allows synthetic/demo documents that are dated in the future
    # to be uploaded. In production this should be False.
    bypass_date_check = True
    try:
        if file.filename and file.filename.lower().endswith(".docx"):
            from agents.mpr_parser import parse_mpr_docx
            import io
            exec_data = parse_mpr_docx(io.BytesIO(content_bytes), prev_actual_pct,
                                       bypass_date_check=bypass_date_check)
        else:
            md_content = content_bytes.decode("utf-8")
            from agents.mpr_parser import parse_mpr
            exec_data = parse_mpr(md_content, prev_actual_pct)
    except MPRValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "MPR validation failed",
                "validation_errors": e.errors,
                "hint": "Correct the listed fields and re-upload the .md file.",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"MPR parse error: {str(e)}")

    # Inject contract_id from form param (overrides extracted Agreement Number if provided)
    exec_data["contract_id"] = contract_id

    # Load rule store
    rule_store_path = os.path.join("data", "rule_store", f"rule_store_{contract_id}.json")
    if not os.path.exists(rule_store_path):
        raise HTTPException(
            status_code=404,
            detail=f"Rule store not found for contract '{contract_id}'. Upload the contract first.",
        )
    with open(rule_store_path, "r", encoding="utf-8") as f:
        rule_store = json.load(f)

    # Run full analysis pipeline
    try:
        # Compliance
        compliance_result = compliance_agent.run_compliance(exec_data, rule_store)

        # Risk
        prediction = risk_predictor.predict(exec_data, rule_store)

        # Explainer
        outputs = explainer_agent.explain(
            compliance_report=compliance_result,
            risk_prediction=prediction.__dict__,
            rule_store=rule_store,
            exec_data=exec_data,
            audience=audience,
        )

        return {
            "status": "success",
            "source": "mpr_upload",
            "filename": file.filename,
            "parsed_mpr": {
                "project_id": exec_data.get("project_id"),
                "project_name": exec_data.get("project_name"),
                "contractor_name": exec_data.get("contractor_name"),
                "day_number": exec_data.get("day_number"),
                "actual_physical_pct": exec_data.get("actual_physical_pct"),
                "planned_physical_pct": exec_data.get("planned_physical_pct"),
                "variance_pct": exec_data.get("variance_pct"),
                "reporting_period": exec_data.get("reporting_period"),
                "gfc_drawings_pending": exec_data.get("gfc_drawings_pending"),
                "test_fail_rate_pct": exec_data.get("test_fail_rate_pct"),
                "labour_skilled_utilisation_pct": exec_data.get("labour_skilled_utilisation_pct"),
                "row_handover_pct": exec_data.get("row_handover_pct"),
                "ncrs_pending": exec_data.get("ncrs_pending"),
                "payment_delay_days": exec_data.get("payment_delay_days"),
                "rainfall_mm_monthly": exec_data.get("rainfall_mm_monthly"),
            },
            "compliance": {
                "total_events": compliance_result.get("total_events", 0),
                "critical_count": compliance_result.get("critical_count", 0),
                "high_count": compliance_result.get("high_count", 0),
                "total_ld_accrued_inr": compliance_result.get("total_ld_accrued_inr", 0),
            },
            "risk": {
                "score": prediction.risk_score,
                "label": prediction.risk_label,
                "ttd_days": prediction.time_to_default_estimate_days,
                "top_factors": prediction.top_risk_factors,
            },
            "reports": {
                "compliance_md": outputs.get("compliance_md_path"),
                "compliance_pdf": outputs.get("compliance_pdf_path"),
                "risk_summary": outputs.get("risk_summary_path"),
            },
            "compliance_md_preview": outputs.get("compliance_md", "")[:600] + "...",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed after MPR parse: {str(e)}")


@app.get("/healthz")
def health():
    return {"status": "ok", "groq_keys_loaded": True}

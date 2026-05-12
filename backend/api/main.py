"""
ContractGuard AI — Production FastAPI with async job queue (Celery+Redis),
Qdrant vector search, LLM auto-extraction, and full persona-gated endpoints.
"""
import os, json, shutil, uuid
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import contextlib

from db.database import get_db, engine
from db import models

# ── Agent singletons ────────────────────────────────────────────────────
from agents.compliance_agent import ComplianceAgent
from agents.risk_predictor import RiskPredictor
from agents.explainer_agent import ExplainerAgent
from agents.escalation_agent import EscalationAgent, EscalationRecord
from agents.parser_agent import ParserAgent
from agents.orchestrator import OrchestratorAgent
from agents.mpr_parser import parse_mpr, MPRValidationError
from agents.eot_agent import EoTAgent
from agents.llm_auto_extract import LLMAutoExtractor

compliance_agent = ComplianceAgent()
risk_predictor = RiskPredictor()
explainer_agent = ExplainerAgent()
escalation_agent = EscalationAgent()
parser_agent = ParserAgent()
orchestrator = OrchestratorAgent()
eot_agent = EoTAgent()
auto_extractor = LLMAutoExtractor()

# ── Lifespan (scheduler) ────────────────────────────────────────────────
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    # Trigger Celery daily check task
    def _trigger_daily():
        try:
            from workers.tasks import run_daily_checks
            run_daily_checks.delay()
        except Exception as e:
            print(f"[Scheduler] daily check trigger failed: {e}")
    scheduler.add_job(_trigger_daily, 'interval', hours=24)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="ContractGuard AI API v2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in ["/healthz", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    if os.environ.get("REQUIRE_API_KEY", "false").lower() == "true":
        key = request.headers.get("X-API-Key")
        if key != os.environ.get("API_KEY_HEADER", "dev-secret-key"):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API Key"})
    return await call_next(request)

def _safe_contract_id(cid: str) -> str:
    return cid.replace("/", "_").replace("\\", "_")

def _load_rule_store(contract_id: str, db: Session) -> dict:
    path = os.path.join("/app/data/rule_store", f"rule_store_{contract_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    row = db.query(models.RuleStore).filter(models.RuleStore.project_id == contract_id).order_by(models.RuleStore.id.desc()).first()
    if row:
        return row.rules
    return {}


# ── Health check ────────────────────────────────────────────────────────

@app.get("/healthz")
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        import redis as _redis
        from config import settings
        r = _redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    qdrant_ok = False
    try:
        import httpx
        from config import settings
        resp = httpx.get(f"{settings.qdrant_url}/healthz", timeout=2)
        qdrant_ok = resp.status_code == 200
    except Exception:
        pass

    from utils.llm_client import get_llm_client
    llm_status = get_llm_client().status()

    return {
        "status": "ok" if db_ok else "degraded",
        "services": {
            "postgresql": db_ok,
            "redis": redis_ok,
            "qdrant": qdrant_ok,
            "llm": llm_status,
        }
    }


# ── LLM Status endpoint ─────────────────────────────────────────────────

@app.get("/llm-status")
def llm_status():
    from utils.llm_client import get_llm_client
    return get_llm_client().status()


# ── Job status polling ──────────────────────────────────────────────────

@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Poll async job status (Celery task progress)."""
    try:
        import redis
        from config import settings
        r = redis.from_url(settings.redis_url)
        raw = r.get(f"job:{job_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    # Fallback: query Celery result
    try:
        from celery.result import AsyncResult
        from workers.celery_app import celery_app as celery
        result = AsyncResult(job_id, app=celery)
        return {
            "job_id": job_id,
            "status": result.state,
            "result": result.result if result.ready() else {},
            "error": str(result.result) if result.failed() else "",
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found: {e}")


# ── Projects CRUD ───────────────────────────────────────────────────────

@app.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(models.Project).all()
    return {"projects": [
        {
            "id": p.id, "name": p.name,
            "contract_type": p.contract_type,
            "contract_value_inr": p.contract_value_inr,
            "contractor_name": p.contractor_name,
            "last_reporting_period": p.last_reporting_period,
            "last_actual_pct": p.last_actual_pct,
            "last_risk_score": p.last_risk_score,
            "last_risk_label": p.last_risk_label,
            "last_ld_accrued_inr": p.last_ld_accrued_inr,
        } for p in projects
    ]}

@app.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    rule_store = _load_rule_store(project_id, db)
    return {"project": {
        "id": p.id, "name": p.name,
        "contract_type": p.contract_type,
        "contract_value_inr": p.contract_value_inr,
        "contractor_name": p.contractor_name,
        "scp_days": p.scp_days,
        "last_actual_pct": p.last_actual_pct,
        "last_risk_score": p.last_risk_score,
        "last_risk_label": p.last_risk_label,
        "last_ld_accrued_inr": p.last_ld_accrued_inr,
    }, "rule_store": rule_store}

@app.get("/projects/{project_id}/mpr-history")
def get_mpr_history(project_id: str, db: Session = Depends(get_db)):
    records = db.query(models.MPRRecord).filter(
        models.MPRRecord.project_id == project_id
    ).order_by(models.MPRRecord.day_number.asc()).all()
    return {"history": [
        {
            "id": r.id, "reporting_period": r.reporting_period,
            "day_number": r.day_number,
            "actual_pct": r.actual_physical_pct,
            "planned_pct": r.planned_physical_pct,
            "risk_score": r.risk_score,
            "risk_label": r.risk_label,
            "critical_events": r.critical_event_count,
            "ld_accrued_inr": r.total_ld_accrued_inr,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in records
    ]}

@app.get("/projects/{project_id}/mpr-detail/{record_id}")
def get_mpr_detail(project_id: str, record_id: int, db: Session = Depends(get_db)):
    r = db.query(models.MPRRecord).filter(
        models.MPRRecord.id == record_id,
        models.MPRRecord.project_id == project_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="MPR record not found")
    return {
        "exec_data": r.exec_data_json,
        "compliance_events": r.compliance_json,
        "risk": r.risk_json,
        "metadata": {
            "reporting_period": r.reporting_period,
            "day_number": r.day_number,
            "actual_pct": r.actual_physical_pct,
            "planned_pct": r.planned_physical_pct,
            "audience": r.audience,
        }
    }

@app.get("/projects/{project_id}/rule-store")
def get_rule_store(project_id: str, db: Session = Depends(get_db)):
    rs = _load_rule_store(project_id, db)
    if not rs:
        raise HTTPException(status_code=404, detail="Rule store not found")
    return rs

@app.get("/projects/{project_id}/compliance-events")
def get_compliance_events(project_id: str, db: Session = Depends(get_db)):
    rows = db.query(models.ComplianceEvent).filter(
        models.ComplianceEvent.project_id == project_id
    ).order_by(models.ComplianceEvent.id.desc()).all()
    return {"events": [{"id": r.id, "period": r.reporting_period, "data": r.event_data} for r in rows]}


# ── LLM Auto-Extraction endpoints ──────────────────────────────────────

@app.post("/llm-extract-contract")
async def llm_extract_contract(file: UploadFile = File(...)):
    """
    Auto-extract contract fields from uploaded PDF/DOCX using LLM.
    Returns pre-filled form data that user can review and confirm.
    """
    tmp_path = f"/tmp/auto_extract_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
    try:
        text = auto_extractor.extract_from_file(tmp_path, "contract")
        result = auto_extractor.extract_contract_fields(text)
        return {"extracted": result, "raw_text_preview": text[:500]}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

@app.post("/llm-extract-mpr")
async def llm_extract_mpr(
    file: UploadFile = File(...),
    project_id: str = Form(default=""),
    db: Session = Depends(get_db)
):
    """
    Auto-extract MPR fields from uploaded MD/PDF using LLM.
    Uses project history for context-aware extraction.
    """
    tmp_path = f"/tmp/mpr_extract_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
    try:
        text = auto_extractor.extract_from_file(tmp_path, "mpr")
        history = []
        if project_id:
            records = db.query(models.MPRRecord).filter(
                models.MPRRecord.project_id == project_id
            ).order_by(models.MPRRecord.day_number.desc()).limit(3).all()
            history = [
                {"reporting_period": r.reporting_period, "actual_pct": r.actual_physical_pct, "risk_label": r.risk_label, "ld_accrued_inr": r.total_ld_accrued_inr}
                for r in records
            ]
        result = auto_extractor.extract_mpr_fields(text, history)
        return {"extracted": result, "history_used": len(history)}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ── Contract Upload (async via Celery) ─────────────────────────────────

@app.post("/upload-contract")
async def upload_contract(
    file: UploadFile = File(...),
    contract_id: str = Form(...),
    contract_type: str = Form("EPC"),
    project_name: str = Form(""),
    contract_value_inr: float = Form(0.0),
    scp_days: int = Form(730),
    location: str = Form(""),
    contractor_name: str = Form(""),
    async_processing: bool = Form(False),
    db: Session = Depends(get_db)
):
    """
    Upload contract PDF/DOCX. 
    async_processing=True returns job_id for polling (for large contracts).
    async_processing=False runs synchronously.
    """
    contract_id = _safe_contract_id(contract_id)
    content = await file.read()
    ext = os.path.splitext(file.filename)[1]
    tmp_path = f"/tmp/contract_{uuid.uuid4()}{ext}"
    with open(tmp_path, "wb") as f:
        f.write(content)

    if async_processing:
        job_id = str(uuid.uuid4())
        try:
            from workers.tasks import parse_contract_task
            parse_contract_task.delay(
                job_id, tmp_path, contract_id, contract_type,
                project_name, contract_value_inr, scp_days, location, contractor_name
            )
            return {"job_id": job_id, "status": "QUEUED", "message": "Contract parsing queued. Poll /jobs/{job_id}"}
        except Exception as e:
            # Celery unavailable — fall through to sync
            print(f"[API] Celery unavailable: {e}, running sync")

    # Synchronous path
    try:
        os.makedirs("/app/data/rule_store", exist_ok=True)
        rule_store = parser_agent.parse_contract(
            file_path=tmp_path,
            contract_id=contract_id,
            contract_type=contract_type,
            project_name=project_name,
            contract_value_inr=contract_value_inr,
            scp_days=scp_days,
            location=location,
            contractor_name=contractor_name,
            db=db,
        )
        # Upsert project record
        existing = db.query(models.Project).filter(models.Project.id == contract_id).first()
        if not existing:
            db.add(models.Project(
                id=contract_id, name=project_name or contract_id,
                contract_type=contract_type, scp_days=scp_days,
                contract_value_inr=contract_value_inr,
                contractor_name=contractor_name,
            ))
            db.commit()
        return {
            "message": "Contract parsed successfully",
            "contract_id": contract_id,
            "rule_store_keys": list(rule_store.keys()) if rule_store else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ── MPR Upload (async via Celery) ──────────────────────────────────────

@app.post("/upload-mpr")
async def upload_mpr(
    file: UploadFile = File(...),
    contract_id: str = Form(...),
    audience: str = Form("project_manager"),
    prev_actual_pct: float = Form(0.0),
    async_processing: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Upload Monthly Progress Report. Triggers compliance + risk + explanation pipeline."""
    contract_id = _safe_contract_id(contract_id)
    content = await file.read()
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = f"/tmp/mpr_{uuid.uuid4()}{ext}"
    with open(tmp_path, "wb") as f:
        f.write(content)

    # Verify rule store exists
    rs = _load_rule_store(contract_id, db)
    if not rs:
        os.remove(tmp_path)
        raise HTTPException(status_code=404, detail=f"Rule store not found for '{contract_id}'. Upload contract first.")

    if async_processing:
        job_id = str(uuid.uuid4())
        try:
            from workers.tasks import process_mpr_task
            process_mpr_task.delay(job_id, contract_id, tmp_path, audience, contract_id)
            return {"job_id": job_id, "status": "QUEUED", "message": "MPR processing queued. Poll /jobs/{job_id}"}
        except Exception as e:
            print(f"[API] Celery unavailable: {e}, running sync")

    # Synchronous path
    try:
        bypass = True
        if ext in (".md", ".txt"):
            md = content.decode("utf-8", errors="ignore")
            exec_data = parse_mpr(md, prev_actual_pct, bypass_date_check=bypass)
        else:
            import io
            from agents.mpr_parser import parse_mpr_docx
            exec_data = parse_mpr_docx(io.BytesIO(content), prev_actual_pct, bypass_date_check=bypass)
    except MPRValidationError as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=422, detail={"error": "MPR validation failed", "validation_errors": e.errors})
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=f"MPR parse error: {str(e)}")

    exec_data["contract_id"] = contract_id
    exec_data["appointed_date"] = rs.get("appointed_date")

    try:
        from agents.pipeline_graph import pipeline_app
        state = {
            "trigger_type": "mpr_upload", "project_id": contract_id,
            "event_data": exec_data, "project_state": {"audience": audience},
            "rule_store": rs, "messages": []
        }
        result_state = pipeline_app.invoke(state)
        compliance_result = result_state.get("compliance_report") or {}
        risk_dict = result_state.get("risk_prediction") or {}
        outputs = result_state.get("explainer_outputs") or {}

        # Persist
        from db.database import SessionLocal
        db2 = SessionLocal()
        try:
            mpr_rec = models.MPRRecord(
                project_id=contract_id,
                reporting_period=exec_data.get("reporting_period_end", exec_data.get("reporting_period", "")),
                day_number=exec_data.get("day_number", 0),
                actual_physical_pct=exec_data.get("actual_physical_pct", 0),
                planned_physical_pct=exec_data.get("planned_physical_pct", 0),
                risk_score=risk_dict.get("risk_score"),
                risk_label=risk_dict.get("risk_label"),
                total_ld_accrued_inr=compliance_result.get("total_ld_accrued_inr", 0),
                critical_event_count=compliance_result.get("critical_count", 0),
                high_event_count=compliance_result.get("high_count", 0),
                total_event_count=compliance_result.get("total_events", 0),
                exec_data_json=exec_data,
                compliance_json=compliance_result,
                risk_json=risk_dict,
                audience=audience,
                uploaded_filename=file.filename,
            )
            db2.add(mpr_rec)
            proj = db2.query(models.Project).filter(models.Project.id == contract_id).first()
            if proj:
                proj.last_actual_pct = exec_data.get("actual_physical_pct")
                proj.last_reporting_period = exec_data.get("reporting_period_end", exec_data.get("reporting_period"))
                proj.last_risk_score = risk_dict.get("risk_score")
                proj.last_risk_label = risk_dict.get("risk_label")
                proj.last_ld_accrued_inr = compliance_result.get("total_ld_accrued_inr", 0)
            db2.commit()
        finally:
            db2.close()

        return {
            "status": "success", "filename": file.filename,
            "compliance": {
                "total_events": compliance_result.get("total_events", 0),
                "critical_count": compliance_result.get("critical_count", 0),
                "high_count": compliance_result.get("high_count", 0),
                "total_ld_accrued_inr": compliance_result.get("total_ld_accrued_inr", 0),
                "events": compliance_result.get("events", []),
            },
            "risk": {
                "score": risk_dict.get("risk_score"),
                "label": risk_dict.get("risk_label"),
                "ttd_days": risk_dict.get("time_to_default_estimate_days"),
                "top_factors": risk_dict.get("top_risk_factors", []),
            },
            "reports": outputs,
            "parsed_mpr": {
                "day_number": exec_data.get("day_number"),
                "actual_physical_pct": exec_data.get("actual_physical_pct"),
                "planned_physical_pct": exec_data.get("planned_physical_pct"),
                "variance_pct": exec_data.get("variance_pct"),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ── EoT / FM endpoints ──────────────────────────────────────────────────

@app.post("/process-hindrance-eot")
def process_hindrance_eot(
    project_id: str = Form(...), hindrance_id: str = Form(...),
    hindrances: str = Form(...), contract_id: str = Form(...),
    db: Session = Depends(get_db)
):
    contract_id = _safe_contract_id(contract_id)
    rule_store = _load_rule_store(contract_id, db)
    if not rule_store:
        raise HTTPException(status_code=404, detail="Rule store not found")
    hindrance_list = json.loads(hindrances)
    decision = eot_agent.process_hindrance_eot(project_id, hindrance_id, hindrance_list, rule_store)
    path = eot_agent.save_decision(decision)
    import dataclasses
    return {"decision": dataclasses.asdict(decision), "saved_to": path}

@app.post("/process-fm-eot")
def process_fm_eot(
    project_id: str = Form(...), fm_claim: str = Form(...),
    contract_id: str = Form(...), db: Session = Depends(get_db)
):
    contract_id = _safe_contract_id(contract_id)
    rule_store = _load_rule_store(contract_id, db)
    if not rule_store:
        raise HTTPException(status_code=404, detail="Rule store not found")
    claim = json.loads(fm_claim)
    decision = eot_agent.process_fm_eot(project_id, claim, rule_store)
    path = eot_agent.save_decision(decision)
    import dataclasses
    return {"decision": dataclasses.asdict(decision), "saved_to": path}


# ── Escalations ─────────────────────────────────────────────────────────

@app.get("/escalations")
def get_escalations(db: Session = Depends(get_db)):
    rows = db.query(models.EscalationEvent).order_by(models.EscalationEvent.id.desc()).all()
    return {"escalations": [
        {
            "id": r.id, "event_id": r.event_id, "project_id": r.project_id,
            "current_tier": r.current_tier, "tier_entered_date": r.tier_entered_date,
            "tier_deadline": r.tier_deadline, "responsible_party": r.responsible_party,
            "next_action": r.next_action, "clause": r.clause, "is_final": r.is_final,
        } for r in rows
    ]}


# ── Reports ──────────────────────────────────────────────────────────────

@app.get("/reports/list")
def list_reports():
    reports = []
    for subdir in ["reports", "risk", "compliance"]:
        path = f"/app/data/{subdir}"
        if os.path.exists(path):
            for fn in os.listdir(path):
                if fn.endswith((".pdf", ".json", ".md")):
                    stat = os.stat(os.path.join(path, fn))
                    reports.append({"filename": fn, "type": subdir, "size": stat.st_size, "created_at": stat.st_ctime})
    reports.sort(key=lambda x: x["created_at"], reverse=True)
    return {"reports": reports}

@app.get("/reports/{filename}")
def serve_report(filename: str):
    for subdir in ["reports", "risk", "compliance"]:
        path = f"/app/data/{subdir}/{filename}"
        if os.path.exists(path):
            mt = "application/pdf" if filename.endswith(".pdf") else "application/json" if filename.endswith(".json") else "text/markdown"
            return FileResponse(path, media_type=mt, filename=filename)
    raise HTTPException(status_code=404, detail=f"Report not found: {filename}")


# ── Trigger / orchestrator ───────────────────────────────────────────────

class TriggerRequest(BaseModel):
    project_id: str
    trigger_type: str
    event_data: Optional[Dict[str, Any]] = None

@app.post("/trigger")
def handle_trigger(request: TriggerRequest, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == request.project_id).first()
    state = {
        "trigger_type": request.trigger_type,
        "project_id": request.project_id,
        "event_data": request.event_data or {},
        "project_state": {"name": project.name if project else request.project_id},
        "rule_store": _load_rule_store(request.project_id, db),
        "messages": []
    }
    try:
        from agents.pipeline_graph import pipeline_app
        result = pipeline_app.invoke(state)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Admin ────────────────────────────────────────────────────────────────

@app.post("/admin/weather-override")
def override_weather(payload: Dict[str, Any]):
    if "source" in payload:
        os.environ["WEATHER_SOURCE"] = payload["source"]
    if "manual_data" in payload:
        os.environ["WEATHER_MANUAL_DATA"] = json.dumps(payload["manual_data"])
    return {"message": "Weather override applied", "source": os.environ.get("WEATHER_SOURCE")}

@app.post("/admin/news-override")
def override_news(payload: Dict[str, Any]):
    if "manual_articles" in payload:
        os.environ["NEWS_MANUAL_DATA"] = json.dumps(payload["manual_articles"])
    return {"message": "News override applied"}

@app.get("/")
def root():
    return {"message": "ContractGuard AI v2 — Production Ready", "docs": "/docs"}

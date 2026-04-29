# ContractGuard AI — Next Action Plan
> Based on full recursive re-read of updated codebase + catalogue_report.md
> Previous error report fixes confirmed ✅ | New bugs found in this session | What to build next

---

## What You've Fixed Since Last Session ✅

All 19 items from the previous error report have been addressed:
- `requirements.txt` — all packages added ✅
- `api/main.py` — orchestrator instantiated, `run_compliance` → `run`, `__dict__` → `dataclasses.asdict` ✅
- `agents/mpr_parser.py` — duplicate helpers removed, `bypass_date_check` wired through, `test_fail_rate = 0.0` deleted ✅
- `agents/compliance_engine.py` — interest rate 18% → 1%/month, M4 LD basis guard, full C13a/b/c implemented ✅
- `agents/risk_predictor.py` — SMOTE → ADASYN ✅
- `agents/parser_agent.py` — `contractor_name` param added and written to rule store ✅
- `db/models.py` — `contractor_name`, `appointed_date`, `last_actual_pct`, `last_reporting_period` added ✅
- `tools/weather_tool.py` — FM threshold 0.5 → 0.75 ✅
- `dashboard.py` — `compliance_events_full` now stored in session state ✅

Since these fixes, you ran a live catalogue session and found **7 new errors** from actual runtime behaviour. Here they are with exact fixes.

---

## NEW BUGS (found in catalogue_report.md — live session)

---

### BUG 1 — `parse_contract()` kwarg mismatch: `pdf_path` vs `file_path` (CRITICAL — 500 on every contract upload)

**What's happening:** `api/main.py` calls `parser_agent.parse_contract(file_path=file_path, ...)` but in the current code `parse_contract()` has `file_path` as its parameter name (you can see this in `agents/parser_agent.py` line ~`def parse_contract(self, file_path: str, ...)`). However the catalogue report says this is still broken.

**Check the actual current file — the catalogue says the 500 is `TypeError: parse_contract() got an unexpected keyword argument 'file_path'`** which means the method still uses `pdf_path` internally somewhere. Grep for `pdf_path` in `parser_agent.py`.

**EXACT FIX — search and replace in `agents/parser_agent.py`:**
```python
# Find every occurrence of pdf_path and rename to file_path:
def parse_contract(self, file_path: str, ...)   # verify parameter name is file_path
ext = os.path.splitext(file_path)[1].lower()    # verify internal usages say file_path
pages = extract_text_from_docx(file_path)        # not pdf_path
pages = extract_text_from_pdf(file_path)         # not pdf_path
```

Run: `grep -n "pdf_path" agents/parser_agent.py` to confirm if the rename is complete.

---

### BUG 2 — Ollama is used in `extraction_engine.py` / `parser_agent.py` but Ollama is not running (CRITICAL — all contract uploads fail)

**What's happening:** The catalogue confirms `parser_agent.py` was previously calling `ollama.Client()` for LLM extraction. Looking at the current code, `parser_agent.py` now correctly uses `deterministic_extract()` only — the Ollama path is gone. **However `scripts/test_llm.py` still imports `ollama`**, and if any import chain pulls it in, it fails.

More critically: `agents/extraction_engine.py` (the deterministic path) calls no Ollama — this is correctly wired. But verify no stale Ollama import exists anywhere in the main agent chain:

```bash
grep -rn "import ollama" agents/ api/ utils/ tools/ db/
```

If found anywhere outside `scripts/test_llm.py`, remove it.

**The Groq API is already configured in `utils/groq_client.py` and used everywhere else. The extraction pipeline is deterministic-first which is correct. This bug is likely already resolved but needs verification.**

---

### BUG 3 — Dashboard: Site Engineer "Field Action Items" reads from `st.session_state["last_compliance_result"]` which is `comp` (the summary dict), not the full events list (HIGH — panel always empty after upload)

**Root cause:** Even though `compliance_events_full` is now stored in `st.session_state` (your fix), the Site Engineer panel still reads from the wrong key:

```python
# Current dashboard.py (wrong):
field_events = [
    e for e in st.session_state["last_compliance_result"].get("events", [])
    ...
]
```

`st.session_state["last_compliance_result"]` = `comp` = `{"total_events": N, "critical_count": N, ...}` — has NO `"events"` key.

But `st.session_state["compliance_events_full"]` = the full events list — this IS populated correctly now.

**EXACT FIX — in `dashboard.py`, Site Engineer section:**
```python
# WRONG (line ~357):
field_events = [
    e for e in st.session_state["last_compliance_result"].get("events", [])
    if e["severity"] in ("HIGH", "MEDIUM")
]

# CORRECT:
field_events = [
    e for e in st.session_state.get("compliance_events_full", [])
    if e["severity"] in ("HIGH", "MEDIUM")
]
```

The fallback path (reading from `data/compliance/` JSON file) is already correct and will work when no session state is present.

---

### BUG 4 — Dashboard: Contract upload form has no guard when `contract_id` is empty (HIGH — causes 422 silently)

The catalogue confirms a 422 error when contract ID is blank. Looking at the current `dashboard.py` — there IS a guard:
```python
if st.button("🚀 Parse Contract"):
    if not contract_id:
        st.warning("⚠️ Please enter a Contract ID in the sidebar before uploading.")
```

**This is already fixed in the current code.** ✅ Verify it works in the live dashboard.

---

### BUG 5 — SHAP chart direction key still wrong in dashboard (HIGH — all SHAP bars render wrong colour)

This was identified in the previous error report but looking at the current `dashboard.py`:

```python
# Current dashboard.py line ~322 (STILL WRONG):
df_shap["color"] = df_shap["direction"].apply(
    lambda x: "#ef5350" if x == "Increases risk" else "#66bb6a"
)
```

But `risk_predictor.py` produces:
```python
{"direction": "increases_risk" if val > 0 else "decreases_risk"}
```

`"increases_risk"` ≠ `"Increases risk"` — the lambda never matches. **This fix was listed but not applied.**

**EXACT FIX — dashboard.py:**
```python
# WRONG:
lambda x: "#ef5350" if x == "Increases risk" else "#66bb6a"

# CORRECT:
lambda x: "#ef5350" if x == "increases_risk" else "#66bb6a"
```

---

### BUG 6 — S-curve "actual" line is a fake linear interpolation, not real data (MEDIUM — misleading chart)

Current code builds the actual curve by linearly interpolating from 0 to `actual_pct_res` across all days up to `day_number_res`. This makes it look like a perfect straight line regardless of actual project trajectory.

**EXACT FIX — replace the fake actual curve with a single point marker:**
```python
# REMOVE this block (lines ~298-304):
actual_curve = [
    min(actual_pct_res, (d / max(day_number_res, 1)) * actual_pct_res)
    if d <= day_number_res else None
    for d in days_list
]

# AND REMOVE this trace:
fig_s.add_trace(go.Scatter(x=days_list, y=actual_curve, mode="lines+markers",
                           name="Actual (%)", line=dict(color="#FF9800", width=3)))

# REPLACE WITH a single marker + annotation:
fig_s.add_trace(go.Scatter(
    x=[day_number_res],
    y=[actual_pct_res],
    mode="markers+text",
    name=f"Actual: {actual_pct_res:.1f}% (Day {day_number_res})",
    marker=dict(color="#FF9800", size=14, symbol="circle"),
    text=[f"{actual_pct_res:.1f}%"],
    textposition="top center",
))

# Add deviation annotation:
planned_at_today = min(100.0, (day_number_res / scp_days) * 100)
deviation = actual_pct_res - planned_at_today
colour = "green" if deviation >= 0 else "red"
fig_s.add_annotation(
    x=day_number_res, y=actual_pct_res,
    text=f"<b>{deviation:+.1f}% vs plan</b>",
    showarrow=True, arrowhead=2, ax=50, ay=-40,
    font=dict(color=colour, size=12),
)
```

---

### BUG 7 — `db/models.py` is missing the `EscalationRecord` model (MEDIUM — escalation agent `save_record()` has nowhere to persist)

`escalation_agent.py` has a `save_record()` method that writes to JSON files but the DB model for escalation state doesn't exist. When the background APScheduler job runs `check_expired_tiers()`, it has no DB table to load records from — the comment in `api/main.py` (`# In a real app, we'd load active EscalationRecords from DB`) makes this explicit.

**EXACT FIX — add to `db/models.py`:**
```python
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
```

Then wire `save_record()` in `escalation_agent.py` to also write to DB:
```python
def save_record(self, record: EscalationRecord, output_dir: str = "data/escalation") -> str:
    # ... existing JSON write ...

    # Also persist to DB:
    from db.database import SessionLocal
    from db.models import EscalationEvent
    db = SessionLocal()
    try:
        row = EscalationEvent(
            event_id=record.event_id,
            project_id=record.project_id,
            contract_type=record.contract_type,
            current_tier=record.current_tier,
            tier_entered_date=record.tier_entered_date,
            tier_deadline=record.tier_deadline,
            responsible_party=record.responsible_party,
            next_action=record.next_action,
            clause=record.clause,
            notice_text=record.notice_text,
            is_final=record.is_final,
            created_at=str(date.today()),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()
    return path
```

And activate the background job in `api/main.py`:
```python
def daily_background_job():
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
        ) for r in rows]
        agent = EscalationAgent()
        updated = agent.check_expired_tiers(records)
        for rec in updated:
            agent.save_record(rec)
        print(f"[Scheduler] Checked {len(records)} escalation records, {len(updated)} updated.")
    finally:
        db.close()
```

---

## REMAINING PHASE 1 ITEMS (no RAM needed — still not built)

These were in the previous action plan. None of them appear in the current codebase.

---

### ITEM A — EoT Agent not wired into API or triggered by Orchestrator

`agents/eot_agent.py` exists and works (verified by CLI test in the file). But there is **no API endpoint** for it and the Orchestrator's fallback routing includes `"EoT Agent"` as a string but doesn't actually call `EoTAgent()`.

**EXACT FIX — add 2 endpoints to `api/main.py`:**

```python
from agents.eot_agent import EoTAgent
eot_agent = EoTAgent()

@app.post("/process-hindrance-eot")
def process_hindrance_eot(
    project_id: str = Form(...),
    hindrance_id: str = Form(...),
    hindrances: str = Form(...),   # JSON string
    contract_id: str = Form(...),
):
    """Process a hindrance-based EoT claim."""
    import json
    rule_store_path = f"data/rule_store/rule_store_{contract_id}.json"
    if not os.path.exists(rule_store_path):
        raise HTTPException(status_code=404, detail="Rule store not found")
    with open(rule_store_path, encoding="utf-8") as f:
        rule_store = json.load(f)
    hindrance_list = json.loads(hindrances)
    decision = eot_agent.process_hindrance_eot(project_id, hindrance_id, hindrance_list, rule_store)
    path = eot_agent.save_decision(decision)
    return {"decision": dataclasses.asdict(decision), "saved_to": path}

@app.post("/process-fm-eot")
def process_fm_eot(
    project_id: str = Form(...),
    fm_claim: str = Form(...),   # JSON string
    contract_id: str = Form(...),
):
    """Process a Force Majeure EoT claim."""
    import json, dataclasses
    rule_store_path = f"data/rule_store/rule_store_{contract_id}.json"
    if not os.path.exists(rule_store_path):
        raise HTTPException(status_code=404, detail="Rule store not found")
    with open(rule_store_path, encoding="utf-8") as f:
        rule_store = json.load(f)
    claim = json.loads(fm_claim)
    decision = eot_agent.process_fm_eot(project_id, claim, rule_store)
    path = eot_agent.save_decision(decision)
    return {"decision": dataclasses.asdict(decision), "saved_to": path}
```

---

### ITEM B — Contractor dashboard panel has no FM claim or EoT submission form

The Contractor Rep panel currently just shows summary numbers. The spec (EL/06) requires FM claim and EoT forms.

**EXACT FIX — add to `dashboard.py` under `elif role == "Contractor Rep":`:**

```python
elif role == "Contractor Rep":
    st.markdown("### 📋 Contractor View")
    # ... existing summary display ...

    st.markdown("---")
    st.markdown("### 📝 Submit FM Claim")
    with st.form("fm_claim_form"):
        fm_event_id = st.text_input("Event ID (e.g. FM-001)")
        fm_event_date = st.date_input("Date of FM Event")
        fm_category = st.selectbox("Category", ["FORCE_MAJEURE_WEATHER", "FORCE_MAJEURE_POLITICAL", "INDIRECT_POLITICAL"])
        fm_description = st.text_area("Event Description")
        fm_impact = st.text_area("Impact Assessment")
        fm_duration = st.text_input("Estimated Duration (days)")
        fm_mitigation = st.text_area("Mitigation Strategy")
        fm_notice_date = st.date_input("Notice Submitted Date")
        fm_submit = st.form_submit_button("Submit FM Claim")

    if fm_submit and contract_id:
        fm_claim = {
            "event_id": fm_event_id,
            "event_date": str(fm_event_date),
            "category": fm_category,
            "event_description": fm_description,
            "impact_assessment": fm_impact,
            "estimated_duration": fm_duration,
            "mitigation_strategy": fm_mitigation,
            "notice_submitted_date": str(fm_notice_date),
        }
        r = httpx.post(
            f"{API_BASE}/process-fm-eot",
            data={"project_id": contract_id, "fm_claim": json.dumps(fm_claim), "contract_id": contract_id},
            timeout=30
        )
        if r.status_code == 200:
            decision = r.json()["decision"]
            if decision["decision"] == "APPROVED":
                st.success(f"✅ FM Claim APPROVED — {decision['eot_days_approved']} days EoT granted.")
            elif decision["decision"] == "REJECTED":
                st.error(f"❌ FM Claim REJECTED — {decision['rejection_reason']}")
            else:
                st.warning(f"⚠️ FM Claim PARTIALLY APPROVED — {decision['eot_days_approved']} days EoT.")
        else:
            st.error(f"Error: {r.text[:300]}")
```

---

### ITEM C — `eot_agent.py` still skips OPEN hindrances (BUG — ongoing hindrances get 0 EoT)

The fix from the previous report was listed but not applied. Current `calculate_net_eot()`:

```python
for h in hindrances:
    if h.get("status") == "OPEN":
        continue   # ← WRONG: OPEN = ongoing = should use today as end
```

**EXACT FIX:**
```python
from datetime import date as _date

def calculate_net_eot(hindrances: list, today=None) -> tuple[int, int]:
    today = today or _date.today()
    ranges = []
    for h in hindrances:
        start = _parse_date(h.get("date_of_occurrence"))
        if not start:
            continue
        if h.get("status") == "OPEN":
            end = today        # ongoing — count up to today
        else:
            end = _parse_date(h.get("date_of_removal"))
        if start and end and end >= start:
            ranges.append((start, end))
    # ... rest of merge logic unchanged ...
```

---

### ITEM D — `scripts/test_upload.py` uses the old path `data/mock_contracts/NH44_Karnataka_EPC.pdf` which doesn't exist if the mock PDF was not generated

The mock contract generator in `scripts/generate_mock_contract.py` must be run first. Add a check:

```python
# In scripts/test_upload.py, add at top:
import os, subprocess
MOCK_PATH = 'data/mock_contracts/NH44_Karnataka_EPC.pdf'
if not os.path.exists(MOCK_PATH):
    print("[TestUpload] Mock PDF not found — generating...")
    subprocess.run(["python", "scripts/generate_mock_contract.py"], check=True)
```

Or better — use your real test DOCX which already exists in `Fake contracts and reports/`:

```python
# Alternative — use the real contract DOCX instead of the mock PDF:
with open('Fake contracts and reports/CONTRACT_EPC_NH44_KA03.docx', 'rb') as f:
    r = client.post(
        'http://127.0.0.1:8000/upload-contract',
        files={'file': ('CONTRACT_EPC_NH44_KA03.docx', f,
                       'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},
        data={...}
    )
```

---

## REMAINING PHASE 2 ITEMS (Groq API already configured — no RAM needed)

---

### ITEM E — LLM extraction not wired into parser_agent.py (regex-only currently)

The `parser_agent.py` calls `deterministic_extract()` and has no Groq fallback for ambiguous fields. The extraction prompts are fully written in `parser_agent.py` (`EXTRACTION_PROMPTS` dict). They just aren't called.

**EXACT FIX — add Groq fallback in `parse_contract()` after deterministic extraction:**

```python
# In agents/parser_agent.py, after Stage 4 (deterministic extraction):

# Stage 4b: Groq LLM fallback for null/failed fields
print("[ParserAgent] Stage 4b: Groq LLM fallback for unresolved fields...")
for item in EXTRACTION_PLAN:
    target = item["target"]
    if extracted.get(target) is None or unresolved.get(target):
        prompt_template = EXTRACTION_PROMPTS.get(target, DEFAULT_EXTRACTION_PROMPT)
        # Get top-3 chunks for this target via semantic search
        query_emb = get_embed_model().encode([item["query"]])[0].tolist()
        db = SessionLocal()
        try:
            top_chunks = self.vector_store.search(db, contract_id, query_emb, top_k=3)
        finally:
            db.close()
        context = "\n\n---\n\n".join(c["chunk_text"] for c in top_chunks)
        prompt = prompt_template.format(context=context, target=target)
        system = "You are a legal extraction engine. Return ONLY valid JSON. No preamble."
        raw = groq_json_extract(system, prompt)
        if raw:
            try:
                cleaned = raw.strip().lstrip("```json").rstrip("```").strip()
                llm_result = json.loads(cleaned)
                extracted[target] = llm_result
                audit_log[target] = {"method": "groq_llm", "warnings": []}
                unresolved.pop(target, None)
                print(f"  [LLM] {target} resolved via Groq")
            except json.JSONDecodeError as e:
                print(f"  [LLM] {target} JSON parse failed: {e}")
```

---

### ITEM F — W&B experiment tracking not added to `risk_predictor.py`

~1 hour of work. Already described in previous plan. Add after `model.fit()`:

```python
# In agents/risk_predictor.py, inside train_model(), after model.fit():
try:
    import wandb
    wandb.init(project="contractguard-risk", config={
        "n_estimators": 400, "max_depth": 6, "learning_rate": 0.05,
        "n_samples": len(y), "positive_class_pct": float(y.mean()),
        "resampler": "ADASYN" if IMBLEARN_AVAILABLE else "none",
    }, reinit=True)
    # Quick eval on training set (no test split in current synthetic setup)
    preds = model.predict(X)
    from sklearn.metrics import f1_score, precision_score, recall_score
    wandb.log({
        "f1": f1_score(y, preds),
        "precision": precision_score(y, preds),
        "recall": recall_score(y, preds),
        "feature_importance": dict(zip(FEATURE_NAMES, model.feature_importances_.tolist())),
    })
    wandb.finish()
    print("[RiskPredictor] W&B metrics logged.")
except ImportError:
    print("[RiskPredictor] wandb not installed — skipping tracking.")
except Exception as e:
    print(f"[RiskPredictor] W&B logging failed: {e}")
```

---

## PRIORITISED FIX ORDER

**Fix immediately (app broken without these):**

1. **BUG 1** — Verify `pdf_path` is fully renamed to `file_path` in `parser_agent.py` — run `grep -n "pdf_path" agents/parser_agent.py`
2. **BUG 3** — Site Engineer panel: change `st.session_state["last_compliance_result"].get("events", [])` → `st.session_state.get("compliance_events_full", [])`
3. **BUG 5** — SHAP direction: `"Increases risk"` → `"increases_risk"` in `dashboard.py`

**Fix next (functionality gaps):**

4. **ITEM C** — `eot_agent.py` OPEN hindrance bug (produces 0 EoT for ongoing hindrances)
5. **ITEM A** — Wire EoT Agent into API endpoints
6. **BUG 7** — Add `EscalationEvent` DB model + activate background scheduler
7. **BUG 6** — Fix S-curve (marker not fake linear)
8. **ITEM B** — Contractor FM/EoT form in dashboard

**Do after RAM upgrade (or any time with Groq — no local RAM needed):**

9. **ITEM E** — Wire Groq LLM fallback into parser_agent extraction
10. **ITEM F** — Add W&B tracking to risk predictor
11. **ITEM D** — Fix `test_upload.py` to use existing DOCX

---

## Quick Verification Checklist (run these after each fix)

```bash
# 1. Check pdf_path remnant
grep -n "pdf_path" agents/parser_agent.py

# 2. Run the smoke test (all 6 MPR scenarios)
python scripts/smoke_test_mpr.py

# 3. Start API
uvicorn api.main:app --reload --port 8000

# 4. Test compliance pipeline
python scripts/test_compliance.py

# 5. Test risk prediction
python scripts/test_risk.py

# 6. Test contract upload with DOCX
python scripts/test_upload.py   # (after fixing path to use DOCX)

# 7. Full pipeline test
python scripts/test_full_pipeline.py
```

---

## EXECUTION REPORT (COMPLETED)

All tasks listed in this action plan have been successfully executed:

1. **BUG 1 (`parser_agent.py`)**: Confirmed `file_path` is exclusively used. `parse_contract` signature and all downstream logic was correct.
2. **BUG 2 (Stale Ollama Imports)**: Removed commented-out `import ollama` line from `agents/orchestrator.py`. No other stale imports were found across the codebase.
3. **BUG 3 (Site Engineer Panel)**: Updated `dashboard.py` to read `compliance_events_full` from session state, ensuring field action items render.
4. **BUG 4 (Upload Guard)**: Confirmed guard is already in place.
5. **BUG 5 (SHAP Chart Casing)**: Fixed string comparison to `"increases_risk"` so that feature importance bars are colored accurately (red vs green).
6. **BUG 6 (S-Curve Marker)**: Replaced fake linear interpolation of actual progress with a single dynamic marker and a deviation annotation.
7. **BUG 7 (Escalation DB Model)**: Created `EscalationEvent` table in `db/models.py`. Wired `escalation_agent.py` to persist to the DB. Activated `check_expired_tiers` APScheduler job in `api/main.py`. Added missing fields (`contractor_name`, `appointed_date`, `last_actual_pct`, `last_reporting_period`) to `Project` model in `db/models.py`.
8. **ITEM A (EoT Endpoints)**: Added `/process-hindrance-eot` and `/process-fm-eot` to `api/main.py`.
9. **ITEM B (Contractor Form)**: Added the "Submit FM Claim" form to `dashboard.py` for Contractor Rep view.
10. **ITEM C (`eot_agent.py`)**: Updated `calculate_net_eot()` to correctly count days up to `today` for `OPEN` hindrances.
11. **ITEM D (`test_upload.py`)**: Updated script to point to `Fake contracts and reports/CONTRACT_EPC_NH44_KA03.docx`.
12. **ITEM E (`parser_agent.py`)**: Implemented Groq LLM fallback for extraction (Stage 4b).
13. **ITEM F (`risk_predictor.py`)**: Integrated Weights & Biases (W&B) experiment tracking inside `train_model()`.

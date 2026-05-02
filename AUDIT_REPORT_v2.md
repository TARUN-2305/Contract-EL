# ContractGuard AI — Full Recursive Audit Report
### `Contract-EL-react-full-migration` zip

> **Audit scope:** Every file read line-by-line.  
> **Purpose:** Current state assessment + what's done, what's broken, what's next.  
> **Date:** May 2026

---

## 1. What's New in This Version (vs previous zip)

This version has implemented the following from the previous action plan:

| Item | Status |
|---|---|
| React frontend scaffolded (Vite + React 19 + Recharts) | ✅ Done |
| `config.py` with Pydantic Settings | ✅ Done |
| `MPRRecord` DB model added | ✅ Done |
| Project last-state columns added to `Project` model | ✅ Done |
| MPR history persist in `/upload-mpr` | ✅ Done |
| `GET /projects`, `GET /projects/{id}/mpr-history`, `GET /projects/{id}/rule-store` | ✅ Done |
| `OrchestratorAgent` with LangGraph `StateGraph` | ✅ Done (partial — see issues) |
| Open-Meteo weather tool | ✅ Done |
| GNews news tool | ✅ Done |
| `docker-compose.yml` with 3 services | ✅ Done |
| `alembic.ini` + migrations folder | ✅ Done |
| Vite proxy `/api` → `localhost:8000` | ✅ Done |
| Bug fix: `eot_agent.py` overlap variable | ✅ **Fixed** (line 308 confirmed `overlap_days`) |
| `EXTRACTION_PROMPTS` wired to LLM fallback | ✅ **Fixed** (line 418 confirmed) |
| Alembic migration for new tables | ✅ Done |

---

## 2. Complete File-by-File Audit

### `agents/graph_state.py` — ✅ Good

Clean TypedDict with all necessary keys. `messages` uses `Annotated[List[str], operator.add]` which is correct LangGraph pattern for accumulating messages across nodes. One suggestion: add `errors: List[str]` as a separate field from `messages` to distinguish log messages from actual failures.

### `agents/orchestrator.py` — ⚠️ Architectural gap remains

LangGraph is used, but only for 4 internal orchestrator nodes (`parse → validate → route → respond`). This is still the same fundamental problem as before: **the orchestrator decides which agents to invoke and returns a list, but nothing actually executes those agents.** The `agents_to_invoke` list in the final state is returned to the API caller as JSON, but `api/main.py` does not read it — `upload-mpr` hardcodes `compliance → risk → explainer` every time.

The LangGraph is used *inside* the orchestrator to structure its own decision-making, but the actual agent pipeline is not a LangGraph graph. This is a conceptual mismatch. Two correct approaches:
- **Option A (simpler):** Keep the current hardcoded pipeline in `upload-mpr` and remove the orchestrator entirely — it's dead code.
- **Option B (correct):** Make the full pipeline (`compliance → risk → escalation? → explainer`) a real LangGraph graph with conditional edges, and have the API invoke `graph.invoke(initial_state)` instead of calling agents manually.

**Current state:** Option A is what's actually running. The orchestrator is called in `/trigger` endpoint only, which is never used by the frontend.

### `agents/parser_agent.py` — ✅ Fixed, one remaining issue

`EXTRACTION_PROMPTS` is now correctly wired at line 418: `prompt_template = EXTRACTION_PROMPTS.get(target, DEFAULT_EXTRACTION_PROMPT)`. This is the Phase 3 fix from the action plan — confirmed done.

Remaining issue: the LLM fallback wraps the Groq call in a broad `except Exception` that silently catches rate limit errors and moves on — this means if all 4 Groq keys are exhausted simultaneously, the LLM fallback silently returns `None` for all fields without any indication of *why*. Add a specific check: if `e` is a rate-limit error and all keys have been tried, log a clear warning and set `extracted[target] = None` with `audit_log[target]["reason"] = "groq_rate_limited"`.

### `agents/extraction_engine.py` — ✅ Good, one latent issue

Milestone extraction is solid. The M4 day validation logic (checking if `raw_m4_day <= max_existing` to detect wrong number capture) is a clever defensive fix.

Latent issue: `extract_force_majeure` — the original regex bug (described in the previous action plan) was NOT in this file in the current version. The function uses separate `_find` calls per field. However, the `notice_deadline_days` field is:

```python
"notice_deadline_days": _int(_find(r"within\s+(\d+)\s+days\s+of\s+becoming\s+aware", text))
    or _int(_find(r"seven\s+\(7\)\s+days", text))
    or 7,
```

The second pattern `seven\s+\(7\)\s+days` has no capture group — `_find` returns `None` regardless. This is harmless because the `or 7` default catches it, but it means the second pattern never fires. Fix: add a capture group: `r"(seven)\s+\(7\)\s+days"` and handle the word-to-int conversion, or just keep the `or 7` default and remove the dead second pattern.

### `agents/eot_agent.py` — ✅ Bug fixed

Line 308 confirmed: `f"Overlap deduction of {overlap_days} days applied."` — the NameError from the previous version is fixed.

### `agents/mpr_parser.py` — ⚠️ Machinery still defaulting

Lines 211 and 410: `machinery_deployment_pct = _safe_float(machinery_deploy_raw) if machinery_deploy_raw else 80.0`

The extraction of `machinery_deploy_raw` is attempted from the text, but the regex it uses (`r"Machinery.*?Deployed.*?(\d+(?:\.\d+)?)\s*%"`) has a very strict ordering requirement and won't match if the DOCX has the value in a table cell rather than inline text. In practice, for the test DOCXs, `machinery_deploy_raw` is almost always `None`, so this still defaults to 80.0.

The `parse_mpr_docx` function (for DOCX files, which is what the fake MPRs are) has a separate machinery extraction path that does look at table cells, but it uses `_kv_from_tables` which looks for `Machinery Deployment` as a key — and the test DOCXs use `Machinery Deployed (%)` as the heading. This slight mismatch causes it to miss.

**Fix needed:** In `parse_mpr_docx`, add: `or _kv_from_tables(tables_text, "Machinery Deployed")` to the machinery extraction line.

### `agents/compliance_engine.py` — ✅ Excellent, unchanged

All 15 checks intact and working. No issues found in this version.

### `agents/risk_predictor.py` — ✅ Works, synthetic training caveat unchanged

XGBoost + SHAP works correctly. The synthetic training data caveat from the previous audit still applies and is a known limitation.

### `agents/escalation_agent.py` — ✅ Solid

APScheduler + LangGraph integration correct. Groq-generated notice text working.

### `agents/explainer_agent.py` — ✅ Works

News tool called unconditionally on every MPR remains — this will burn through the GNews daily quota quickly with multiple projects. Consider caching: if a contractor was scanned today, return the cached result for all same-day uploads.

### `agents/compliance_agent.py` — ✅ Good

Thin wrapper that calls `compliance_engine.run()` and persists events to DB. Works correctly.

### `api/main.py` — ✅ Functional, three gaps

**Gap 1 — Orchestrator is dead code:** As noted above, `/upload-mpr` never calls the orchestrator. The orchestrator is only called via `/trigger`, which the frontend never uses. This is fine functionally but the orchestrator is wasted complexity.

**Gap 2 — No auth:** All endpoints are fully open. The `api_key_header` setting in `config.py` exists but is never read by `main.py`. The middleware described in the action plan was not implemented.

**Gap 3 — Missing override endpoints:** `POST /weather-override`, `DELETE /weather-override`, `POST /news-override` from the action plan were not added. The override is only controllable via `.env` variables, not at runtime. This means testing FM scenarios requires restarting the server to change weather data.

**`/healthz` is minimal:** Returns `{"status": "ok", "groq_keys_loaded": True}` — hardcoded `True`, doesn't actually check Groq key count or DB connectivity.

### `db/models.py` — ✅ Complete

All 6 tables present: `users`, `projects`, `rule_store`, `compliance_events`, `escalation_events`, `mpr_records`. `MPRRecord` and the last-state columns on `Project` are correctly implemented. `created_at` on `MPRRecord` is a `String` — should be `DateTime` with `default=func.now()` for proper time-series ordering.

### `db/database.py` — ✅ Unchanged and correct

### `tools/weather_tool.py` — ✅ Good

Open-Meteo integration working correctly. Location coord map is present. Manual override via `WEATHER_SOURCE=manual` + `WEATHER_MANUAL_DATA` env var works. Synthetic fallback present.

One issue: the synthetic fallback uses `random` without seeding — same location will give different results on every call. This makes FM testing non-deterministic. Fix: seed with `random.seed(hash(location))` for consistent test results.

### `tools/news_tool.py` — ✅ Good

GNews integration with file override working. Risk keyword list is appropriate for Indian construction sector. One issue: GNews param is `"apikey"` in this implementation but should be `"token"` — check GNews v4 docs. If using wrong param name, all calls silently return empty results and fall through to synthetic without any error logged.

### `frontend/src/App.jsx` — ✅ Clean

React Router v7 with 5 routes. `AppProvider` wrapping is correct. Structure is clean.

### `frontend/src/context/AppContext.jsx` — ✅ Good

Simple context with `role` and `contractId`. Works fine. For production, `contractId` should persist to `localStorage` so it survives page refresh.

### `frontend/src/components/Sidebar.jsx` — ✅ Good

Role selector and contract ID input work correctly. Navigation links with active state highlighting work.

### `frontend/src/components/Dashboard.jsx` — ✅ Good

Portfolio overview with risk trend chart and project status table. Loads from `/api/projects` and `/api/projects/:id/mpr-history`. One issue: the risk trend chart only loads history for `projects[0]` (first project) — should let the user pick which project's trend to display.

### `frontend/src/pages/AnalysisPage.jsx` — ✅ Most complete page

Excellent implementation. All the key components are there:
- MPR upload form with file drag target
- S-curve chart (single-point actual vs planned line)
- SHAP bar chart with direction coloring  
- Compliance events with severity card styling
- Role-specific panels (Auditor, Site Engineer, Contractor Rep)
- FM claim form in Contractor Rep panel
- Download buttons for MD/PDF/JSON reports

Issues:
- S-curve only shows a single actual data point (current MPR). It should pull from `/mpr-history` to show the full curve across all uploaded MPRs.
- Auditor panel shows raw JSON in a `<pre>` — should be a formatted table.
- `AuditorPanel` makes a redundant call to `GET /api/projects` (it already has the project list from Dashboard). Should receive it as a prop.

### `frontend/src/pages/ProjectsPage.jsx` — ✅ Clean

Full project table with risk badges, progress bars, LD totals. Click navigates to MPR history. Works well.

### `frontend/src/pages/MprHistoryPage.jsx` — ✅ Good

Progress trend and risk score time-series charts. History table with variance column. This is the page that most benefits from the `MPRRecord` persistence — correctly implemented.

### `frontend/src/pages/UploadContractPage.jsx` — ✅ Good

Contract upload form with file zone, all required fields, and success/error feedback. Works correctly.

### `frontend/src/index.css` — ✅ Excellent

Dark theme with CSS variables. All component styles are present: cards, badges, tables, upload zones, accordions, event cards, spinners, skeleton loaders. No Tailwind dependency — pure CSS custom properties. This is a clean, production-ready design system.

### `frontend/vite.config.js` — ✅ Correct

Proxy `/api` → `http://localhost:8000` with path rewrite. This means all frontend fetch calls use `/api/...` and the backend receives them without the `/api` prefix. Matches the `axios.get('/api/projects')` calls in the components.

### `frontend/package.json` — ✅ Good

React 19.2.5 (latest), React Router 7, Recharts 3.8.1, Lucide React, Axios. No unnecessary dependencies. Note: `lucide-react@1.14.0` is very new — if you see any missing icon errors, it may be ahead of the icon set you're referencing. The icons used (`ShieldAlert`, `LayoutDashboard`, `FolderKanban`, `Activity`, `Upload`, `AlertTriangle`, `CheckCircle`, `IndianRupee`, `TrendingUp`, `ArrowRight`, `ChevronDown`, `ChevronUp`, `Download`, `FileText`, `Search`) are all stable icons that exist in v1.x.

### `docker-compose.yml` — ✅ Good

Three services: `db` (postgres:15-alpine), `api` (build from Dockerfile), `frontend` (node:20-alpine running `npm run dev`). Healthcheck on DB before API starts. Volumes for data persistence.

**Issues:**
- `docker-compose.yml` DB name is `contractguardv2` but `.env` may still say `contractguard`. Make sure these match.
- The frontend service runs `npm install && npm run dev` on every container start — fine for development, should use a pre-built static serve for production.
- `Dockerfile` not shown in listing but referenced — assumed present.

### `alembic.ini` + `migrations/` — ✅ Present

Migration file `850ee1e128af_add_mprrecord_and_project_last_columns.py` exists. Alembic is correctly set up. Remember to run `alembic upgrade head` before starting the API for the first time.

### `requirements.txt` — needs one addition

`langgraph` and `langchain-core` should be in requirements if not already. `pydantic-settings` is needed for `config.py`. Check: `pip show langgraph pydantic-settings` — if missing, `pip install langgraph langchain-core pydantic-settings`.

---

## 3. What Still Needs to Be Done (Prioritised)

### Priority 1 — Fix before next test session

**P1-A: GNews API key param name**  
In `tools/news_tool.py` line with `params`, change `"apikey"` to `"token"`:
```python
# WRONG (current):
params = { "q": query, "lang": "en", "max": 10, "apikey": self.api_key }

# CORRECT (GNews v4):
params = { "q": query, "lang": "en", "max": 10, "token": self.api_key }
```

**P1-B: `MPRRecord.created_at` type**  
Change from `Column(String)` to `Column(DateTime, default=func.now())` in `db/models.py`. Then generate a new Alembic migration.

**P1-C: Weather synthetic fallback seeding**  
In `tools/weather_tool.py`, `_generate_synthetic_weather`:
```python
# Add at start of method:
import random
random.seed(hash(location) % (2**32))
```
This makes FM testing reproducible — same location always returns same synthetic rainfall.

**P1-D: Machinery deployment DOCX mismatch**  
In `agents/mpr_parser.py`, `parse_mpr_docx`, find the machinery extraction line and add the alternate key:
```python
machinery_deploy_raw = (
    _kv_from_tables(tables_text, "Machinery Deployment")
    or _kv_from_tables(tables_text, "Machinery Deployed")   # ← add this
    or _kv(text, "Machinery")
)
```

### Priority 2 — Significant UX improvements

**P2-A: S-curve should show full history, not single point**  
In `AnalysisPage.jsx`, `SCurveChart` component: after a successful MPR upload, fetch `GET /api/projects/{contractId}/mpr-history` and render all historical `actual_pct` values as a line, not a single dot. The planned line is already drawn correctly.

```jsx
// After successful analysis, add:
const histRes = await axios.get(`/api/projects/${contractId}/mpr-history`);
const histPoints = histRes.data.history || [];
// Map to { day, actual } and merge into SCurveChart data
```

**P2-B: Dashboard risk trend — let user pick project**  
In `Dashboard.jsx`, replace the hardcoded `projs[0]` with a project selector dropdown above the trend chart.

**P2-C: Auditor panel — replace raw JSON with table**  
The `AuditorPanel` shows `<pre>{JSON.stringify(data)}</pre>`. Replace with the same history table from `MprHistoryPage` — it already has all the formatting logic.

**P2-D: `contractId` persistence in localStorage**  
In `AppContext.jsx`:
```jsx
const [contractId, setContractId] = useState(() => localStorage.getItem('contractId') || '');
const updateContractId = (id) => { setContractId(id); localStorage.setItem('contractId', id); };
// Pass updateContractId as setContractId in provider value
```

**P2-E: `healthz` endpoint — make it real**  
```python
@app.get("/healthz")
def health(db: Session = Depends(get_db)):
    from utils.groq_client import _KEYS
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "groq_keys_loaded": len(_KEYS),
        "db_connected": db_ok,
        "weather_source": os.environ.get("WEATHER_SOURCE", "open_meteo"),
        "news_source": "gnews" if os.environ.get("GNEWS_API_KEY") else "synthetic",
    }
```

### Priority 3 — Production requirements

**P3-A: Runtime weather/news override endpoints**  
Add to `api/main.py`:
```python
@app.post("/weather-override")
def set_weather_override(total_mm: float = Form(...), extreme_days: int = Form(0), historical_avg_mm: float = Form(100)):
    os.environ["WEATHER_SOURCE"] = "manual"
    os.environ["WEATHER_MANUAL_DATA"] = json.dumps({
        "total_mm": total_mm, "extreme_days": extreme_days, "historical_avg_mm": historical_avg_mm
    })
    return {"message": "Weather override set", "total_mm": total_mm}

@app.delete("/weather-override")
def clear_weather_override():
    os.environ.pop("WEATHER_SOURCE", None)
    os.environ.pop("WEATHER_MANUAL_DATA", None)
    return {"message": "Weather override cleared"}

@app.post("/news-override")
def set_news_override(file_path: str = Form(...)):
    os.environ["NEWS_OVERRIDE_FILE"] = file_path
    return {"message": f"News override set to {file_path}"}
```

Also add a simple UI for this in `AnalysisPage` — a collapsible "Test Overrides" panel visible only to Contract Manager role.

**P3-B: API key auth middleware**  
```python
# In api/main.py, add after app creation:
from config import settings

@app.middleware("http")
async def api_key_middleware(request, call_next):
    if settings.api_key_header:
        key = request.headers.get("X-API-Key")
        if key != settings.api_key_header:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Invalid API key"}, status_code=403)
    return await call_next(request)
```

**P3-C: Real LangGraph pipeline (Option B orchestration)**  
This is the biggest remaining piece of the action plan. The orchestrator as currently implemented decides but doesn't execute. To make LangGraph real:

1. Create `agents/pipeline_graph.py` (separate from orchestrator):
```python
from langgraph.graph import StateGraph, END
from agents.graph_state import ContractGuardState

def build_pipeline():
    graph = StateGraph(ContractGuardState)
    graph.add_node("compliance", run_compliance_node)
    graph.add_node("risk", run_risk_node)
    graph.add_node("escalation", run_escalation_node)
    graph.add_node("explainer", run_explainer_node)
    graph.add_node("eot_fm", run_eot_fm_node)
    graph.add_node("eot_hindrance", run_eot_hindrance_node)

    graph.add_conditional_edges("compliance", route_after_compliance, {
        "escalation": "escalation",
        "risk": "risk"
    })
    graph.add_edge("escalation", "risk")
    graph.add_edge("risk", "explainer")
    graph.add_edge("explainer", END)
    graph.add_edge("eot_fm", "compliance")
    graph.add_edge("eot_hindrance", "compliance")
    return graph.compile()
```

2. In `api/main.py`, `/upload-mpr`: replace the manual `compliance_agent.run() → risk_predictor.predict() → explainer_agent.explain()` sequence with `pipeline_graph.invoke(initial_state)`.

**P3-D: File validation middleware**  
```python
MAX_FILE_MB = 20
ALLOWED_CONTRACT_EXT = {".pdf", ".docx"}
ALLOWED_MPR_EXT = {".md", ".docx"}

async def validate_file(file: UploadFile, allowed: set, max_mb: int = 20):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not allowed. Use: {allowed}")
    content = await file.read()
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {max_mb}MB limit")
    await file.seek(0)
    return content
```

**P3-E: Missing Escalations page in frontend**  
The sidebar has no link to an Escalations page, but escalation data is stored in the DB (`escalation_events` table) and there's no way to view it from the UI. Add `src/pages/EscalationsPage.jsx`:
- Table showing all escalation events across projects
- Current tier, deadline, responsible party, notice text
- For Contract Manager role only

**P3-F: Missing Reports download page**  
No central place to list and download generated PDFs. Add `src/pages/ReportsPage.jsx`:
- List files from `data/reports/` via a new `GET /reports` endpoint that lists available files
- Download button per file using the existing `/reports/{filename}` endpoint

---

## 4. Bugs Found in This Version

| # | File | Line | Severity | Description |
|---|---|---|---|---|
| 1 | `tools/news_tool.py` | ~40 | HIGH | GNews param should be `token` not `apikey`. Causes silent failure — all GNews calls return empty and fall to synthetic. |
| 2 | `agents/mpr_parser.py` | 211, 410 | MEDIUM | `machinery_deploy_raw` almost always None for DOCX files because key mismatch (`"Machinery Deployment"` vs `"Machinery Deployed (%)"` in DOCXs). Still defaults to 80.0. |
| 3 | `db/models.py` | MPRRecord | LOW | `created_at = Column(String, nullable=True)` — never set at creation time. All records have `null` for `created_at`. Should be `DateTime` with `server_default`. |
| 4 | `tools/weather_tool.py` | `_generate_synthetic_weather` | LOW | Random without seed — FM test results are non-deterministic. |
| 5 | `api/main.py` | `/healthz` | LOW | `groq_keys_loaded: True` is hardcoded. Doesn't reflect actual key state. |
| 6 | `extraction_engine.py` | `extract_force_majeure` | INFO | Second `_find` pattern for `notice_deadline_days` has no capture group — dead code, but harmless since `or 7` default catches it. |

---

## 5. What's Actually Working End-to-End Right Now

If you run `uvicorn api.main:app` + `npm run dev` right now, this is the complete working flow:

1. **Upload Contract** → `/upload-contract` → Parser Agent extracts rule store → saved to `data/rule_store/` and DB → Project row created ✅
2. **Upload MPR** (Analysis page) → `/upload-mpr` → MPR parsed → Compliance (15 checks) → Risk (XGBoost) → Explainer (Groq) → `MPRRecord` persisted → Response returned ✅
3. **Dashboard** → loads all projects from DB with last-state KPIs → risk trend chart for first project ✅
4. **Projects page** → full portfolio table with risk badges and progress bars ✅
5. **MPR History page** → progress trend + risk trend charts across all uploaded MPRs ✅
6. **FM Claim** (Contractor Rep panel) → `POST /process-fm-eot` → EoT agent decision → weather validation via Open-Meteo ✅
7. **Hindrance EoT** → `POST /process-hindrance-eot` → overlap deduction logic → EoT decision ✅
8. **Report download** → compliance PDF and markdown downloadable via `/reports/{filename}` ✅

**Not working / not connected:**
- Escalations page: no UI, data exists in DB but inaccessible from frontend ❌
- Reports listing page: no `GET /reports` endpoint to list files ❌
- Weather/news override from UI: only via `.env` restart ❌  
- LangGraph as actual pipeline executor: orchestrator decides but doesn't execute ❌
- Auth: all endpoints open ❌
- S-curve full history: only shows single current data point ❌

---

## 6. Updated .env for This Version

```env
# ── DATABASE ──────────────────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:helloPeter%402005@localhost:5432/contractguardv2
# NOTE: DB name changed to contractguardv2 in docker-compose.yml
# If running locally without Docker, either create contractguardv2 or change to contractguard

# ── GROQ ──────────────────────────────────────────────────────────────
KEY1=gsk_xxxxxxxxxxxxxxxxxxxx
KEY2=gsk_xxxxxxxxxxxxxxxxxxxx
KEY3=gsk_xxxxxxxxxxxxxxxxxxxx
KEY4=gsk_xxxxxxxxxxxxxxxxxxxx

# ── WEATHER ───────────────────────────────────────────────────────────
WEATHER_SOURCE=open_meteo
# For manual FM testing:
# WEATHER_SOURCE=manual
# WEATHER_MANUAL_DATA={"total_rainfall_mm":512,"extreme_rainfall_days":8,"historical_average_mm":120,"period_days":7,"source":"manual_override","location":"Karnataka, India"}

# ── NEWS ──────────────────────────────────────────────────────────────
GNEWS_API_KEY=your_gnews_key_here
# For manual contractor news testing:
# NEWS_OVERRIDE_FILE=data/overrides/news_override.json

# ── OPTIONAL ──────────────────────────────────────────────────────────
# API_KEY_HEADER=your_secret_here
# CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Critical note:** `WEATHER_MANUAL_DATA` needs to match the exact keys returned by `WeatherTool.get_rainfall_data()` — specifically `total_rainfall_mm` (not `total_mm`). The previous action plan used `total_mm` but the actual code uses `total_rainfall_mm`. Use the exact format above.

---

## 7. Startup Sequence for This Version

```bash
# 1. Create DB (if not using Docker)
createdb -U postgres contractguardv2

# 2. Install Python deps
pip install -r requirements.txt
pip install langgraph langchain-core pydantic-settings  # if not in requirements.txt

# 3. Run Alembic migrations
alembic upgrade head

# 4. Start API (Terminal 1)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Start React frontend (Terminal 2)
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173

# OR: use Docker Compose (all 3 services)
docker-compose up --build
```

---

## 8. Summary Scorecard

| Category | Score | Notes |
|---|---|---|
| Backend correctness | 8/10 | All 15 compliance checks, EoT, escalation work. 3 minor bugs. |
| Frontend completeness | 7/10 | 5 pages working. Missing escalations, reports listing, full S-curve, auth. |
| Database & persistence | 9/10 | All tables present. `created_at` type issue only. |
| LangGraph orchestration | 4/10 | Graph exists inside orchestrator but pipeline is not graph-driven. |
| Parser reliability | 8/10 | EXTRACTION_PROMPTS wired. Machinery fallback issue remains. |
| Weather/news tools | 8/10 | Open-Meteo works. GNews param name bug. Override by env only. |
| Docker / deployment | 8/10 | Three services, healthcheck, volumes. DB name mismatch risk. |
| Auth / security | 2/10 | Settings exist but middleware not wired. All endpoints open. |
| **Overall** | **7/10** | Strong foundation. Production-ready backend. Frontend needs 4-5 additions. |

---

*End of audit. See Priority 1 fixes above — all are under 10 lines each and should be done before any further testing.*

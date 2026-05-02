# ContractGuard AI — Audit Report v3
### `Contract-EL-react-full-migration` (latest zip)

> **Previous audit:** `AUDIT_REPORT_v2.md`  
> **Scope:** Every file read recursively. Cross-referenced against walkthrough.md claims.  
> **Verdict summary:** All P1 bugs fixed. All P2 UX improvements implemented. Most P3 items done. 3 real bugs remain — one is a **silent API routing crash** that will break the Escalations and Reports pages entirely.

---

## 1. What Was Claimed vs What Was Actually Done

| Walkthrough claim | Verified? | Notes |
|---|---|---|
| S-Curve shows full historical trajectory | ✅ Done | `SCurveChart` now accepts `history` prop, fetches from `/mpr-history`, maps all historical points |
| Dashboard risk trend project selector dropdown | ✅ Done | `trendProjectId` state, separate `useEffect` on change, dropdown at line 107 |
| Auditor panel replaced with formatted table | ✅ Done | Replaced `<pre>` JSON dump with proper `<table>` with columns |
| `contractId` localStorage persistence | ✅ Done | `AppContext.jsx` uses `localStorage.getItem('contractId')` as initial state |
| `role` localStorage persistence | ❌ NOT done | Only `contractId` is persisted. `role` resets to `'Contract Manager'` on every page reload |
| `/healthz` real DB check | ✅ Done | Now queries `SELECT 1` and returns `groq_keys_loaded`, `db_connected`, `weather_source`, `news_source` |
| Admin Overrides page (`AdminPage.jsx`) | ✅ Done | Full weather + news override UI with JSON textarea |
| Runtime weather/news override endpoints | ✅ Done | `POST /admin/weather-override` and `POST /admin/news-override` |
| File size validation (10MB max) | ✅ Done | Check at top of `/upload-mpr` |
| File type validation (.md and .docx only) | ✅ Done | Extension check present |
| `X-API-Key` middleware | ✅ Done | Middleware present, gated by `REQUIRE_API_KEY=true` env var |
| True LangGraph pipeline (`pipeline_graph.py`) | ✅ Done | `pipeline_app.invoke(state)` now called in `/upload-mpr` |
| `EscalationsPage.jsx` | ✅ Done | Table with tier badges, deadlines, responsible party |
| `ReportsPage.jsx` | ✅ Done | File listing with download links |
| New routes in `App.jsx` + Sidebar | ✅ Done | All 3 new routes registered and linked |
| GNews `token` param fix | ✅ Done | Line 46 confirmed `"token": self.api_key` |
| `created_at` DateTime migration | ✅ Done | Migration `b49dcac55fe5` correctly alters column to `DateTime` |
| Weather synthetic fallback seeding | ✅ Done | `random.seed(hash(location) % (2**32))` at line 94 |
| Machinery DOCX key mismatch fix | ✅ Done | Line 210: now tries both `"Machinery Deployment"` and `"Machinery Deployed"` |
| `requirements.txt` updated | ❌ NOT done | `langgraph`, `langchain-core`, `pydantic-settings` are missing. App will crash on import. |

---

## 2. New Bugs Found in This Version

### 🔴 BUG 1 — Critical: Route prefix double-nesting breaks Escalations and Reports

**File:** `api/main.py`  
**Lines:** 611, 630  
**Severity:** CRITICAL — both new pages return 404 in the browser  

The Vite dev proxy strips `/api` from the path before forwarding to FastAPI. So a frontend call to `/api/escalations` becomes `GET /escalations` at the FastAPI server. But the endpoint is registered as `@app.get("/api/escalations")` — FastAPI sees it as `/api/escalations`. The Vite proxy has already removed `/api`, so FastAPI receives `/escalations` and finds no route → **404**.

The same issue affects `GET /api/reports/list`.

All other endpoints (`/projects`, `/upload-mpr`, `/healthz` etc.) are registered **without** the `/api` prefix and work correctly because the proxy strips it. These two new endpoints were accidentally registered with it.

**Fix (2 lines):**
```python
# In api/main.py, change:
@app.get("/api/escalations")     →  @app.get("/escalations")
@app.get("/api/reports/list")    →  @app.get("/reports/list")

# Frontend calls stay the same:
# axios.get('/api/escalations')  → proxy strips /api → FastAPI receives /escalations ✅
# axios.get('/api/reports/list') → proxy strips /api → FastAPI receives /reports/list ✅
```

---

### 🔴 BUG 2 — Critical: `requirements.txt` missing LangGraph and Pydantic Settings

**File:** `requirements.txt`  
**Severity:** CRITICAL — `uvicorn api.main:app` will crash on startup with `ModuleNotFoundError`  

`pipeline_graph.py` imports `from langgraph.graph import StateGraph, END`.  
`agents/orchestrator.py` imports `from langgraph.graph import StateGraph, END`.  
`config.py` imports `from pydantic_settings import BaseSettings`.  

None of these are in `requirements.txt`. The app will fail to start on any fresh install.

**Fix — add to `requirements.txt`:**
```
langgraph>=0.2.0
langchain-core>=0.3.0
pydantic-settings>=2.0.0
```

---

### 🟡 BUG 3 — Medium: `MPRRecord.created_at` still `String` in the model

**File:** `db/models.py`  
**Line:** 87  
**Severity:** MEDIUM — `created_at` for `MPRRecord` is set correctly in `EscalationEvent` (line 55: `DateTime, default=func.now()`) but `MPRRecord` at line 87 still says `Column(String, nullable=True)`. The Alembic migration correctly alters the DB column to `DateTime`, but the SQLAlchemy model still declares it as `String` — meaning new records inserted after migration will pass Python's `None` (never set) since there's no `default=func.now()` in the model declaration. The column type mismatch between model and DB can cause silent insert failures on some PostgreSQL configurations.

**Fix:**
```python
# db/models.py, MPRRecord class, line 87:
# CHANGE:
created_at = Column(String, nullable=True)
# TO:
from sqlalchemy import DateTime
from sqlalchemy.sql import func
created_at = Column(DateTime, default=func.now())
```

---

### 🟡 BUG 4 — Medium: News manual override from Admin UI is not read by `NewsTool`

**File:** `tools/news_tool.py` + `api/main.py`  
**Severity:** MEDIUM — Admin UI "Apply News Override" does nothing to actual news fetches  

The `POST /admin/news-override` endpoint sets `os.environ["NEWS_MANUAL_DATA"]` from the `manual_articles` payload. But `NewsTool.__init__` reads `NEWS_OVERRIDE_FILE` (a file path), not `NEWS_MANUAL_DATA`. There is no code in `NewsTool.get_entity_news()` that checks for `NEWS_MANUAL_DATA`. So when Admin UI injects news articles, they are stored in an env var that nobody reads.

The weather override works because `WeatherTool` reads `WEATHER_MANUAL_DATA` directly. The news tool needs the same pattern.

**Fix — add to `tools/news_tool.py`, inside `get_entity_news()`, before the API call:**
```python
# After the file override check, add:
manual_data = os.environ.get("NEWS_MANUAL_DATA")
if manual_data:
    try:
        articles = json.loads(manual_data)
        return self._analyze_articles(articles)
    except Exception as e:
        print(f"[NewsTool] NEWS_MANUAL_DATA parse error: {e}")
```

---

### 🟡 BUG 5 — Medium: `role` not persisted in localStorage

**File:** `frontend/src/context/AppContext.jsx`  
**Severity:** MEDIUM — role resets to 'Contract Manager' on every page reload  

The walkthrough claims role persistence was implemented. It was not. Only `contractId` uses `localStorage`. The role selector reverts on refresh, which is disruptive for Site Engineers and Contractor Reps who want to stay in their role across sessions.

**Fix:**
```jsx
// AppContext.jsx
const [role, setRole] = useState(() => localStorage.getItem('role') || 'Contract Manager');

const updateRole = (r) => {
  setRole(r);
  localStorage.setItem('role', r);
};

// In provider value: pass updateRole as setRole
<AppContext.Provider value={{ role, setRole: updateRole, contractId, setContractId: updateContractId }}>
```

---

### 🟢 BUG 6 — Low: Pipeline graph `DummyPrediction` antipattern

**File:** `api/main.py`  
**Lines:** ~505–510  
**Severity:** LOW — works but is brittle  

After invoking `pipeline_app.invoke(state)`, the code creates a `DummyPrediction` class to hold risk fields extracted from the dict:

```python
class DummyPrediction: pass
prediction = DummyPrediction()
prediction.risk_score = risk_dict.get("risk_score", 0.0)
```

This is fragile — if `risk_dict` is `None` (e.g. if the risk node crashes), `risk_dict.get()` throws `AttributeError`. Since the whole block is wrapped in a broad `except Exception`, this silently returns a 500 with no useful error message.

**Fix:** Replace with a proper dict access pattern:
```python
# Replace the DummyPrediction block with:
risk_score = risk_dict.get("risk_score", 0.0) if risk_dict else 0.0
risk_label = risk_dict.get("risk_label", "UNKNOWN") if risk_dict else "UNKNOWN"
risk_ttd = risk_dict.get("time_to_default_estimate_days") if risk_dict else None
risk_factors = risk_dict.get("top_risk_factors", []) if risk_dict else []
```

---

## 3. Remaining Open Items (Not Yet Done)

These were in the previous action plan but are still not implemented:

| Item | Why it matters |
|---|---|
| `role` localStorage persistence | Role resets on refresh — annoying for non-PM roles |
| LangGraph conditional routing for FM/escalation triggers | Pipeline is linear only: compliance → risk → explainer. FM claims don't go through EoT agent in the pipeline, they use separate `/process-fm-eot` endpoint. The full conditional graph described in the action plan (FM → eot_fm → compliance → risk → explainer) is not wired. |
| `pipeline_graph.py` has no error handling per node | If compliance agent crashes (e.g. rule store missing a key), the entire LangGraph invoke fails silently inside the broad `except`. Each node should `try/except` and write to `state["messages"]`. |
| `mpr_parser.py` `.md` path machinery extraction | Line 409 for `.md` files still only checks `_kv(text, "Machinery Deployment")` — the second key variant `"Machinery Deployed"` was only added to the DOCX path (line 210). The `.md` parser still defaults to 80.0. |
| Upload contract file type validation | `/upload-contract` has no file size or type check. Only `/upload-mpr` was validated. |
| `DummyPrediction` antipattern | See Bug 6 above |

---

## 4. Full Status Scorecard

| Category | v2 Score | v3 Score | Change |
|---|---|---|---|
| Backend correctness | 8/10 | 9/10 | LangGraph pipeline real now, override endpoints added |
| Frontend completeness | 7/10 | 9/10 | 3 new pages, S-curve history, dropdown, auditor table |
| Database & persistence | 9/10 | 9/10 | Migration correct, model still has String issue |
| LangGraph orchestration | 4/10 | 7/10 | Pipeline is now real but linear only — no FM/escalation branches |
| Parser reliability | 8/10 | 8/10 | Unchanged — .md machinery path still defaults to 80 |
| Weather/news tools | 8/10 | 9/10 | Seeded, token fixed. News manual override not wired. |
| Docker / deployment | 8/10 | 8/10 | requirements.txt missing 3 packages — breaks fresh install |
| Auth / security | 2/10 | 6/10 | Middleware implemented but opt-in only via env var |
| **Overall** | **7/10** | **8/10** | Good progress. 2 critical bugs need fixing before demo. |

---

## 5. Priority Fix List Before Demo

Do these in order. All are small.

### Must-fix (will visibly break during demo)

**Fix 1 — Route prefix (5 min)**  
In `api/main.py`: change `@app.get("/api/escalations")` → `@app.get("/escalations")` and `@app.get("/api/reports/list")` → `@app.get("/reports/list")`. Without this, clicking Escalations or Reports in the sidebar returns an empty white screen.

**Fix 2 — requirements.txt (2 min)**  
Add `langgraph>=0.2.0`, `langchain-core>=0.3.0`, `pydantic-settings>=2.0.0`. Without this, any fresh `pip install -r requirements.txt` + `uvicorn` startup crashes before serving a single request.

### Should-fix (breaks a demo feature)

**Fix 3 — News manual override wiring (15 min)**  
Add `NEWS_MANUAL_DATA` env var check in `NewsTool.get_entity_news()`. Admin UI news override currently does nothing. This matters for the FM political/riot validation demo.

**Fix 4 — MPRRecord model `created_at` (5 min)**  
Change `Column(String, nullable=True)` → `Column(DateTime, default=func.now())` in `MPRRecord`. MPR history timestamps are all `null` right now.

**Fix 5 — `role` localStorage (10 min)**  
Add `localStorage.getItem('role')` and `localStorage.setItem('role', r)` to `AppContext.jsx`. The walkthrough said this was done — it wasn't.

### Nice-to-fix (polish)

**Fix 6 — DummyPrediction → dict access** (5 min)  
**Fix 7 — Upload contract file validation** (10 min)  
**Fix 8 — `.md` parser machinery key** (2 min, add `or _kv(text, "Machinery Deployed")` to line 409)

---

## 6. What Is Fully Working Right Now

Assuming fixes 1 and 2 are applied:

- ✅ Full pipeline: Upload Contract → Upload MPR → LangGraph compliance/risk/explainer → DB persist → response
- ✅ Dashboard: portfolio KPIs, project dropdown risk trend, project status table
- ✅ Projects page: full table, click → MPR History
- ✅ MPR History: progress trend + risk trend charts, history table with variance
- ✅ Analysis page: S-curve with full history, SHAP chart, compliance events by severity, role panels, FM claim form, report downloads
- ✅ Escalations page: *after fix 1* — tier badges, deadlines, responsible party
- ✅ Reports page: *after fix 1* — file listing with download
- ✅ Admin Overrides: weather source selector + JSON editor, news JSON editor
- ✅ `contractId` persists across page reload
- ✅ Auth middleware ready (set `REQUIRE_API_KEY=true` to enable)
- ✅ Open-Meteo real historical weather data
- ✅ GNews with correct `token` param
- ✅ FM claim → EoT decision with weather validation
- ✅ Hindrance EoT with overlap deduction
- ✅ PDF and markdown reports downloadable

---

## 7. Updated .env Reference

```env
DATABASE_URL=postgresql://postgres:helloPeter%402005@localhost:5432/contractguardv2

KEY1=gsk_xxxxxxxxxxxxxxxxxxxx
KEY2=gsk_xxxxxxxxxxxxxxxxxxxx
KEY3=gsk_xxxxxxxxxxxxxxxxxxxx
KEY4=gsk_xxxxxxxxxxxxxxxxxxxx

WEATHER_SOURCE=open_meteo
# Manual FM test: set WEATHER_SOURCE=manual and fill WEATHER_MANUAL_DATA
# WEATHER_MANUAL_DATA={"total_rainfall_mm": 512, "extreme_rainfall_days": 8, "historical_average_mm": 120, "period_days": 7, "source": "manual_override", "location": "Karnataka, India"}

GNEWS_API_KEY=your_gnews_key_here
# Manual news test: set NEWS_OVERRIDE_FILE to a JSON file path
# NEWS_OVERRIDE_FILE=data/overrides/news_override.json

# To enable API key auth:
# REQUIRE_API_KEY=true
# API_KEY_HEADER=your_secret_key_here
```

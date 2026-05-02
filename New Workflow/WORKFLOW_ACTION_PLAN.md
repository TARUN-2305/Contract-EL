# ContractGuard AI — Complete Migration & Production Upgrade Action Plan

> **Document version:** 1.0  
> **Based on:** Full recursive audit of Contract-EL-main codebase  
> **Scope:** Bug fixes → LangGraph orchestration → React frontend → Free API replacements → Production hardening  
> **Reading time:** ~25 min  

---

## Table of Contents

1. [Project State Assessment](#1-project-state-assessment)
2. [Phase 0 — Immediate Bug Fixes](#2-phase-0--immediate-bug-fixes-day-1)
3. [Phase 1 — API & Tool Replacements](#3-phase-1--api--tool-replacements-days-2-3)
4. [Phase 2 — Database & History Layer](#4-phase-2--database--history-layer-days-4-5)
5. [Phase 3 — LLM Parser Hardening](#5-phase-3--llm-parser-hardening-days-6-7)
6. [Phase 4 — LangGraph Orchestration](#6-phase-4--langgraph-orchestration-days-8-11)
7. [Phase 5 — React Frontend](#7-phase-5--react-frontend-days-12-20)
8. [Phase 6 — Production Hardening](#8-phase-6--production-hardening-days-21-25)
9. [New File Structure](#9-new-file-structure)
10. [New .env Reference](#10-new-env-reference)
11. [Testing Checklist](#11-testing-checklist)
12. [Known Limitations & Honest Caveats](#12-known-limitations--honest-caveats)

---

## 1. Project State Assessment

### What is solid and must not be changed

| Component | File | Assessment |
|---|---|---|
| Compliance engine | `agents/compliance_engine.py` | All 15 checks correct, EPC/ITEM_RATE branching works, keep as-is |
| Groq client | `utils/groq_client.py` | Round-robin rotation, thread-safe, excellent — do not touch |
| Escalation state machine | `agents/escalation_agent.py` | EPC and ITEM_RATE tracks correct, APScheduler wired correctly |
| EoT decision logic | `agents/eot_agent.py` | FM notice validation, overlap calculation correct (one variable name bug only) |
| Risk predictor | `agents/risk_predictor.py` | XGBoost + SHAP works, 25 features wired correctly |
| DB models | `db/models.py` | 5 tables correct, just needs one addition |
| PDF exporter | `agents/pdf_exporter.py` | Works, keep |
| FastAPI endpoints | `api/main.py` | All endpoints functional, need extensions not rewrites |

### What is broken or incomplete

| Issue | File | Severity | Fix effort |
|---|---|---|---|
| `overlap` variable NameError | `agents/eot_agent.py` | **CRITICAL** — crashes on PARTIALLY_APPROVED | 1 line |
| FM notice regex returns None always | `agents/extraction_engine.py` | HIGH — FM validation always uses hardcoded default | 5 lines |
| `machinery_deployment_pct` hardcoded 80.0 | `agents/mpr_parser.py` | MEDIUM — wrong risk feature input | 10 lines |
| BoQ and materials always empty | `agents/mpr_parser.py` | MEDIUM — risk features missing | 30 lines |
| EXTRACTION_PROMPTS not wired to LLM fallback | `agents/parser_agent.py` | HIGH — LLM gets vague prompts | 20 lines |
| Orchestrator decision ignored by API | `api/main.py` | HIGH — orchestrator is decorative | LangGraph phase |
| Weather tool calls paid OWM endpoint | `tools/weather_tool.py` | HIGH — always falls back to random data | 1 file rewrite |
| News tool NewsAPI free tier inadequate | `tools/news_tool.py` | MEDIUM — 100 req/day, no Indian sources | 1 file rewrite |
| No MPR history persistence | `db/models.py` | HIGH — no time-series data for charts | New table |
| No auth on any API endpoint | `api/main.py` | MEDIUM for production | API key middleware |
| Streamlit rerenders everything on each action | `dashboard.py` | HIGH — replace with React | Full phase |

### Architecture gap

The orchestrator (`agents/orchestrator.py`) calls Groq to decide which agents to invoke and in what order. It returns a JSON list of agent names. However, `api/main.py` never reads that list — it hardcodes `compliance → risk → explainer` for every MPR upload regardless. The orchestrator is being called but its output thrown away. LangGraph fixes this by making the routing structural and conditional.

---

## 2. Phase 0 — Immediate Bug Fixes (Day 1)

These three fixes take under an hour combined and should be done before any other work. They affect current testing.

### Fix 1 — `eot_agent.py` NameError crash

**File:** `agents/eot_agent.py`  
**Location:** Inside `process_hindrance_eot`, the PARTIALLY_APPROVED branch  
**Problem:** Variable `overlap` used but never defined — should be `overlap_days`

```python
# FIND THIS LINE (approximately line 180):
rejection_reason=f"Overlap deduction of {overlap} days applied. Net approved: {approved} days."

# REPLACE WITH:
rejection_reason=f"Overlap deduction of {overlap_days} days applied. Net approved: {approved} days."
```

**Test:** Run `python agents/eot_agent.py` — the CLI test at the bottom should print `✅ EoT Decision: APPROVED` without NameError.

---

### Fix 2 — FM notice regex always returning None

**File:** `agents/extraction_engine.py`  
**Location:** `extract_force_majeure()` function  
**Problem:** The alternation `pattern1|pattern2` with two capture groups means `_int()` gets a tuple, not a string. Result: `notice_deadline_days` is always `None`, FM validation falls back to hardcoded 7 days.

```python
# FIND THIS (the single regex with alternation):
"notice_deadline_days": _int(_find(
    r"within\s+(\d+)\s+(?:seven\s+)?\(?seven\)?\s*days\s+of\s+becoming\s+aware|within\s+(\d+)\s+days\s+of\s+becoming",
    text
)),

# REPLACE WITH (two separate searches, take first non-None result):
"notice_deadline_days": (
    _int(_find(r"within\s+(\d+)\s+days\s+of\s+becoming\s+aware", text))
    or _int(_find(r"within\s+seven\s+\(7\)\s+days", text))
    or _int(_find(r"within\s+(\d+)\s+days\s+of\s+(?:the\s+)?occurrence", text))
    or 7  # NITI Aayog Article 19.1 default
),
```

**Test:** Parse the fake contract and check the extracted rule store — `force_majeure.notice_deadline_days` should be `7`, not `null`.

---

### Fix 3 — `machinery_deployment_pct` hardcoded + BoQ empty

**File:** `agents/mpr_parser.py`  
**Location:** In `parse_mpr_docx()` and `parse_mpr()`, the machinery section

```python
# FIND THIS IN BOTH parse_mpr_docx AND parse_mpr:
"machinery_deployment_pct": 80.0,  # default if not in MPR

# REPLACE WITH (add extraction before the record dict):
# Add these extractions in Section 5 (Labour & machinery):
machinery_planned = _safe_int(
    extract_from_table_row(doc.tables, "Planned Machinery", 1)
    or _kv(text, "Planned Machinery Count")
)
machinery_actual = _safe_int(
    extract_from_table_row(doc.tables, "Actual Machinery", 1)
    or _kv(text, "Actual Machinery Deployed")
)
machinery_deployment = (
    round(machinery_actual / machinery_planned * 100, 1)
    if machinery_planned and machinery_planned > 0
    else 80.0  # fallback only if truly missing
)

# Then in the record dict:
"machinery_deployment_pct": machinery_deployment,
```

For the BoQ fix — the section header in the DOCX is "Section 3" not "BoQ Execution":

```python
# In parse_mpr_docx, replace the BoQ table search:
# FIND:
boq_items = []

# REPLACE WITH:
boq_items = []
for table in doc.tables:
    if not table.rows:
        continue
    headers = [c.text.strip().lower() for c in table.rows[0].cells]
    if any(h in headers for h in ['item', 'description', 'boq', 'quantity']):
        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) >= 3 and cells[0] and cells[0][0].isdigit():
                boq_items.append({
                    "item": cells[0],
                    "description": cells[1] if len(cells) > 1 else "",
                    "planned_qty": cells[2] if len(cells) > 2 else "",
                    "actual_qty": cells[3] if len(cells) > 3 else "",
                })
        if boq_items:
            break
```

**Test:** Run Scenario C MPR through the dashboard — machinery deployment should now reflect actual MPR values, not always 80%.

---

## 3. Phase 1 — API & Tool Replacements (Days 2-3)

### 3.1 Weather Tool — Replace with Open-Meteo

**Why Open-Meteo:**
- Completely free, no API key required
- Real historical precipitation data from global weather models
- REST endpoint: `https://archive-api.open-meteo.com/v1/archive`
- Returns daily `precipitation_sum` in mm for any lat/lon, any date range
- No rate limits for reasonable usage

**New file: `tools/weather_tool.py`** — complete replacement:

```python
"""
Weather Tool — tools/weather_tool.py
Uses Open-Meteo Archive API (free, no key) for real historical rainfall data.
Supports manual override for testing and CI environments.
"""
import os
import json
import requests
from datetime import date
from dataclasses import dataclass
from typing import Optional, Dict, Any

from agents.compliance_engine import _parse_date


# ── Location coordinate map for Indian NH corridors ──────────────────────
# Add more as needed. Keyed to partial location name match (lowercase).
LOCATION_COORDS = {
    "karnataka":      (13.08, 77.59),   # Bengaluru centroid
    "bengaluru":      (12.97, 77.59),
    "chennai":        (13.08, 80.27),
    "mumbai":         (19.07, 72.87),
    "delhi":          (28.61, 77.20),
    "hyderabad":      (17.38, 78.48),
    "pune":           (18.52, 73.86),
    "kolkata":        (22.57, 88.36),
    "ahmedabad":      (23.02, 72.57),
    "rajasthan":      (27.02, 74.21),
    "gujarat":        (22.26, 71.19),
    "maharashtra":    (19.75, 75.71),
    "andhra pradesh": (15.91, 79.74),
    "tamil nadu":     (11.12, 78.66),
    "kerala":         (10.85, 76.27),
    "odisha":         (20.94, 85.09),
    "bihar":          (25.09, 85.31),
    "uttar pradesh":  (26.84, 80.94),
    "default":        (20.59, 78.96),   # Geographic centre of India
}


@dataclass
class WeatherOverride:
    """
    Inject synthetic or manually-measured weather data instead of calling API.
    Use in .env: WEATHER_SOURCE=manual and WEATHER_MANUAL_DATA={"total_mm":512,...}
    Or call WeatherTool.set_override(...) directly in test code.
    """
    total_rainfall_mm: float
    extreme_rainfall_days: int
    historical_average_mm: float
    source: str = "manual_override"


_GLOBAL_OVERRIDE: Optional[WeatherOverride] = None


class WeatherTool:
    """
    Fetch historical rainfall data to validate Force Majeure weather claims.

    Priority order:
      1. Global override (set via set_override() or WEATHER_MANUAL_DATA env var)
      2. Open-Meteo Archive API (free, no key)
      3. Synthetic fallback (if API fails)
    """

    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
    # Historical baseline: approximate average monthly rainfall per region (mm)
    # Source: IMD normal rainfall statistics
    BASELINE_MM_PER_DAY = 4.5  # rough all-India average for non-monsoon

    def __init__(self):
        self.source = os.environ.get("WEATHER_SOURCE", "open_meteo").lower()
        manual_data = os.environ.get("WEATHER_MANUAL_DATA")
        if manual_data:
            try:
                d = json.loads(manual_data)
                self.env_override = WeatherOverride(
                    total_rainfall_mm=d.get("total_mm", 0),
                    extreme_rainfall_days=d.get("extreme_days", 0),
                    historical_average_mm=d.get("historical_avg_mm", 100),
                    source=d.get("source", "env_override"),
                )
            except Exception:
                self.env_override = None
        else:
            self.env_override = None

    @classmethod
    def set_override(cls, override: WeatherOverride):
        """Set a global override for all WeatherTool instances. Use in tests."""
        global _GLOBAL_OVERRIDE
        _GLOBAL_OVERRIDE = override

    @classmethod
    def clear_override(cls):
        global _GLOBAL_OVERRIDE
        _GLOBAL_OVERRIDE = None

    def _get_coords(self, location: str) -> tuple:
        loc = location.lower()
        for key, coords in LOCATION_COORDS.items():
            if key in loc:
                return coords
        return LOCATION_COORDS["default"]

    def get_rainfall_data(self, location: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Fetch rainfall for a location and date range."""
        # Priority 1: global override
        if _GLOBAL_OVERRIDE:
            return {
                "location": location,
                "start_date": start_date,
                "end_date": end_date,
                "total_rainfall_mm": _GLOBAL_OVERRIDE.total_rainfall_mm,
                "extreme_rainfall_days": _GLOBAL_OVERRIDE.extreme_rainfall_days,
                "historical_average_mm": _GLOBAL_OVERRIDE.historical_average_mm,
                "source": _GLOBAL_OVERRIDE.source,
            }

        # Priority 2: env override
        if self.env_override:
            return {
                "location": location,
                "total_rainfall_mm": self.env_override.total_rainfall_mm,
                "extreme_rainfall_days": self.env_override.extreme_rainfall_days,
                "historical_average_mm": self.env_override.historical_average_mm,
                "source": self.env_override.source,
            }

        start = _parse_date(start_date)
        end = _parse_date(end_date)
        if not start or not end:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}

        days = max(1, (end - start).days)

        # Priority 3: Open-Meteo API (free, no key)
        if self.source == "open_meteo":
            try:
                lat, lon = self._get_coords(location)
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": str(start),
                    "end_date": str(end),
                    "daily": "precipitation_sum",
                    "timezone": "Asia/Kolkata",
                }
                resp = requests.get(self.BASE_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                daily_precip = data.get("daily", {}).get("precipitation_sum", [])
                # Filter out None values (missing data days)
                valid = [v for v in daily_precip if v is not None]
                total_mm = round(sum(valid), 2)
                # IMD definition: heavy rain = >64.5mm/day, extreme = >204.4mm/day
                extreme_days = sum(1 for v in valid if v > 64.5)
                historical_avg = round(self.BASELINE_MM_PER_DAY * days, 2)

                return {
                    "location": location,
                    "coordinates": {"lat": lat, "lon": lon},
                    "period_days": days,
                    "total_rainfall_mm": total_mm,
                    "extreme_rainfall_days": extreme_days,
                    "historical_average_mm": historical_avg,
                    "daily_data": list(zip(
                        data.get("daily", {}).get("time", []),
                        daily_precip
                    ))[:10],  # first 10 days for audit trail
                    "source": "open_meteo_archive",
                }
            except requests.Timeout:
                print("[WeatherTool] Open-Meteo timed out — using synthetic fallback")
            except Exception as e:
                print(f"[WeatherTool] Open-Meteo error: {e} — using synthetic fallback")

        # Priority 4: synthetic fallback
        return self._generate_synthetic_weather(location, days)

    def _generate_synthetic_weather(self, location: str, days: int) -> Dict[str, Any]:
        """Deterministic synthetic data (seeded by location name for consistency)."""
        import hashlib
        seed = int(hashlib.md5(location.encode()).hexdigest()[:8], 16)
        import random
        rng = random.Random(seed)
        total = rng.uniform(20, 80) * (days / 30)
        extreme = rng.randint(0, max(0, days // 10))
        return {
            "location": location,
            "period_days": days,
            "total_rainfall_mm": round(total, 2),
            "extreme_rainfall_days": extreme,
            "historical_average_mm": round(self.BASELINE_MM_PER_DAY * days, 2),
            "source": "synthetic_fallback",
        }

    def verify_force_majeure(self, claim: dict) -> Dict[str, Any]:
        """Validate a Force Majeure weather claim."""
        location = claim.get("location", "Karnataka, India")
        start = claim.get("event_date") or claim.get("date_of_occurrence")
        end = claim.get("date_ended") or str(date.today())

        if not start:
            return {"valid": False, "reason": "No event date provided in FM claim."}

        weather_data = self.get_rainfall_data(location, start, end)
        if "error" in weather_data:
            return {"valid": None, "reason": weather_data["error"], "weather_data": {}}

        total_mm = weather_data.get("total_rainfall_mm", 0)
        hist_avg = weather_data.get("historical_average_mm", 1)
        extreme_days = weather_data.get("extreme_rainfall_days", 0)

        # Anomaly ratio: actual vs historical average
        ratio = total_mm / max(1, hist_avg)
        anomaly_score = min(1.0, max(0.0, (ratio - 1) / 2))

        # Valid if: anomaly score >= 0.75 OR at least 2 extreme rain days (>64.5mm)
        # This matches IMD "heavy rainfall" classification
        is_valid = anomaly_score >= 0.75 or extreme_days >= 2

        return {
            "valid": is_valid,
            "anomaly_score": round(anomaly_score, 4),
            "weather_data": weather_data,
            "reason": (
                f"Severe weather verified: {total_mm}mm over period, {extreme_days} extreme days."
                if is_valid else
                f"Weather data does not support FM claim: {total_mm}mm recorded, "
                f"{extreme_days} extreme days (threshold: 2 days or anomaly ≥ 0.75)."
            ),
        }
```

**Add to `.env`:**
```
WEATHER_SOURCE=open_meteo
# To manually override for testing:
# WEATHER_SOURCE=manual
# WEATHER_MANUAL_DATA={"total_mm": 512, "extreme_days": 8, "historical_avg_mm": 120, "source": "site_gauge_reading"}
```

---

### 3.2 News Tool — Replace with GNews + override

**Why GNews over NewsAPI:**
- Free tier: 100 req/day (same as NewsAPI)
- Better coverage of Indian English publications
- Supports `lang=en` and `country=in` parameters
- No date restriction on free tier unlike NewsAPI's 1-month limit
- API key: sign up at https://gnews.io

**New file: `tools/news_tool.py`** — complete replacement:

```python
"""
News Tool — tools/news_tool.py
Uses GNews API for contractor risk signals.
Supports manual override via JSON file (NEWS_OVERRIDE_FILE env var).
"""
import os
import json
import requests
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path


RISK_KEYWORDS = [
    "insolvency", "NCLT", "bankrupt", "fraud", "default",
    "CBI", "ED raid", "blacklist", "debarred", "liquidation",
    "delayed salary", "strike", "labour dispute", "arbitration award",
    "project abandoned", "cost overrun", "penalty",
]

# For GNews: map risk keywords to search-friendly terms
GNEWS_QUERY_TERMS = [
    "insolvency OR NCLT OR bankrupt",
    "fraud OR CBI OR ED",
    "blacklist OR debarred OR default",
    "strike OR \"delayed salary\"",
]


class NewsTool:
    """
    Fetch contractor news and flag adverse signals.

    Priority order:
      1. JSON override file (NEWS_OVERRIDE_FILE env var or set_override_file())
      2. GNews API (GNEWS_API_KEY env var)
      3. Synthetic fallback (deterministic, seeded by entity name)
    """

    GNEWS_URL = "https://gnews.io/api/v4/search"
    _override_file: Optional[str] = None

    def __init__(self):
        self.api_key = os.environ.get("GNEWS_API_KEY") or os.environ.get("NEWSAPI_KEY")
        self.override_file = self.__class__._override_file or os.environ.get("NEWS_OVERRIDE_FILE")

    @classmethod
    def set_override_file(cls, path: str):
        """Set a JSON file path to use as override for all instances. Use in tests."""
        cls._override_file = path

    @classmethod
    def clear_override(cls):
        cls._override_file = None

    def get_entity_news(self, entity_name: str, days_back: int = 30) -> Dict[str, Any]:
        # Priority 1: file override
        if self.override_file and Path(self.override_file).exists():
            try:
                with open(self.override_file, encoding="utf-8") as f:
                    data = json.load(f)
                data["source"] = f"file_override:{self.override_file}"
                return data
            except Exception as e:
                print(f"[NewsTool] Override file error: {e}")

        # Priority 2: GNews API
        if self.api_key:
            try:
                results = []
                # Search with risk keyword combinations
                for query_terms in GNEWS_QUERY_TERMS[:2]:  # Limit to 2 calls to preserve daily quota
                    query = f'"{entity_name}" ({query_terms})'
                    params = {
                        "q": query,
                        "lang": "en",
                        "country": "in",
                        "max": 10,
                        "token": self.api_key,
                    }
                    resp = requests.get(self.GNEWS_URL, params=params, timeout=8)
                    if resp.status_code == 200:
                        articles = resp.json().get("articles", [])
                        results.extend(articles)
                    elif resp.status_code == 429:
                        print("[NewsTool] GNews rate limit hit")
                        break

                return self._analyze_articles(results, entity_name)

            except requests.Timeout:
                print("[NewsTool] GNews timed out — using synthetic fallback")
            except Exception as e:
                print(f"[NewsTool] GNews error: {e} — using synthetic fallback")

        # Priority 3: synthetic fallback (deterministic)
        return self._generate_synthetic_news(entity_name)

    def _analyze_articles(self, articles: List[dict], entity_name: str) -> Dict[str, Any]:
        risk_signals = []
        for article in articles:
            title = article.get("title", "")
            desc = article.get("description", "")
            text = (title + " " + desc).lower()
            found = [kw for kw in RISK_KEYWORDS if kw.lower() in text]
            if found:
                risk_signals.append({
                    "title": title,
                    "source": article.get("source", {}).get("name", ""),
                    "published_at": article.get("publishedAt", ""),
                    "url": article.get("url", ""),
                    "matched_keywords": found,
                })
        score = min(1.0, len(risk_signals) * 0.2)
        return {
            "entity_name": entity_name,
            "total_articles_analyzed": len(articles),
            "adverse_signals_found": len(risk_signals),
            "risk_score": round(score, 2),
            "signals": risk_signals,
            "source": "gnews",
            "scan_date": str(date.today()),
        }

    def _generate_synthetic_news(self, entity_name: str) -> Dict[str, Any]:
        """Deterministic synthetic news (seeded — same entity always gets same result)."""
        import hashlib
        import random
        seed = int(hashlib.md5(entity_name.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        is_risky = rng.random() < 0.15  # 15% chance of adverse signal
        if not is_risky:
            return {
                "entity_name": entity_name,
                "total_articles_analyzed": rng.randint(8, 25),
                "adverse_signals_found": 0,
                "risk_score": 0.0,
                "signals": [],
                "source": "synthetic_fallback",
                "scan_date": str(date.today()),
            }
        signals = [{
            "title": f"NCLT admits insolvency plea against {entity_name}",
            "source": "Economic Times",
            "published_at": str(date.today() - timedelta(days=rng.randint(2, 15))),
            "url": "https://economictimes.indiatimes.com",
            "matched_keywords": ["insolvency", "NCLT"],
        }]
        return {
            "entity_name": entity_name,
            "total_articles_analyzed": 42,
            "adverse_signals_found": 1,
            "risk_score": 0.4,
            "signals": signals,
            "source": "synthetic_fallback",
            "scan_date": str(date.today()),
        }
```

**Override file format** (`data/overrides/news_xyz_constructions.json`):
```json
{
  "entity_name": "XYZ Constructions Pvt. Ltd.",
  "total_articles_analyzed": 42,
  "adverse_signals_found": 2,
  "risk_score": 0.8,
  "signals": [
    {
      "title": "NCLT admits insolvency plea against XYZ Constructions",
      "source": "Economic Times",
      "published_at": "2026-04-15",
      "url": "https://example.com/news/1",
      "matched_keywords": ["insolvency", "NCLT"]
    }
  ],
  "source": "manual_test_override"
}
```

**Add to `.env`:**
```
GNEWS_API_KEY=your_gnews_key_here
# To manually override:
# NEWS_OVERRIDE_FILE=data/overrides/news_xyz_constructions.json
```

---

## 4. Phase 2 — Database & History Layer (Days 4-5)

### 4.1 Add MPR history table

Without persisting each MPR upload's results, there is no time-series data for the S-curve chart, risk trend chart, or cross-period comparisons. This is the most important structural addition.

**Add to `db/models.py`:**

```python
class MPRRecord(Base):
    """Persists every MPR upload and its full analysis results."""
    __tablename__ = "mpr_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String, nullable=False, index=True)
    reporting_period = Column(String, nullable=False)          # "2026-03"
    reporting_period_end = Column(String, nullable=True)       # "2026-03-31"
    day_number = Column(Integer, nullable=True)
    actual_physical_pct = Column(Float, nullable=True)
    planned_physical_pct = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_label = Column(String, nullable=True)                 # LOW/MEDIUM/HIGH/CRITICAL
    total_ld_accrued_inr = Column(Float, nullable=True)
    critical_event_count = Column(Integer, nullable=True)
    high_event_count = Column(Integer, nullable=True)
    total_event_count = Column(Integer, nullable=True)
    exec_data_json = Column(JSON, nullable=True)               # full parsed MPR
    compliance_json = Column(JSON, nullable=True)              # full compliance report
    risk_json = Column(JSON, nullable=True)                    # full risk prediction
    audience = Column(String, nullable=True)
    created_at = Column(String, default=lambda: str(date.today()))
    uploaded_filename = Column(String, nullable=True)
```

**Also add to `Project` model** — fields for last known state:

```python
# Add these columns to the existing Project model:
last_actual_pct = Column(Float, nullable=True)
last_reporting_period = Column(String, nullable=True)
last_risk_score = Column(Float, nullable=True)
last_risk_label = Column(String, nullable=True)
last_ld_accrued_inr = Column(Float, nullable=True)
```

**Update `scripts/init_db.py`** to call `Base.metadata.create_all(engine)` which will auto-create the new table. For existing databases, add an Alembic migration.

### 4.2 Set up Alembic migrations

```bash
pip install alembic
alembic init migrations
```

Edit `migrations/env.py` to import your models and set the correct database URL. Then:

```bash
alembic revision --autogenerate -m "add mpr_records table and project last state columns"
alembic upgrade head
```

From this point forward, all schema changes go through Alembic.

### 4.3 New API endpoints for history

Add to `api/main.py`:

```python
@app.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    """List all projects with their latest state."""
    projects = db.query(models.Project).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "contract_type": p.contract_type,
            "day_number": p.day_number,
            "scp_days": p.scp_days,
            "contractor_name": p.contractor_name,
            "last_actual_pct": p.last_actual_pct,
            "last_risk_score": p.last_risk_score,
            "last_risk_label": p.last_risk_label,
            "last_ld_accrued_inr": p.last_ld_accrued_inr,
            "last_reporting_period": p.last_reporting_period,
        }
        for p in projects
    ]


@app.get("/projects/{contract_id}/mpr-history")
def get_mpr_history(contract_id: str, db: Session = Depends(get_db)):
    """Return all MPR periods for S-curve and risk trend charts."""
    cid = contract_id.replace("/", "_").replace("\\", "_")
    records = (
        db.query(models.MPRRecord)
        .filter(models.MPRRecord.contract_id == cid)
        .order_by(models.MPRRecord.day_number)
        .all()
    )
    return [
        {
            "period": r.reporting_period,
            "day_number": r.day_number,
            "actual_pct": r.actual_physical_pct,
            "planned_pct": r.planned_physical_pct,
            "risk_score": r.risk_score,
            "risk_label": r.risk_label,
            "ld_accrued_inr": r.total_ld_accrued_inr,
            "critical_events": r.critical_event_count,
            "high_events": r.high_event_count,
        }
        for r in records
    ]


@app.get("/projects/{contract_id}/rule-store")
def get_rule_store(contract_id: str):
    """Return the parsed rule store for a contract."""
    cid = contract_id.replace("/", "_").replace("\\", "_")
    path = f"data/rule_store/rule_store_{cid}.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Rule store not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.post("/weather-override")
def set_weather_override(data: Dict[str, Any]):
    """
    Manually set weather data for FM validation testing.
    Body: {"total_mm": 512, "extreme_days": 8, "historical_avg_mm": 120}
    """
    from tools.weather_tool import WeatherTool, WeatherOverride
    WeatherTool.set_override(WeatherOverride(
        total_rainfall_mm=data.get("total_mm", 0),
        extreme_rainfall_days=data.get("extreme_days", 0),
        historical_average_mm=data.get("historical_avg_mm", 100),
        source="api_override",
    ))
    return {"message": "Weather override set", "data": data}


@app.delete("/weather-override")
def clear_weather_override():
    from tools.weather_tool import WeatherTool
    WeatherTool.clear_override()
    return {"message": "Weather override cleared"}


@app.post("/news-override")
def set_news_override(file_path: str = Form(...)):
    """Point news tool at a local JSON override file."""
    from tools.news_tool import NewsTool
    NewsTool.set_override_file(file_path)
    return {"message": f"News override set to {file_path}"}
```

**Also update `/upload-mpr`** to persist the MPR record after analysis:

```python
# Add this block at the end of the upload_mpr endpoint, before returning:
try:
    mpr_rec = models.MPRRecord(
        contract_id=contract_id,
        reporting_period=exec_data.get("reporting_period", ""),
        reporting_period_end=exec_data.get("reporting_period_end"),
        day_number=exec_data.get("day_number"),
        actual_physical_pct=exec_data.get("actual_physical_pct"),
        planned_physical_pct=exec_data.get("planned_physical_pct"),
        risk_score=prediction.risk_score,
        risk_label=prediction.risk_label,
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
    db_session = SessionLocal()
    db_session.add(mpr_rec)
    # Update project last state
    proj = db_session.query(models.Project).filter(models.Project.id == contract_id).first()
    if proj:
        proj.last_actual_pct = exec_data.get("actual_physical_pct")
        proj.last_reporting_period = exec_data.get("reporting_period")
        proj.last_risk_score = prediction.risk_score
        proj.last_risk_label = prediction.risk_label
        proj.last_ld_accrued_inr = compliance_result.get("total_ld_accrued_inr", 0)
    db_session.commit()
    db_session.close()
except Exception as e:
    print(f"[API] MPR history persist failed: {e}")  # non-fatal
```

---

## 5. Phase 3 — LLM Parser Hardening (Days 6-7)

### 5.1 Wire EXTRACTION_PROMPTS to LLM fallback

The rich, per-field JSON schema prompts in `EXTRACTION_PROMPTS` are already written but the LLM fallback in `parse_contract()` sends a generic `"extract {target}"` prompt instead of using them. This is a 20-line change with major impact on extraction quality.

**In `agents/parser_agent.py`, find the LLM fallback block (Stage 4b) and replace:**

```python
# FIND the generic prompt construction:
system_prompt = "You are a legal contract parsing assistant..."
user_prompt = f"Contract Text:\n{context_text}\n\nMissing Field to extract: {target}..."

# REPLACE with schema-specific prompts:
from agents.parser_agent import EXTRACTION_PROMPTS, DEFAULT_EXTRACTION_PROMPT

# Use the rich schema prompt if available, else fall back to default
if target in EXTRACTION_PROMPTS:
    user_prompt = EXTRACTION_PROMPTS[target].format(context=context_text)
    system_prompt = (
        "You are a legal contract extraction engine for Indian public infrastructure contracts "
        "(NITI Aayog EPC and CPWD Item Rate types). "
        "Return ONLY valid JSON matching the exact schema requested. "
        "Never hallucinate values. Use null for any field not found in the text."
    )
else:
    user_prompt = DEFAULT_EXTRACTION_PROMPT.format(
        target=target,
        context=context_text
    )
    system_prompt = (
        "You are a legal contract parsing assistant. "
        "Return ONLY valid JSON. No markdown, no preamble."
    )
```

### 5.2 Add post-extraction validation

After the LLM returns a value, validate it against `VALIDATION_RULES` before accepting:

```python
# After parsing LLM response:
if val is not None:
    warnings = validate_extracted(target, val)
    if warnings:
        print(f"[ParserAgent] LLM result for {target} failed validation: {warnings}")
        # Keep the value but log it — don't discard, the regex also failed
        audit_log[target] = {
            "method": "groq_llm_fallback",
            "warnings": warnings,
            "note": "Validation failed but keeping LLM result — manual review recommended",
        }
    else:
        audit_log[target] = {"method": "groq_llm_fallback", "warnings": []}
    extracted[target] = val
    del unresolved[target]
```

### 5.3 Add a `config.py` for all settings

Create `config.py` in the project root:

```python
"""
config.py — centralised settings via Pydantic Settings.
All values readable from .env file or environment variables.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/contractguard"

    # Groq keys (loaded by groq_client.py via KEY* pattern — these are for documentation)
    # KEY1, KEY2, KEY3, KEY4: set directly in .env

    # Weather
    weather_source: str = "open_meteo"          # "open_meteo" | "manual" | "synthetic"
    weather_manual_data: Optional[str] = None    # JSON string override

    # News
    gnews_api_key: Optional[str] = None
    news_override_file: Optional[str] = None     # path to JSON override file

    # Parser
    llm_fallback_enabled: bool = True
    llm_model_extraction: str = "llama-3.3-70b-versatile"
    llm_model_narration: str = "llama-3.1-8b-instant"

    # API
    api_key_header: Optional[str] = None         # if set, all endpoints require X-API-Key header
    cors_origins: str = "http://localhost:5173"   # React dev server

    # Frontend
    react_build_dir: str = "frontend/dist"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
```

Add `pydantic-settings` to `requirements.txt`.

---

## 6. Phase 4 — LangGraph Orchestration (Days 8-11)

### 6.1 Install LangGraph

```bash
pip install langgraph langchain-core
```

Add both to `requirements.txt`.

### 6.2 Define the state schema

Create `agents/graph_state.py`:

```python
"""
ContractGuard AI — LangGraph state definition.
"""
from typing import TypedDict, Optional, Any


class ContractGuardState(TypedDict):
    # Inputs
    trigger_type: str                    # MPR_UPLOADED | FM_CLAIM_SUBMITTED | etc.
    contract_id: str
    audience: str

    # Loaded data
    rule_store: Optional[dict]           # Loaded from disk / DB
    exec_data: Optional[dict]            # Parsed MPR / FM claim / hindrance

    # Agent outputs — populated as graph runs
    compliance_report: Optional[dict]
    risk_prediction: Optional[dict]
    eot_decision: Optional[dict]
    escalation_record: Optional[dict]
    explainer_outputs: Optional[dict]

    # Control flow
    has_critical_events: bool
    has_fm_claim: bool
    has_hindrance_claim: bool
    errors: list[str]
```

### 6.3 Define agent node functions

Create `agents/langgraph_nodes.py`:

```python
"""
LangGraph node functions — each wraps an existing agent.
Nodes read from state, call agents, write results back to state.
"""
from agents.compliance_agent import ComplianceAgent
from agents.risk_predictor import RiskPredictor
from agents.explainer_agent import ExplainerAgent
from agents.escalation_agent import EscalationAgent
from agents.eot_agent import EoTAgent
from agents.graph_state import ContractGuardState
import dataclasses

_compliance = ComplianceAgent()
_risk = RiskPredictor()
_explainer = ExplainerAgent()
_escalation = EscalationAgent()
_eot = EoTAgent()


def node_compliance(state: ContractGuardState) -> ContractGuardState:
    print("[Graph] node_compliance running")
    try:
        report = _compliance.run(state["exec_data"])
        critical = report.get("critical_count", 0) > 0
        return {
            **state,
            "compliance_report": report,
            "has_critical_events": critical,
        }
    except Exception as e:
        return {**state, "errors": state["errors"] + [f"compliance: {e}"]}


def node_risk(state: ContractGuardState) -> ContractGuardState:
    print("[Graph] node_risk running")
    try:
        pred = _risk.predict(state["exec_data"], state["rule_store"])
        return {**state, "risk_prediction": dataclasses.asdict(pred)}
    except Exception as e:
        return {**state, "errors": state["errors"] + [f"risk: {e}"]}


def node_explainer(state: ContractGuardState) -> ContractGuardState:
    print("[Graph] node_explainer running")
    try:
        outputs = _explainer.explain(
            compliance_report=state["compliance_report"],
            risk_prediction=state["risk_prediction"],
            rule_store=state["rule_store"],
            exec_data=state["exec_data"],
            audience=state["audience"],
        )
        return {**state, "explainer_outputs": outputs}
    except Exception as e:
        return {**state, "errors": state["errors"] + [f"explainer: {e}"]}


def node_escalation(state: ContractGuardState) -> ContractGuardState:
    print("[Graph] node_escalation running")
    try:
        # Find the most severe compliance event and escalate it
        events = state["compliance_report"].get("events", [])
        critical_events = [e for e in events if e.get("severity") == "CRITICAL"]
        if not critical_events:
            return state
        top = critical_events[0]
        record = _escalation.advance_escalation(
            event_id=top.get("check_id"),
            project_id=state["contract_id"],
            contract_type=state["rule_store"].get("contract_type", "EPC"),
            current_tier="NONE",
            violation_summary=top.get("description", ""),
            project_name=state["rule_store"].get("project_name", ""),
            contractor_name=state["rule_store"].get("contractor_name", ""),
            generate_notice=True,
        )
        _escalation.save_record(record)
        return {**state, "escalation_record": dataclasses.asdict(record)}
    except Exception as e:
        return {**state, "errors": state["errors"] + [f"escalation: {e}"]}


def node_eot_fm(state: ContractGuardState) -> ContractGuardState:
    print("[Graph] node_eot_fm running")
    try:
        fm_claims = state["exec_data"].get("force_majeure_events", [])
        if not fm_claims:
            return state
        decision = _eot.process_fm_eot(
            project_id=state["contract_id"],
            fm_claim=fm_claims[0],
            rule_store=state["rule_store"],
        )
        _eot.save_decision(decision)
        return {**state, "eot_decision": dataclasses.asdict(decision)}
    except Exception as e:
        return {**state, "errors": state["errors"] + [f"eot_fm: {e}"]}


def node_eot_hindrance(state: ContractGuardState) -> ContractGuardState:
    print("[Graph] node_eot_hindrance running")
    try:
        hindrances = state["exec_data"].get("hindrances", [])
        if not hindrances:
            return state
        h = hindrances[0]
        decision = _eot.process_hindrance_eot(
            project_id=state["contract_id"],
            hindrance_id=h.get("hindrance_id", "H001"),
            hindrances=hindrances,
            rule_store=state["rule_store"],
        )
        _eot.save_decision(decision)
        return {**state, "eot_decision": dataclasses.asdict(decision)}
    except Exception as e:
        return {**state, "errors": state["errors"] + [f"eot_hindrance: {e}"]}


# ── Routing functions ───────────────────────────────────────────────────

def route_after_compliance(state: ContractGuardState) -> str:
    """Route to escalation if CRITICAL events exist, else go straight to risk."""
    if state.get("has_critical_events"):
        return "escalation"
    return "risk"


def route_after_eot(state: ContractGuardState) -> str:
    """After EoT, always run compliance then risk."""
    return "compliance"
```

### 6.4 Build the graph

Create `agents/langgraph_graph.py`:

```python
"""
ContractGuard AI — LangGraph StateGraph definition.
Replace the fake orchestrator with real conditional routing.
"""
from langgraph.graph import StateGraph, END
from agents.graph_state import ContractGuardState
from agents.langgraph_nodes import (
    node_compliance, node_risk, node_explainer,
    node_escalation, node_eot_fm, node_eot_hindrance,
    route_after_compliance, route_after_eot,
)


def build_graph() -> StateGraph:
    graph = StateGraph(ContractGuardState)

    # Add all nodes
    graph.add_node("compliance", node_compliance)
    graph.add_node("risk", node_risk)
    graph.add_node("explainer", node_explainer)
    graph.add_node("escalation", node_escalation)
    graph.add_node("eot_fm", node_eot_fm)
    graph.add_node("eot_hindrance", node_eot_hindrance)

    # ── Routing per trigger type ────────────────────────────────────────
    # MPR_UPLOADED:           compliance → (escalation if critical) → risk → explainer
    # FM_CLAIM_SUBMITTED:     eot_fm → compliance → risk → explainer
    # HINDRANCE_LOGGED:       eot_hindrance → compliance → risk → explainer
    # MILESTONE_DATE_REACHED: compliance → escalation → risk → explainer
    # CURE_PERIOD_EXPIRED:    escalation → explainer (no new compliance run)
    # LD_CAP_WARNING:         escalation → explainer

    # Compliance routes conditionally to escalation or risk
    graph.add_conditional_edges(
        "compliance",
        route_after_compliance,
        {"escalation": "escalation", "risk": "risk"},
    )

    # Escalation always goes to risk
    graph.add_edge("escalation", "risk")

    # Risk always goes to explainer
    graph.add_edge("risk", "explainer")

    # Explainer is terminal
    graph.add_edge("explainer", END)

    # EoT nodes route to compliance after processing
    graph.add_edge("eot_fm", "compliance")
    graph.add_edge("eot_hindrance", "compliance")

    return graph


def get_entry_node(trigger_type: str) -> str:
    """Determine which node to enter based on trigger type."""
    routes = {
        "MPR_UPLOADED":             "compliance",
        "FM_CLAIM_SUBMITTED":       "eot_fm",
        "HINDRANCE_LOGGED":         "eot_hindrance",
        "MILESTONE_DATE_REACHED":   "compliance",
        "CURE_PERIOD_EXPIRED":      "escalation",
        "LD_CAP_WARNING":           "escalation",
        "VARIATION_CLAIM_FILED":    "compliance",
    }
    return routes.get(trigger_type, "compliance")


# Compile the graph once at module load
_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_graph()
        graph.set_entry_point("compliance")  # default entry; overridden per run
        _compiled_graph = graph.compile()
    return _compiled_graph


def run_pipeline(
    trigger_type: str,
    contract_id: str,
    rule_store: dict,
    exec_data: dict,
    audience: str = "Project Manager",
) -> ContractGuardState:
    """
    Run the full LangGraph pipeline for a given trigger.
    Returns the final state with all agent outputs populated.
    """
    initial_state: ContractGuardState = {
        "trigger_type": trigger_type,
        "contract_id": contract_id,
        "audience": audience,
        "rule_store": rule_store,
        "exec_data": exec_data,
        "compliance_report": None,
        "risk_prediction": None,
        "eot_decision": None,
        "escalation_record": None,
        "explainer_outputs": None,
        "has_critical_events": False,
        "has_fm_claim": bool(exec_data.get("force_majeure_events")),
        "has_hindrance_claim": bool(exec_data.get("hindrances")),
        "errors": [],
    }

    # Build a graph with the correct entry point for this trigger
    graph = build_graph()
    entry = get_entry_node(trigger_type)
    graph.set_entry_point(entry)
    compiled = graph.compile()

    final_state = compiled.invoke(initial_state)
    if final_state.get("errors"):
        print(f"[LangGraph] Pipeline completed with errors: {final_state['errors']}")
    return final_state
```

### 6.5 Wire LangGraph into `api/main.py`

Replace the manual pipeline sequence in `/upload-mpr` with `run_pipeline`:

```python
# In upload_mpr endpoint, REPLACE this block:
# compliance_result = compliance_agent.run(exec_data)
# prediction = risk_predictor.predict(exec_data, rule_store)
# outputs = explainer_agent.explain(...)

# WITH:
from agents.langgraph_graph import run_pipeline
final_state = run_pipeline(
    trigger_type="MPR_UPLOADED",
    contract_id=contract_id,
    rule_store=rule_store,
    exec_data=exec_data,
    audience=audience,
)
compliance_result = final_state["compliance_report"]
risk_dict = final_state["risk_prediction"]
outputs = final_state["explainer_outputs"]
prediction_score = risk_dict.get("risk_score")
prediction_label = risk_dict.get("risk_label")
prediction_ttd = risk_dict.get("time_to_default_estimate_days")
prediction_factors = risk_dict.get("top_risk_factors", [])
```

---

## 7. Phase 5 — React Frontend (Days 12-20)

### 7.1 Project setup

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install react-router-dom @tanstack/react-query recharts axios
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

Add to `tailwind.config.js`:
```js
content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"]
```

### 7.2 Directory structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.js          # axios instance pointing to localhost:8000
│   │   ├── projects.js        # GET /projects, GET /projects/:id/mpr-history
│   │   ├── upload.js          # POST /upload-contract, POST /upload-mpr
│   │   └── analysis.js        # GET /projects/:id/rule-store
│   ├── components/
│   │   ├── SCurveChart.jsx     # Recharts LineChart — planned vs actual
│   │   ├── RiskGauge.jsx       # Circular risk score indicator
│   │   ├── RiskTrendChart.jsx  # Risk score over MPR periods
│   │   ├── ComplianceTable.jsx # Sorted events table with severity badges
│   │   ├── SHAPBarChart.jsx    # Top 5 risk factors horizontal bar chart
│   │   ├── LDProgressBar.jsx   # LD cap utilisation bar
│   │   ├── PersonaSelector.jsx # Dropdown — changes which panels show
│   │   ├── KPICard.jsx         # Reusable metric card
│   │   ├── UploadDropzone.jsx  # Drag-drop file upload with progress
│   │   └── ProjectSidebar.jsx  # Left nav with project list
│   ├── pages/
│   │   ├── Dashboard.jsx       # Main project view — all panels
│   │   ├── Projects.jsx        # All-projects overview table
│   │   ├── Upload.jsx          # Contract + MPR upload forms
│   │   ├── Reports.jsx         # PDF report links and download
│   │   └── Escalations.jsx     # Escalation state view
│   ├── hooks/
│   │   ├── useProject.js       # useQuery wrapper for project data
│   │   ├── useMPRHistory.js    # useQuery for time-series data
│   │   └── useUpload.js        # useMutation for file uploads
│   ├── store/
│   │   └── personaStore.js     # Zustand store for selected persona
│   ├── App.jsx
│   └── main.jsx
```

### 7.3 Key component specifications

**`SCurveChart.jsx`** — renders planned vs actual progress over time:
```jsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

export function SCurveChart({ history }) {
  const data = history.map(r => ({
    day: r.day_number,
    actual: r.actual_pct,
    planned: r.planned_pct,
  }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <XAxis dataKey="day" label={{ value: 'Day', position: 'insideBottom' }} />
        <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} />
        <Tooltip formatter={(v) => `${v.toFixed(1)}%`} />
        <Line dataKey="planned" stroke="#3B8BD4" strokeDasharray="4 4" dot={false} name="Planned" />
        <Line dataKey="actual" stroke="#E24B4A" strokeWidth={2} dot={{ r: 3 }} name="Actual" />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

**`ComplianceTable.jsx`** — sortable events table:
```jsx
const SEVERITY_COLORS = {
  CRITICAL: 'bg-red-100 text-red-800',
  HIGH:     'bg-amber-100 text-amber-800',
  MEDIUM:   'bg-blue-100 text-blue-800',
  LOW:      'bg-green-100 text-green-800',
  INFO:     'bg-gray-100 text-gray-600',
}

export function ComplianceTable({ events, persona }) {
  // Filter events by persona visibility rules
  const visible = filterByPersona(events, persona)
  return (
    <div className="divide-y divide-gray-100">
      {visible.map(e => (
        <div key={e.check_id} className="flex gap-3 py-3">
          <span className={`text-xs font-medium px-2 py-1 rounded ${SEVERITY_COLORS[e.severity]}`}>
            {e.severity}
          </span>
          <div className="flex-1">
            <p className="text-sm font-medium">{e.title}</p>
            <p className="text-xs text-gray-500">{e.clause} — {e.description}</p>
            {e.ld_accrued_inr > 0 && (
              <p className="text-xs text-red-600 font-mono mt-1">
                LD: ₹{(e.ld_accrued_inr / 1e5).toFixed(2)} L
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
```

**Persona-based filtering** — what each role sees:
```js
// src/utils/personaFilter.js
export function filterByPersona(events, persona) {
  if (persona === 'Contract Manager' || persona === 'Auditor') return events
  if (persona === 'Project Manager') {
    return events.filter(e => ['CRITICAL', 'HIGH'].includes(e.severity))
  }
  if (persona === 'Site Engineer') {
    // Show only field-actionable events
    const fieldChecks = ['C06a', 'C06b', 'C07a', 'C07b', 'C08', 'C09']
    return events.filter(e => fieldChecks.includes(e.check_id))
  }
  if (persona === 'Contractor Rep') {
    // Show only LD, FM, payment events
    const contractorChecks = ['C03_M1', 'C03_M2', 'C03_M3', 'C03_M4', 'C04', 'C05', 'C11a', 'C11b', 'C13a', 'C13b', 'C14']
    return events.filter(e => contractorChecks.some(id => e.check_id.startsWith(id)))
  }
  return events
}
```

### 7.4 CORS configuration

Add to `api/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware
from config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 7.5 Serve React build from FastAPI (production)

```python
from fastapi.staticfiles import StaticFiles

# Add at the END of api/main.py (after all route definitions):
import os
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

For development, run both servers separately:
- FastAPI: `uvicorn api.main:app --port 8000 --reload`
- React: `cd frontend && npm run dev` (runs on port 5173)

---

## 8. Phase 6 — Production Hardening (Days 21-25)

### 8.1 API key authentication middleware

```python
# In api/main.py:
from fastapi import Security
from fastapi.security.api_key import APIKeyHeader
from config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(key: str = Security(api_key_header)):
    if settings.api_key_header and key != settings.api_key_header:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key

# Add to each endpoint: `_: str = Depends(verify_api_key)`
```

### 8.2 Request logging middleware

```python
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("contractguard")

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)")
    return response
```

### 8.3 File size and type validation

```python
# Add to upload_contract and upload_mpr endpoints:
MAX_FILE_SIZE_MB = 20
ALLOWED_CONTRACT_TYPES = {".pdf", ".docx"}
ALLOWED_MPR_TYPES = {".md", ".docx"}

async def validate_upload(file: UploadFile, allowed_types: set, max_mb: int = 20):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_types:
        raise HTTPException(400, f"File type {ext} not allowed. Allowed: {allowed_types}")
    content = await file.read()
    await file.seek(0)  # reset for subsequent reads
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {max_mb}MB limit")
    return content
```

### 8.4 Background job hardening

The APScheduler daily job in `api/main.py` currently has no error handling for DB failures. Add:

```python
def daily_background_job():
    try:
        # ... existing job code ...
    except Exception as e:
        logger.error(f"[Scheduler] Daily job failed: {e}")
        # Do not re-raise — scheduler should keep running
```

### 8.5 Health check endpoint improvements

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
        "langgraph": "enabled",
    }
```

### 8.6 Docker setup (optional but recommended)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build React frontend
RUN apt-get update && apt-get install -y nodejs npm
RUN cd frontend && npm install && npm run build

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `docker-compose.yml`:
```yaml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db]
    volumes:
      - ./data:/app/data
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: contractguard
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports: ["5432:5432"]
volumes:
  pgdata:
```

---

## 9. New File Structure

```
Contract-EL-main/
├── .env                         # (unchanged — same keys)
├── config.py                    # NEW — Pydantic Settings
├── requirements.txt             # + langgraph, langchain-core, pydantic-settings, alembic
├── startup.sh
│
├── agents/
│   ├── compliance_engine.py     # UNCHANGED
│   ├── compliance_agent.py      # UNCHANGED
│   ├── escalation_agent.py      # UNCHANGED
│   ├── eot_agent.py             # BUG FIX: overlap → overlap_days
│   ├── explainer_agent.py       # UNCHANGED
│   ├── mpr_parser.py            # BUG FIX: machinery + BoQ
│   ├── parser_agent.py          # CHANGE: wire EXTRACTION_PROMPTS to LLM fallback
│   ├── extraction_engine.py     # BUG FIX: FM notice regex
│   ├── risk_predictor.py        # UNCHANGED
│   ├── pdf_exporter.py          # UNCHANGED
│   ├── orchestrator.py          # KEEP (legacy /trigger endpoint still uses it)
│   ├── graph_state.py           # NEW — TypedDict state
│   ├── langgraph_nodes.py       # NEW — node functions
│   └── langgraph_graph.py       # NEW — StateGraph definition
│
├── api/
│   ├── main.py                  # EXTEND: new endpoints, LangGraph wired to /upload-mpr
│   └── __init__.py
│
├── db/
│   ├── models.py                # EXTEND: add MPRRecord model
│   ├── database.py              # UNCHANGED
│   ├── vector_store.py          # UNCHANGED
│   └── __init__.py
│
├── tools/
│   ├── weather_tool.py          # REWRITE: Open-Meteo + override
│   └── news_tool.py             # REWRITE: GNews + file override
│
├── utils/
│   ├── groq_client.py           # UNCHANGED
│   ├── docx_to_md.py            # UNCHANGED
│   └── __init__.py
│
├── scripts/
│   ├── init_db.py               # MINOR UPDATE: creates new MPRRecord table
│   └── (existing test scripts unchanged)
│
├── migrations/                  # NEW — Alembic migration files
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
│       └── 001_add_mpr_records.py
│
├── data/
│   ├── rule_store/              # (unchanged)
│   ├── models/                  # (unchanged)
│   ├── reports/                 # (unchanged)
│   ├── overrides/               # NEW — JSON override files for news/weather
│   │   ├── weather_override.json
│   │   └── news_override_xyz.json
│   └── uploads/                 # (unchanged)
│
├── frontend/                    # NEW — React application
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── api/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── utils/
│       ├── App.jsx
│       └── main.jsx
│
└── dashboard.py                 # KEEP for backwards-compat but no longer primary UI
```

---

## 10. New .env Reference

```env
# ── DATABASE ──────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:helloPeter%402005@localhost:5432/contractguard

# ── GROQ API KEYS (round-robin rotated) ─────────────────────────────────
KEY1=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
KEY2=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
KEY3=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
KEY4=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── WEATHER ──────────────────────────────────────────────────────────────
# Options: "open_meteo" (default, free, no key), "manual", "synthetic"
WEATHER_SOURCE=open_meteo

# To manually override FM weather validation (JSON string):
# WEATHER_MANUAL_DATA={"total_mm": 512, "extreme_days": 8, "historical_avg_mm": 120, "source": "site_gauge_reading"}

# ── NEWS ─────────────────────────────────────────────────────────────────
# Get free key at https://gnews.io (100 req/day free)
GNEWS_API_KEY=your_gnews_key_here

# To override with a local JSON file:
# NEWS_OVERRIDE_FILE=data/overrides/news_xyz_constructions.json

# ── API SECURITY (optional) ──────────────────────────────────────────────
# If set, all API endpoints require: X-API-Key: <this value>
# API_KEY_HEADER=your_secret_key_here

# ── CORS (React dev server) ───────────────────────────────────────────────
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ── LLM MODEL OVERRIDES (optional) ──────────────────────────────────────
# LLM_MODEL_EXTRACTION=llama-3.3-70b-versatile
# LLM_MODEL_NARRATION=llama-3.1-8b-instant
```

---

## 11. Testing Checklist

### Phase 0 — Bug fixes
- [ ] Run `python agents/eot_agent.py` → no NameError on PARTIALLY_APPROVED case
- [ ] Upload fake contract, check `data/rule_store/` → `force_majeure.notice_deadline_days` is `7` not `null`
- [ ] Upload Scenario C MPR → `machinery_deployment_pct` reflects actual MPR value, not hardcoded 80

### Phase 1 — API tools
- [ ] `WeatherTool().get_rainfall_data("Karnataka, India", "2026-06-01", "2026-06-07")` returns `source: "open_meteo_archive"` not synthetic
- [ ] Set `WEATHER_MANUAL_DATA={"total_mm":512,...}` → verify_force_majeure returns `valid: true`
- [ ] `WeatherTool.set_override(...)` in test code → override respected
- [ ] `NewsTool().get_entity_news("XYZ Constructions")` hits GNews if key is set
- [ ] `NEWS_OVERRIDE_FILE` → news data comes from JSON file

### Phase 2 — Database
- [ ] `scripts/init_db.py` creates `mpr_records` table without error
- [ ] Upload Scenario A MPR → `mpr_records` table has 1 row
- [ ] Upload Scenario B MPR for same contract → `mpr_records` has 2 rows
- [ ] `GET /projects` returns both projects with last state populated
- [ ] `GET /projects/NHAI_KA_EPC_2025_KA-03/mpr-history` returns 2 rows with day_number, actual_pct, risk_score

### Phase 3 — LLM parser
- [ ] Upload fake contract → check `data/audit/extraction_audit_*.json` → LLM fallback fields show `"method": "groq_llm_fallback"` not generic
- [ ] Upload a differently-worded contract → LLM fallback correctly extracts milestones using schema prompts

### Phase 4 — LangGraph
- [ ] `python -c "from agents.langgraph_graph import run_pipeline; print('OK')"` — no import errors
- [ ] Upload Scenario C MPR → final state has `escalation_record` populated (CRITICAL event should trigger)
- [ ] Upload Scenario D MPR (FM) → final state goes through `eot_fm` node, then `compliance`, then `risk`
- [ ] `GET /healthz` → `langgraph: "enabled"`

### Phase 5 — React frontend
- [ ] `cd frontend && npm run dev` → dashboard loads at http://localhost:5173
- [ ] Project sidebar shows all projects from `GET /projects`
- [ ] S-curve chart renders with real data from `/mpr-history`
- [ ] Persona selector changes which compliance events are shown
- [ ] File upload dropzone accepts .docx and .pdf, rejects .xlsx
- [ ] Risk trend chart shows ascending risk score for Scenarios A→B→C sequence

### Phase 6 — Production
- [ ] `X-API-Key` header rejected with 403 when wrong key
- [ ] File > 20MB rejected with 413
- [ ] `GET /healthz` shows all services status
- [ ] APScheduler job runs without crash after 24h

---

## 12. Known Limitations & Honest Caveats

### Risk predictor is trained on synthetic data

The XGBoost model (`agents/risk_predictor.py`) generates its own training data in `generate_training_data()` — 3000 synthetic project snapshots whose "at-risk" features are hand-crafted based on domain assumptions. The model will produce a number but its predictions cannot be validated against real Indian infrastructure project outcomes until you collect labelled historical MPR data from actual projects. SHAP explanations are technically correct but reflect the synthetic training distribution, not real failure patterns. For production trust, this needs 6-12 months of real MPR data with known outcomes.

### Parsing accuracy on real contracts

The regex extraction engine works well on the fake contract because the fake contract was written to match the regex patterns. Real government contracts — especially older CPWD contracts — are often scanned PDFs with inconsistent formatting, section numbering by Roman numerals, and embedded tables that pdfplumber misreads. The LLM fallback compensates for this but LLMs can hallucinate clause numbers and monetary values. Every parsed rule store should be manually reviewed before first use on a real project.

### Open-Meteo coordinate mapping

The `LOCATION_COORDS` dictionary maps location name strings to lat/lon coordinates. It covers major Indian cities and states but uses centroids — a project at the northern tip of Karnataka gets the same coordinates as one at the southern tip. For precise FM validation, the site engineer should be able to enter actual GPS coordinates when submitting a FM claim, and these should be stored in the exec_data.

### GNews free tier

GNews free tier is 100 requests per day. Each `get_entity_news()` call makes 2 requests (2 query term combinations). With multiple projects each getting scanned on every MPR upload, this can exhaust the daily quota quickly. The synthetic fallback is deterministic (same entity always gets same result), which is a reasonable degradation. For production with many projects, upgrade to a paid tier or implement a daily caching layer that only hits GNews once per contractor per day.

### LangGraph checkpointing

The LangGraph implementation above uses in-memory state only — there is no persistence of graph run state to a database. If the server restarts mid-pipeline (e.g. during a long Groq call), the run is lost. LangGraph supports SQLite and PostgreSQL checkpointers (`SqliteSaver`, `PostgresSaver`) for fault-tolerant runs. Adding this is the recommended next step after the basic LangGraph integration is working.

### No authentication on uploaded documents

The `/upload-contract` and `/upload-mpr` endpoints accept any file from any caller. In a multi-project environment, a Site Engineer for Project A should not be able to upload to Project B's contract. Role-based access control — at minimum checking that the caller's project assignment matches the `contract_id` form field — is needed before this is used in a real office.

---

*End of action plan. Total estimated effort: 25 working days for one developer familiar with Python, FastAPI, and React. The phases are ordered by dependency — each phase is independently deployable and testable before the next begins.*

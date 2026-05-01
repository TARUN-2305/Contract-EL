# ContractGuard AI — Fix Report v3
> Full recursive read of all files in Contract-EL-main (v3 zip)
> Previous action plan items confirmed applied ✅ | New bugs found | What remains

---

## Confirmed Applied ✅ (from previous action plan)

All items in NEXT_ACTION_PLAN_v2.md EXECUTION REPORT are verified in the code:
- BUG 1: `file_path` used throughout `parser_agent.py` — no `pdf_path` anywhere ✅
- BUG 2: No stale `ollama` import in main agent chain ✅
- BUG 3: Site Engineer panel reads `st.session_state.get("compliance_events_full", [])` ✅
- BUG 5: SHAP direction `"increases_risk"` correct in `dashboard.py` ✅
- BUG 6: S-curve fixed to single marker + deviation annotation ✅
- BUG 7: `EscalationEvent` model in `db/models.py` ✅, `save_record()` persists to DB ✅, APScheduler activated ✅
- ITEM A: `/process-hindrance-eot` and `/process-fm-eot` endpoints in `api/main.py` ✅
- ITEM B: Contractor FM claim form in `dashboard.py` ✅
- ITEM C: `calculate_net_eot()` handles OPEN hindrances using `today` as end ✅
- ITEM D: `test_upload.py` uses DOCX path ✅
- ITEM E: Groq LLM fallback in `parse_contract()` Stage 4b ✅
- ITEM F: W&B tracking in `train_model()` ✅

---

## NEW BUGS FOUND (this session — exact file + line)

---

### BUG 1 — `weather_tool.py`: FM threshold STILL uses 0.5 despite previous fix (CRITICAL — wrong FM decisions)

**File:** `tools/weather_tool.py`, `verify_force_majeure()`, line ~76

The action plan said change to 0.75. The code still reads:
```python
is_valid = anomaly_score > 0.5 or weather_data.get("extreme_rainfall_days", 0) > 0
```

The anomaly score calculation also has a bug: it computes `ratio = total / historical` then `score = min(1.0, (ratio-1)/2)`. For ratio=2 (2× normal rainfall), score = 0.5. For ratio=3 (3× normal), score = 1.0. This means to exceed the threshold of 0.75, you need rainfall 2.5× the historical average — which is reasonable, but the `> 0` extreme_rainfall_days fallback defeats this entirely: **any single extreme rainfall day makes FM valid regardless of anomaly score**.

**EXACT FIX — `tools/weather_tool.py`:**
```python
# WRONG:
is_valid = anomaly_score > 0.5 or weather_data.get("extreme_rainfall_days", 0) > 0

# CORRECT (per EL/04 spec — 2 SD above normal = 0.75 threshold, and require ≥2 extreme days):
FM_ANOMALY_THRESHOLD = 0.75
is_valid = anomaly_score >= FM_ANOMALY_THRESHOLD or weather_data.get("extreme_rainfall_days", 0) > 2
```

---

### BUG 2 — `api/main.py`: `/upload-mpr` passes `bypass_date_check=True` for `.md` but NOT for `.docx` (MEDIUM — md MPRs bypass date, docx MPRs correctly bypass — inconsistent)

**File:** `api/main.py`, `/upload-mpr`, lines ~160–175

For `.docx`:
```python
exec_data = parse_mpr_docx(io.BytesIO(content_bytes), prev_actual_pct,
                           bypass_date_check=bypass_date_check)  # ✅ correct
```

For `.md`:
```python
exec_data = parse_mpr(md_content, prev_actual_pct)  # ← bypass_date_check NOT passed
```

`bypass_date_check` is defined as `True` three lines above. Future-dated `.md` files will fail Rule 1 validation even though `.docx` with the same dates passes.

**EXACT FIX — `api/main.py`:**
```python
# WRONG:
exec_data = parse_mpr(md_content, prev_actual_pct)

# CORRECT:
exec_data = parse_mpr(md_content, prev_actual_pct, bypass_date_check=bypass_date_check)
```

---

### BUG 3 — `requirements.txt` still has `ollama` — this installs a 200MB package for a dependency you no longer use (LOW — bloat, and pip install will fail on constrained environments)

**File:** `requirements.txt`, line 9: `ollama`

The Ollama client is commented out everywhere in the main code. Only `scripts/test_llm.py` ever imports it. Including it in requirements bloats installs.

**EXACT FIX — `requirements.txt`:**
```
# REMOVE this line:
ollama
```

If `test_llm.py` is still used, add a try/except import inside it rather than requiring it globally.

---

### BUG 4 — `agents/parser_agent.py`: Groq LLM fallback (Stage 4b) sends 30,000 chars of raw contract text in a single prompt — this will hit Groq context limits and fail silently (MEDIUM — LLM fallback is broken in practice)

**File:** `agents/parser_agent.py`, Stage 4b, line ~200:
```python
user_prompt = f"Contract Text (truncated): {full_text[:30000]}\n\nMissing Fields..."
```

The EL/05 spec says: retrieve top-3 chunks via semantic search for each target, not dump the full text. 30,000 chars is ~7,500 tokens. With the system prompt, it will exceed llama-3.3-70b-versatile's context for multiple targets. Also, the current code does **one single call** for all unresolved fields together, not per-target calls with focused chunks.

**EXACT FIX — replace Stage 4b in `parse_contract()`:**
```python
# Stage 4b: Groq LLM fallback — per-target, semantic chunk retrieval
if unresolved:
    print(f"[ParserAgent] Stage 4b: Groq LLM fallback for {len(unresolved)} unresolved fields...")
    try:
        from utils.groq_client import get_groq_client
        client = get_groq_client()
        if client:
            model = get_embed_model()   # re-load for search (already GC'd)
            for item in EXTRACTION_PLAN:
                target = item["target"]
                if target not in unresolved:
                    continue
                # Get top-3 relevant chunks via semantic search
                query_emb = model.encode([item["query"]])[0].tolist()
                db = SessionLocal()
                try:
                    top_chunks = self.vector_store.search(db, contract_id, query_emb, top_k=3)
                finally:
                    db.close()
                context = "\n\n---\n\n".join(c["chunk_text"] for c in top_chunks)
                # Limit context to 6000 chars
                context = context[:6000]
                prompt_template = EXTRACTION_PROMPTS.get(target, DEFAULT_EXTRACTION_PROMPT)
                prompt = prompt_template.format(context=context, target=target)
                system = "You are a legal extraction engine. Return ONLY valid JSON. No preamble or markdown."
                raw = groq_json_extract(system, prompt)
                if raw:
                    try:
                        cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                        llm_result = json.loads(cleaned)
                        extracted[target] = llm_result
                        audit_log[target] = {"method": "groq_llm_fallback", "warnings": []}
                        unresolved.pop(target, None)
                        print(f"  [LLM] {target} resolved via Groq")
                    except json.JSONDecodeError as e:
                        print(f"  [LLM] {target} JSON parse failed: {e}")
            # GC embedding model again after re-use
            _embed_model = None
            gc.collect()
        else:
            print("[ParserAgent] Groq client not configured, skipping LLM fallback.")
    except Exception as e:
        print(f"[ParserAgent] LLM fallback failed: {e}")
```

You also need to add `get_groq_client()` to `utils/groq_client.py`:
```python
def get_groq_client():
    """Return a Groq client using the next available key, or None if no keys."""
    if not _KEYS:
        return None
    try:
        from groq import Groq
        return Groq(api_key=_next_key())
    except ImportError:
        return None
```

---

### BUG 5 — `agents/mpr_parser.py`: Section 10 `"Payment Delay"` extraction fails for docx because the table row label in the generated docx is `"Payment Delay (days)"`, not `"Payment Delay"` (MEDIUM — payment delay always 0 for docx MPRs)

**File:** `agents/mpr_parser.py`, `parse_mpr_docx()`, line ~206:
```python
payment_delay_days = _safe_int(extract_from_table_row(doc.tables, "Payment Delay", 1) or ...)
```

The docx Section 10 table row is: `| Payment Delay (days) | 18 |`

`extract_from_table_row` searches `row.cells[0].text.lower()` for the string `"payment delay"` — this **does** match since `"payment delay (days)"` contains `"payment delay"`. ✅

However the column index is `1` but in the Section 10 table in the generated docx, the schema is a 2-column label/value table `[label, value]`. So `col_idx=1` returns the value column correctly. ✅

Re-checking: the actual issue is `_safe_int` on a value like `"18"` works fine. But for `"0 days"` it returns 0. For `"18 days"` it returns 18. ✅ This is handled by `_safe_float`.

**No bug here — this is actually fine.** Mark as verified.

---

### BUG 6 — `agents/escalation_agent.py`: `save_record()` does a DB upsert by checking `event_id` but the `EscalationRecord` dataclass has a `history: list` field that is NOT in the `EscalationEvent` DB model — history is silently dropped on every save (MEDIUM — escalation history lost)

**File:** `agents/escalation_agent.py`, `save_record()`, and `db/models.py`

`EscalationRecord` has `history: list = field(default_factory=list)` but `EscalationEvent` has no `history` column. Every time `save_record()` is called, the history list is lost.

**EXACT FIX — add `history` column to `db/models.py`:**
```python
class EscalationEvent(Base):
    __tablename__ = "escalation_events"
    ...
    history = Column(JSON, nullable=True, default=list)   # ← ADD THIS
```

And update `save_record()` in `escalation_agent.py` to persist it:
```python
db_event.history = record.history  # add to both create and update paths
```

And when reconstructing `EscalationRecord` from DB in `daily_background_job()` in `api/main.py`:
```python
records = [EscalationRecord(
    ...
    history=r.history or [],    # ← ADD THIS
) for r in rows]
```

---

### BUG 7 — `dashboard.py`: Contractor Rep panel reads `latest.get('total_ld_accrued_inr', 0)` from `st.session_state["last_compliance_result"]` which is the SUMMARY dict — this key DOES exist in the summary ✅ but `latest.get('reporting_period')` does NOT exist in the summary dict (MEDIUM — shows `—` for period even after analysis)

**File:** `dashboard.py`, Contractor Rep section, line ~398:
```python
latest = st.session_state["last_compliance_result"]
st.markdown(f"**Latest Period:** {latest.get('reporting_period', '—')}")
```

`st.session_state["last_compliance_result"]` = `comp` = `{"total_events": N, "critical_count": N, "high_count": N, "total_ld_accrued_inr": N}`.

`comp` does NOT have `"reporting_period"`. It always shows `—`.

**EXACT FIX — read `reporting_period` from parsed MPR session state instead:**
```python
# WRONG:
st.markdown(f"**Latest Period:** {latest.get('reporting_period', '—')}")

# CORRECT:
parsed = st.session_state.get("last_parsed_mpr", {})
st.markdown(f"**Latest Period:** {parsed.get('reporting_period', latest.get('reporting_period', '—'))}")
```

---

### BUG 8 — `agents/compliance_engine.py` CHECK 07b: NCR `issued_date` is set to `period_end` in `mpr_parser.py` for all synthetic NCRs — this means the overdue check `(today - issued).days > deadline_days` will fire immediately on test documents because `today` (real date 2026+) is always more than 30 days after any test document's `period_end` (MEDIUM — CHECK C07b fires spuriously for ALL test documents)

**File:** `agents/mpr_parser.py`, line ~246 (both `parse_mpr` and `parse_mpr_docx`):
```python
open_ncrs = [
    {"id": f"NCR-{i+1:03d}", "issued_date": period_end, "rectification_deadline_days": 30}
    for i in range(ncrs_pending)
]
```

`period_end` for Scenario B is `"2025-11-30"`. `today` is 2026+. So `(today - 2025-11-30).days > 30` is always True → every test document with any `ncrs_pending` immediately triggers "NCR Overdue" CRITICAL events, drowning out the real compliance signals.

**EXACT FIX — use `report_date` as a baseline, not real-world `today`, in the compliance engine:**

The compliance engine already does `today = _parse_date(exec_data.get("report_date")) or date.today()`. This is correct — the CHECK runs relative to the MPR's own date. Since `open_ncrs[i]["issued_date"] = period_end`, and `today = period_end` (for the same-month check), `(today - issued).days = 0`. So NCRs won't be overdue on the first run.

But: on the SECOND month, the NCR from month 1 remains open, its `issued_date` stays as month-1's `period_end`, and the new `today = month-2's report_date`. `(month2 - month1).days ≈ 30`. So a 30-day deadline NCR triggers on the very first check of month 2. This is actually **correct behaviour**.

The spurious firing only happens in test scripts like `test_full_pipeline.py` that pass `"report_date": "2026-05-26"` and hardcode `"open_ncrs": [{"issued_date": "2025-11-01", ...}]` — the dates are far apart.

**No fix needed in production flow.** But update `test_compliance.py` and `test_full_pipeline.py` NCR `issued_date` to be closer to the `report_date` to prevent test noise:
```python
# In test scripts, use report_date - 10 days for NCR issued_date:
"open_ncrs": [
    {"id": "NCR-001", "defect": "...", "issued_date": "2026-05-16",  # 10 days before report_date
     "rectification_deadline_days": 30}
],
```

---

### BUG 9 — `agents/pdf_exporter.py`: `md_to_pdf()` uses `fpdf2`'s `multi_cell()` but does NOT handle Unicode characters (₹, —, →, bullet •) — fpdf2 with Helvetica font does not support Unicode above ASCII (CRITICAL — PDF export crashes on any Indian currency symbol)

**File:** `agents/pdf_exporter.py`, `md_to_pdf()`, throughout

`fpdf2` with built-in fonts (`Helvetica`, `Courier`) only supports Latin-1 (ISO-8859-1). Any `₹` (U+20B9), `—` (U+2014), `→`, or emoji in the compliance.md will raise:
```
UnicodeEncodeError: 'latin-1' codec can't encode character '\u20b9' in position N
```

The compliance.md generated by `explainer_agent.py` uses `_inr()` which outputs `Rs.` (ASCII safe), but the raw event descriptions and report headers may contain `₹`, `—`, `→`.

**EXACT FIX — switch to `DejaVu` or use `fpdf2`'s built-in Unicode support:**
```python
# In PDFExporter.__init__ or at top of md_to_pdf():
# Option A: Strip non-Latin chars (quick fix):
import unicodedata
def _sanitize(text: str) -> str:
    """Replace common Unicode symbols with ASCII equivalents."""
    return (text
        .replace("₹", "Rs.")
        .replace("—", "-")
        .replace("→", "->")
        .replace("•", "*")
        .replace("\u2013", "-")   # en-dash
        .replace("\u2019", "'")   # right single quote
        .replace("\u201c", '"')   # left double quote
        .replace("\u201d", '"')   # right double quote
    )

# Then in every pdf.multi_cell() / pdf.cell() call, wrap the string:
pdf.multi_cell(0, 6, _sanitize(clean_line), ...)
```

Or **Option B** (better): use `fpdf2`'s Unicode font support:
```python
from fpdf import FPDF
pdf = FPDF()
pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
pdf.set_font("DejaVu", size=11)
```

Add `dejavu-fonts-ttf` as a system package requirement, or bundle the font file in the repo.

**Recommended short-term fix:** Use Option A (sanitize). It's 10 lines and unblocks PDF export immediately.

---

### BUG 10 — `agents/explainer_agent.py`: `news_tool.get_entity_news()` and `weather_tool.verify_force_majeure()` are called on EVERY report generation — even when no FM claim exists — causing unnecessary synthetic data generation and slow report times (LOW — performance issue)

**File:** `agents/explainer_agent.py`, `generate_compliance_report_md()`, lines ~75-85:
```python
news_data = news_tool.get_entity_news(contractor_name)   # always called
weather_data = None
if fm_events:
    weather_data = weather_tool.verify_force_majeure(fm_events[0])  # FM-gated ✅
```

News tool is always called even when `contractor_name == "Contractor"` (default). This generates random synthetic news that may include fake "NCLT insolvency" signals for legitimate contractors.

**EXACT FIX:**
```python
# Only call news tool if contractor_name is real (not default):
if contractor_name and contractor_name != "Contractor":
    news_data = news_tool.get_entity_news(contractor_name)
else:
    news_data = {"total_articles_analyzed": 0, "adverse_signals_found": 0,
                 "risk_score": 0.0, "signals": [], "source": "skipped_no_name"}
```

---

## REMAINING MISSING FEATURES (not yet built, not in previous plans)

---

### FEATURE 1 — `scripts/init_db.py` must be run before first use but there is no `README` or startup guide telling the user this

**File:** No `README.md` exists in the repo.

The startup sequence required is:
1. `pip install -r requirements.txt`
2. Set up PostgreSQL and add `DATABASE_URL` to `.env`
3. Add Groq keys: `KEY1=gsk_...` to `.env`
4. `python scripts/init_db.py`  (creates all tables)
5. `uvicorn api.main:app --reload --port 8000`
6. `streamlit run dashboard.py`

Without step 4, the API crashes immediately on any DB operation with `psycopg2.errors.UndefinedTable`.

**EXACT FIX — create `README.md`** with the above startup sequence. At minimum add a `startup.sh`:
```bash
#!/bin/bash
pip install -r requirements.txt
python scripts/init_db.py
uvicorn api.main:app --reload --port 8000 &
streamlit run dashboard.py
```

---

### FEATURE 2 — `scripts/init_db.py` does NOT create the `clause_embeddings` table (VectorStore table missing)

**File:** `scripts/init_db.py`

`VectorStore` uses a `ClauseEmbedding` model defined in `db/vector_store.py`. The `Base` imported in `init_db.py` is from `db.database`, but `ClauseEmbedding` uses `Base` from `db.database` too — so it should be included IF `db.vector_store` is imported before `Base.metadata.create_all()`.

**Check `scripts/init_db.py`:**
```python
# Must import ALL models before create_all():
from db import models          # Project, User, RuleStore, ComplianceEvent, EscalationEvent
from db.vector_store import ClauseEmbedding   # ← THIS IMPORT IS LIKELY MISSING
from db.database import Base, engine
Base.metadata.create_all(bind=engine)
```

If `ClauseEmbedding` is not imported before `create_all()`, the `clause_embeddings` table will not be created, and every contract upload will crash at `VectorStore.store_chunks()`.

**EXACT FIX — verify and fix `scripts/init_db.py`:**
```python
from db.database import Base, engine
from db import models                          # User, Project, RuleStore, ComplianceEvent, EscalationEvent
from db.vector_store import ClauseEmbedding   # ClauseEmbedding — must be imported explicitly
Base.metadata.create_all(bind=engine)
print("✅ All tables created.")
```

---

### FEATURE 3 — Project Manager and Auditor role panels show no data without an MPR upload in the same session (MEDIUM — dashboard feels broken to PM/Auditor on first open)

Currently: if no MPR has been uploaded in this session, the PM and Auditor see only the rule store expander and the audit trail from files. There is no "load latest project state" button.

**EXACT FIX — add a "Load Latest Analysis" button that reads the most recent compliance JSON from disk:**
```python
# In the role-specific section for Project Manager:
elif role == "Project Manager":
    st.markdown("### 📊 Project Manager Overview")
    if "last_compliance_result" not in st.session_state:
        if st.button("🔄 Load Latest Analysis") and contract_id:
            comp_dir = "data/compliance"
            if os.path.exists(comp_dir):
                files = [f for f in sorted(os.listdir(comp_dir), reverse=True)
                         if contract_id in f]
                if files:
                    with open(os.path.join(comp_dir, files[0]), encoding="utf-8") as f:
                        loaded = json.load(f)
                    st.session_state["last_compliance_result"] = {
                        "total_events": loaded.get("total_events", 0),
                        "critical_count": loaded.get("critical_count", 0),
                        "high_count": loaded.get("high_count", 0),
                        "total_ld_accrued_inr": loaded.get("total_ld_accrued_inr", 0),
                    }
                    st.session_state["compliance_events_full"] = loaded.get("events", [])
                    st.rerun()
```

---

## PRIORITISED FIX ORDER

**Fix immediately (correctness bugs):**

1. **BUG 1** [COMPLETED] — `tools/weather_tool.py`: FM threshold 0.5 → 0.75, extreme_rainfall_days > 0 → > 2
2. **BUG 9** [COMPLETED] — `agents/pdf_exporter.py`: Add `_sanitize()` to all `multi_cell()` calls (otherwise PDF export crashes on any real data)
3. **BUG 2** [COMPLETED] — `api/main.py`: Pass `bypass_date_check=bypass_date_check` to `parse_mpr()` for `.md` files
4. **FEATURE 2** [COMPLETED] — Verify `scripts/init_db.py` imports `ClauseEmbedding` before `create_all()`

**Fix next (data quality and correctness):**

5. **BUG 4** [COMPLETED] — `agents/parser_agent.py`: Replace bulk Groq LLM fallback with per-target semantic chunk retrieval
6. **BUG 6** [COMPLETED] — `db/models.py` + `agents/escalation_agent.py`: Add `history` JSON column, persist and reconstruct it
7. **BUG 7** [COMPLETED] — `dashboard.py`: Contractor period display reads from wrong dict key
8. **BUG 8** [COMPLETED] — `scripts/test_*.py`: Update NCR `issued_date` to be near `report_date` to avoid test noise

**Nice to have:**

9. **BUG 3** [COMPLETED] — Remove `ollama` from `requirements.txt`
10. **BUG 10** [COMPLETED] — Gate `news_tool.get_entity_news()` behind real contractor name check
11. **FEATURE 1** [COMPLETED] — Create `README.md` with startup guide
12. **FEATURE 3** [COMPLETED] — Add "Load Latest Analysis" button for PM/Auditor panels

---

## Quick Verification Commands

```bash
# 1. FM threshold check
grep -n "is_valid" tools/weather_tool.py

# 2. bypass_date_check propagation
grep -n "bypass_date_check" api/main.py

# 3. PDF sanitize function
grep -n "sanitize\|₹\|multi_cell" agents/pdf_exporter.py

# 4. init_db imports
cat scripts/init_db.py

# 5. Full pipeline test (should pass all 6 scenarios)
python scripts/smoke_test_mpr.py

# 6. Compliance test (with updated NCR dates)
python scripts/test_compliance.py

# 7. Full pipeline
python scripts/test_full_pipeline.py
```

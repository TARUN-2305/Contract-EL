# ContractGuard AI — Catalogue Report & Error Log
**Date:** 2026-04-28  
**Session Recording:** `contractguard_catalogue_run_1777391782286.webp`

---

## ✅ What Looks Good (Working State)

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard loads | ✅ | Clean, no pre-fills after fix |
| All 5 role personas | ✅ | Role switcher works correctly |
| Contract Manager view | ✅ | Upload Contract (PDF/DOCX) + form fields shown |
| MPR upload widget | ✅ | Accepts `.md` and `.docx` |
| Field Action Items (Site Engineer) | ✅ | "[HIGH] Project Milestone II Missed" shown |
| Footer branding | ✅ | "Powered by XGBoost + Deterministic Rule Engine" |
| Role-specific headers | ✅ | Header shows active role name correctly |

---

## ❌ Errors & Issues Found

### ERROR 1 — Contract Upload: `parse_contract()` called with wrong kwarg
**Severity:** 🔴 CRITICAL  
**How triggered:** Dashboard submits `file_path=` but `ParserAgent.parse_contract()` signature still has `pdf_path=`  
**API Log:** `POST /upload-contract → 500 Internal Server Error`  
**Root Cause:** In `api/main.py` line ~142, we renamed the kwarg to `file_path=file_path` but `parser_agent.parse_contract()` signature still uses `pdf_path:str` as parameter name.  
**Fix Plan (Phase 2):**  
- Rename `pdf_path` → `file_path` in `ParserAgent.parse_contract()` method signature in `agents/parser_agent.py`

---

### ERROR 2 — Contract Upload: First attempt returned 422 (missing `contract_id`)
**Severity:** 🟠 HIGH  
**How triggered:** First upload attempt before Contract ID was set  
**API Log:** `POST /upload-contract → 422 Unprocessable Content`  
**Root Cause:** `contract_id` form field was empty. The dashboard does not prevent form submission when Contract ID is blank.  
**Fix Plan (Phase 2):**  
- Add `if not contract_id: st.warning("Please enter a Contract ID first.")` guard before the Parse Contract button is active

---

### ERROR 3 — File Upload: Playwright/headless cannot trigger native OS file picker
**Severity:** 🟡 MEDIUM (Demo/Test only — not a user-facing bug)  
**How triggered:** Browser subagent cannot interact with `<input type="file">` via pixel clicks  
**Root Cause:** Streamlit's file uploader uses a native browser file dialog which requires `setInputFiles()` Playwright API — not available in our browser subagent's pixel-click toolkit  
**Fix Plan (Phase 2):**  
- No code change needed. Add a **Drag & Drop zone** alternative using `st.experimental_data_editor` or implement a local path input text box as a demo bypass mode
- OR: Add a "Load Demo File" button that pre-loads a scenario file server-side

---

### ERROR 4 — `parse_contract()` uses Ollama LLM (`gemma4:e2b` model) — likely not running
**Severity:** 🔴 CRITICAL  
**How triggered:** Any contract upload triggers `ollama.Client()` calls in `ParserAgent`  
**Root Cause:** `parser_agent.py` calls `ollama.Client()` for LLM-based contract extraction. Ollama must be running locally with `gemma4:e2b` pulled — almost certainly not configured.  
**Evidence:** The 500 error on contract upload is likely caused by this (Ollama connection refused) before even reaching the docx parsing.  
**Fix Plan (Phase 2):**  
- Make ParserAgent fall back to **deterministic extraction only** (already implemented in `agents/extraction_engine.py`) when Ollama is unavailable
- Add `try/except` around Ollama calls, default to `deterministic_extract()` only path
- OR replace Ollama with Groq API (already configured for MPR analysis)

---

### ERROR 5 — `parse_contract()` method signature mismatch (pdf_path vs file_path)
**Severity:** 🔴 CRITICAL  
**Exact location:** `agents/parser_agent.py` line ~326-335  
**Current:** `def parse_contract(self, pdf_path: str, ...)` + internal uses `pdf_path`  
**API call:** `parser_agent.parse_contract(file_path=file_path, ...)`  
**Result:** `TypeError: parse_contract() got an unexpected keyword argument 'file_path'`  
**Fix Plan (Phase 2):**  
```python
# In agents/parser_agent.py, rename:
def parse_contract(self, file_path: str, ...)  # was: pdf_path
```

---

### ERROR 6 — Site Engineer "Field Action Items" shows hardcoded placeholder data
**Severity:** 🟠 HIGH  
**Observed:** "[HIGH] Project Milestone II Missed — Required 50% progress by Day 491, Actual 35.0%, Shortfall 15.0%, Delay 40 days"  
**Root Cause:** Field Action Items section is rendering **stale/hardcoded** mock data, not live data from an MPR analysis. This shows even before any file is uploaded.  
**Fix Plan (Phase 2):**  
- Wrap Field Action Items in `if "compliance_result" in st.session_state:` — only show after analysis runs

---

### ERROR 7 — Auditor Panel: Stale "Select Historical Report" dropdown with hardcoded entries  
**Severity:** 🟡 MEDIUM  
**Root Cause:** The Auditor view shows a historical report dropdown pre-populated with mock entries.  
**Fix Plan (Phase 2):**  
- Populate dropdown from actual files in `data/risk/` directory or `data/rule_store/`
- Show empty state message "No analysis history yet" when no files exist

---

## 📸 Screenshots Captured

| Screenshot | Description |
|-----------|-------------|
| `click_feedback_1777391836162.png` | Contract Manager — clean empty state |
| `click_feedback_1777392028220.png` | Project Manager — MPR upload section |
| `click_feedback_1777392154562.png` | Site Engineer — role dropdown + Field Action Items below fold |
| `click_feedback_1777392176075.png` | Auditor — role dropdown visible |
| `click_feedback_1777392097955.png` | Contract Manager — form filled by Playwright |

---

## 🗂 Phase 2 Fix Priority List

| Priority | Error | Fix |
|----------|-------|-----|
| P0 | Error 5 — `pdf_path` vs `file_path` kwarg mismatch | Rename param in `ParserAgent.parse_contract()` |
| P0 | Error 4 — Ollama not available, blocks all contract parsing | Add Ollama fallback → deterministic extraction only |
| P1 | Error 1 — 500 on contract upload | Caused by P0 fixes above |
| P1 | Error 2 — 422 when Contract ID is empty | Add validation guard in dashboard |
| P1 | Error 6 — Hardcoded Field Action Items | Wrap in session state guard |
| P2 | Error 7 — Hardcoded Auditor history dropdown | Populate from real files |
| P3 | Error 3 — Playwright file upload limitation | Add "Load Demo File" server-side button |

---

## 📹 Recording
Video: `C:\Users\tarun\.gemini\antigravity\brain\6302fc4b-ca1e-4940-89db-f14968d52d86\contractguard_catalogue_run_1777391782286.webp`

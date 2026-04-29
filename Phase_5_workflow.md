# Phase 5: Explainer Agent + Outputs + Dashboard

## Objective
Build the Explanation Agent (Module 06), the report generators (`compliance.md`, `predictions.md`), PDF export, and the Streamlit multi-page role-gated dashboard.

## Execution Steps

### Part A — Explainer Agent

1. **Explanation Agent:** Build `agents/explanation_agent.py`:
   - Implements `EXPLANATION_AGENT_PROMPT` from `05_AGENT_ENGINE.md`.
   - Audience-aware narration: SITE_ENGINEER, PROJECT_MANAGER, CONTRACTOR, AUDITOR.
   - Rules: every figure in ₹ and %, every deadline as date + days remaining, every decision with clause ref.

2. **compliance.md Generator:** Build `modules/report_generator.py`:
   - Produce the full `compliance_{project_id}.md` report matching the exact structure in `06_EXPLAINER_AND_OUTPUTS.md`.
   - Includes: Executive Summary table, Active Compliance Events (with colour-coded severity), Penalty Ledger Summary, Contractor's Rights, Audit Trail.

3. **predictions.md Generator:** Extend `modules/report_generator.py`:
   - Produce `predictions_{project_id}.md` matching the structure in `06_EXPLAINER_AND_OUTPUTS.md`.
   - Includes: Risk Score, Next Milestone Forecast, Top Risk Factors (SHAP), External Intelligence, Recommendations, Model Transparency table.

### Part B — PDF Export

4. **PDF Generator:** Build `modules/pdf_exporter.py` using `fpdf2`:
   - `compliance.pdf`: Cover page, executive summary, events, penalty ledger, contractor rights, audit trail.
   - `predictions.pdf`: Risk gauge, S-curve chart, SHAP chart, forecast table, recommendations.
   - Numbered, dated, version-stamped for formal project records.

### Part C — Streamlit Dashboard

5. **Authentication & Role Gating:** Build `app/login.py`:
   - Simple login → role detection → route to role-specific views.
   - Roles: `contract_manager`, `site_engineer`, `project_manager`, `contractor`, `auditor`.

6. **Page 1 — Project Overview:** `app/pages/overview.py`
   - Project card, progress ring, S-curve chart (Plotly), risk score badge, active violations count.

7. **Page 2 — Compliance Status:** `app/pages/compliance.py`
   - Filterable compliance events list, penalty ledger table, EoT decisions log.

8. **Page 3 — MPR Upload:** `app/pages/mpr_upload.py`
   - Upload `.md` file, validation feedback, parsed data preview, hindrance register entry form.

9. **Page 4 — Risk & Predictions:** `app/pages/risk.py`
   - Risk score gauge, SHAP waterfall chart, forecast table, external signals panel, recommendations.

10. **Page 5 — Notices & Claims (Contractor):** `app/pages/notices.py`
    - Received notices, FM claim form, EoT application form, variation order claim form.

11. **Page 6 — Audit Trail:** `app/pages/audit.py`
    - Full event log, agent invocation log, PDF download buttons.

## Verification
- Run the full pipeline end-to-end: Upload contract → Upload MPR → View compliance report → View risk dashboard.
- Verify each role sees only their permitted pages.
- Download `compliance.pdf` and `predictions.pdf` → verify they match the structure in `06_EXPLAINER_AND_OUTPUTS.md`.
- Cross-check the compliance.md and predictions.md outputs against the sample reports in the EL spec.

Implemented ✅
9
modules complete
Partial ⚠️
5
needs finishing
Not built ❌
8
items pending
RAM unlock
~6
items unblocked
Phase 1 — Now
RAM-independent fixes
Phase 2 — Post-RAM
LLM + live tools
Phase 3 — Polish
Dashboard + exports
Phase 1 — Do now (no RAM needed)
Critical bug
MPR markdown parser — Sections 3–11 not implemented
System currently accepts raw JSON POST body. The whole Site Engineer upload workflow is broken for real use — the test docx files you have are unusable until this is fixed.
Hide ↑
What to build: agents/mpr_parser.py — reads the structured MD template from Module 02.

Parse order:
S1: regex key-value pairs → project metadata dict
S2: regex key-value pairs → progress floats
S3/S4/S5/S6: markdown table parser (split |, strip whitespace, map headers to schema columns)
S7–S10: regex key-value pairs
S11: signature fields

Validation: Run all 5 existing validation rules against parsed output. Reject with field-level error messages on failure.

Wire into: POST /upload-mpr new endpoint → parse → validate → store exec_data row → trigger /full-analysis

~1 day effortNo RAM dependencyUnblocks test docs
Critical gap
Item Rate (CPWD GCC) contract type — zero implementation
Only EPC is live. Two contract types are in scope per spec. All your CPWD test logic (7-day show cause, monthly targets, bonus Clause 2A) is untested.
Hide ↑
What differs in Item Rate:
— LD: 1%/month (daily basis) of tendered value, cap 10% (not 0.05%/day of milestone value)
— Milestones: monthly absolute quantity targets, not % of SCP
— Default notice: 7-day show cause (not 60-day cure)
— EoT: Hindrance Register mandatory, joint AE/JE sign
— Bonus: CPWD Clause 2A (1%/month, max 5%) — already scaffolded
— Dispute: SE → DRC → Arbitration (not Conciliation → Arbitration)

Implementation: Add contract_type branch in compliance_engine.py for all checks. The rule store schema already has the right keys — just needs the alternate calculation paths.

~2 days effortNo RAM dependencyDoubles contract coverage
High priority
RA Bill / Payment workflow tracking (Clause 7) — not implemented
Retention money (5%), payment deadline (30 days), interest on late payment — all in your RA Bill test doc but no compliance checks exist for them.
Hide ↑
Add 3 new compliance checks:
C13a — Payment delayed beyond 30 days → interest at 1%/month (Article 22.2)
C13b — Retention not released after DLP expiry → HIGH severity
C13c — Mobilisation advance recovery not deducted → MEDIUM

New data fields in exec_data schema:
ra_bill_submitted_date, payment_received_date, retention_released, mob_advance_recovered_pct

These are already in the MPR S10 template — just need to flow through to the compliance checks.

~1 day effortNo RAM dependencyTest doc: RA_BILL_RA07
High priority
EoT Agent — full decision schema + overlap deduction not built
C10/C11 checks exist in compliance engine but eot_decision.json output, overlap-aware net EoT calculation, and revised milestone dates are missing.
Hide ↑
Build agents/eot_agent.py:
1. Load hindrance register from DB for project
2. Check 14-day timeliness per hindrance (C10 — already exists)
3. Implement calculate_net_eot(): merge overlapping date ranges (interval merge algorithm), sum merged segments
4. Output eot_decision.json per schema in EL/05
5. Write revised milestone dates back to rule store

Test with: HINDRANCE_REGISTER_Overlapping_EoT_Test.docx — has 6 hindrances with known expected net EoT of 31 days after deductions. Your agent should match this exactly.

~1.5 days effortNo RAM dependencyTest doc ready
High priority
Escalation Agent — state machine not built (only C15 check exists)
The system detects the 90-day termination threshold but does not track notice tiers, cure period timers, or generate the correct next step.
Hide ↑
Build agents/escalation_agent.py as a state machine:

EPC states: NONE → NOTICE_OF_INTENT (60d cure) → TERMINATION_NOTICE → CONCILIATION (30d) → ARBITRATION
Item Rate states: NONE → SHOW_CAUSE (7d) → CONTRACT_DETERMINED → SE_APPEAL (15d file, 30d decision) → DRC (15d file, 90d decision) → ARBITRATION (30d)

Store per event: current_tier, tier_entered_date, tier_deadline, responsible_party
Trigger: CURE_PERIOD_EXPIRED in orchestrator
Output: next required action, deadline, notice template text

~2 days effortNo RAM dependencyTest with Scenario C
Medium priority
ADASYN class balancing — using scale_pos_weight as substitute
scale_pos_weight=3 is a reasonable fallback but ADASYN generates synthetic minority samples which better captures the decision boundary for rare default events.
Hide ↑
pip install imbalanced-learn — lightweight, no GPU needed, ~50MB

Replace in agents/risk_predictor.py:
from imblearn.over_sampling import ADASYN
X_res, y_res = ADASYN(random_state=42).fit_resample(X_train, y_train)

Then remove scale_pos_weight from XGBoost config. Re-run training and compare F1/PR-AUC on the held-out test set. Expect F1 improvement of 3–6% on the critical/default class.

~2 hours effortNo RAM dependencyLow risk change
Medium priority
Orchestrator — stateful multi-cycle trigger queue not complete
Agents are currently called directly via endpoints. The trigger queue (MPR_UPLOADED, MILESTONE_DATE_REACHED, CURE_PERIOD_EXPIRED timers) is scaffolded but not active.
Hide ↑
Simplest working implementation:
Use a background thread (or APScheduler) in FastAPI that checks:
1. milestone_dates from rule store vs today → emit MILESTONE_DATE_REACHED
2. cure_deadline from compliance events vs today → emit CURE_PERIOD_EXPIRED
3. FM 7-day notice window vs event date → emit FM_NOTICE_WINDOW_CLOSING

Each trigger calls the appropriate agent sequence. The stateful context (project state assembled fresh each call) is already designed correctly in EL/05.

~1 day effortNo RAM dependency
Phase 2 — Post-RAM unlock (LLM + live tools)
RAM unlocked
Switch extraction from regex → LLM (the core spec requirement)
The regex engine works for the mock contract but will break on real-world contracts with varied phrasing. LLM extraction with few-shot prompts is what makes this generalisable.
Hide ↑
With more RAM, run gemma4:e2b (or switch to Groq API — no local RAM cost at all).

Recommended: Use Groq API (free tier, ~6k tokens/min). No local RAM consumed. Swap extraction_engine.py for the LLM extraction loop from EL/01 spec. Keep regex engine as fallback if API is unavailable.

12-target extraction plan is fully defined in 01_CONTRACT_PARSER.md. Few-shot prompts per target are written. Just need to wire in the API call and JSON parser.

Test with: CONTRACT_EPC_NH44_KA03.docx → compare LLM output vs current regex output field-by-field.

~1 day effortGroq API = no local RAM
RAM unlocked
Weather API + News API — live-connect (scaffolded, not active)
FM validation (C11b IMD cross-check) and risk prediction (weather anomaly score, news signals) are incomplete without live data. This is architecturally important.
Hide ↑
Weather: OpenWeatherMap API (free tier) or IMD open data.
Implement tools/weather_tool.py:
— get_monthly_rainfall(location, month, year)
— compute_anomaly_score(actual_mm, imd_normal_mm, imd_std_mm) → 0.0–1.0
— FM eligibility: score ≥ 0.75 (2 SD above normal)

News: NewsAPI (free tier, 100 req/day).
Implement tools/news_tool.py:
— Search keywords: project location + ["strike", "bandh", "flood", "forest clearance", "steel price", "cement price"]
— Return risk signals as strings → Explainer Agent narrates them

Both tools are already in the Tool Registry spec in EL/05. Just need the API keys and the implementation.

~1 day effortFree API keysNo local RAM needed
RAM unlocked
LLM-powered audience-aware narration in ExplainerAgent
Currently rule-based narrative only. The spec requires 4 distinct audiences: SITE_ENGINEER, PROJECT_MANAGER, CONTRACTOR (formal legal), AUDITOR. This is what makes compliance.md actually useful to each role.
Hide ↑
The Explanation Agent prompt in EL/05 is fully written. Just needs an LLM backend.

Recommend Groq API — no local RAM, fast, free tier sufficient for reports.
Pass: agent_outputs bundle + audience identifier → get audience-specific plain-English report.

Key difference for CONTRACTOR audience: formal legal language, exact ₹ amounts and deadlines, appeal rights always included. For SITE_ENGINEER: simple bullets, immediate actions only.

~0.5 day effortGroq API = no local RAM
RAM unlocked
W&B experiment tracking — not implemented
Needed for model versioning and F1/PR-AUC tracking across training runs. Low effort, high professional value for demonstrating ML rigour.
Hide ↑
pip install wandb
Add 8 lines to agents/risk_predictor.py:

import wandb
wandb.init(project="contractguard", config=MODEL_CONFIG)
wandb.log({"f1": f1, "pr_auc": pr_auc, "precision": precision, "recall": recall})
wandb.log({"feature_importance": dict(zip(feature_names, model.feature_importances_))})

Free tier. No GPU needed. Runs fine on CPU training.

~1 hour effortFree tier
Phase 3 — Dashboard & export polish
Dashboard
S-curve Plotly chart + SHAP waterfall chart — not in dashboard
Both are generated as data but not rendered in Streamlit. These are the most visually compelling outputs of the system.
Hide ↑
S-curve: import plotly.graph_objects as go then st.plotly_chart(fig)
3 traces: planned (dashed gray), actual (blue solid), forecast (orange dashed)
Vertical lines at M1/M2/M3/SCD with annotations
Shaded red zone after 90-day termination threshold

SHAP waterfall: shap.plots.waterfall(shap_values[0]) → st.pyplot()
Or use the SHAP values already in risk_summary.json to build a simple Plotly bar chart (red for risk-increasing features, green for risk-reducing).

Both charts are in Page 1 (Overview) and Page 4 (Risk) of the dashboard spec in EL/06.

~1 day effortNo RAM dependency
Dashboard
PDF export (fpdf2) — compliance.pdf and predictions.pdf not implemented
The download buttons exist but only output .md and .json. The spec requires downloadable PDFs for formal project records usable in disputes and audits.
Hide ↑
pip install fpdf2

Build agents/pdf_exporter.py:
— Read compliance_{id}.md → render as PDF with cover page, NHAI logo placeholder, section headers, tables
— Add signature block (Engineer-in-Charge / Authority's Engineer)
— Version stamp + date in footer
— st.download_button(label="Download PDF", data=pdf_bytes, file_name="compliance.pdf")

The exact PDF structure is in EL/06. Priority: compliance.pdf first (used by auditors and in disputes), then predictions.pdf.

~1.5 days effortNo RAM dependency
Dashboard
Dashboard Pages 3–6 — partially scaffolded, not full spec
Pages 3 (MPR Upload with live validation feedback), 5 (Contractor FM/EoT forms), and 6 (Audit Trail with agent attribution) are the most important gaps.
Hide ↑
Priority order:
1. Page 3 (Site Engineer MPR Upload): file uploader → parse → validate → show per-field ✅/❌ → submit button → triggers /full-analysis
2. Page 5 (Contractor): FM claim form (event date, category, notice text) + EoT application form — submits to new endpoints
3. Page 6 (Auditor): render agent_log entries from DB as a table with agent name, timestamp, tools called, output summary + download buttons

Page 4 (Risk) just needs the Plotly charts wired in (covered above).

~2 days effortNo RAM dependency
Note on Groq API vs local LLM: Most of the "blocked by RAM" items can actually be unblocked right now using the Groq API (free tier, no local memory cost). The LLM extraction, audience-aware narration, and orchestrator routing can all run via API calls. Local RAM matters mainly for running gemma4:e2b alongside sentence-transformers simultaneously — consider GC after embedding stage as you already do, or offload LLM calls to Groq regardless of the RAM upgrade.
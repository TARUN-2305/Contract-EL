# ContractGuard AI — Project Report
> Based on EL Specification Files `EL/00` through `EL/06`  
> Generated: 2026-04-28 | Status: Phases 1–5 Complete

---

## 1. Project Purpose & Philosophy

ContractGuard AI is a **multi-agent compliance system** for Indian public infrastructure contracts. Its core thesis is that contract violations on EPC and Item Rate infrastructure projects are largely deterministic and predictable — the right rules are written into the contracts themselves (NITI Aayog Model EPC Agreement, CPWD GCC 2023, NHAI Works Manual), and a machine can enforce them more consistently than a manual review process.

The system acts as an **always-on compliance layer**, not a replacement for engineers. It reads contract PDFs, watches monthly execution data, enforces rules, predicts risk, and explains every decision in plain language with exact clause citations.

**Two contract types are in scope:**

| Type | Framework | Key Features |
|---|---|---|
| EPC | NITI Aayog Model | 3 interim milestones (28/55/75% SCP), LD 0.05%/day, 10% cap, catch-up refund (Art. 10.3.3), 60-day cure period |
| Item Rate | CPWD GCC 2023 | Monthly absolute targets, LD 1%/month, 7-day show cause notice, Hindrance Register mandatory for EoT |

---

## 2. System Architecture (EL/00)

The spec defines a **3-layer agentic pattern:**

```
Layer 1 — Specialist Agents   (Parser, Compliance, Risk, Penalty, EoT, Escalation, Explainer)
Layer 2 — Orchestrator Agent  (routes triggers, assembles context, sequences agent calls)
Layer 3 — Explanation Agent   (translates all decisions to plain language + clause refs)
```

### 2.1 Data Flow

```
Contract PDF → Parser Agent → Rule Store (JSON + pgvector)
                                    │
MPR Upload → Compliance Engine → Events → Penalty Agent → LD Ledger
                                    │
                              Risk Predictor → Risk Score
                                    │
                              Explainer → compliance.md + predictions.md
                                    │
                              Dashboard (Streamlit, role-gated)
```

### 2.2 Five User Roles

| Role | Real Title | Produces | Consumes |
|---|---|---|---|
| Contract Manager | Engineer-in-Charge | Approved rule store | Extracted clauses, violations |
| Site Engineer | JE / AE | MPR uploads, hindrance entries | NCRs, compliance flags, EoT status |
| Project Manager | SE / Project Director | EoT approvals, VO decisions | Risk dashboard, S-curve, alerts |
| Contractor | Site Contractor | FM claims, EoT applications, test results | Violation notices, LD calculations |
| Auditor | CAG / Authority's Engineer | — (read-only) | Full audit trail, reports, PDFs |

### 2.3 Technology Stack (Specified vs. Built)

| Layer | Specified | Built |
|---|---|---|
| LLM | Groq (claude-3 / llama-3.3) | `gemma4:e2b` via Ollama (RAM constraint) |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 | ✅ Implemented |
| Vector DB | PostgreSQL + pgvector | ✅ Implemented |
| Relational DB | PostgreSQL | ✅ Implemented (4 tables) |
| ML Model | XGBoost + ADASYN | ✅ XGBoost implemented; ADASYN deferred |
| Explainability | SHAP | ✅ SHAP TreeExplainer integrated |
| Backend | FastAPI | ✅ Implemented |
| Frontend | Streamlit (role-gated) | ✅ Implemented (5 roles) |
| PDF Export | fpdf2 | ⚠️ Mock contract only; PDF export from dashboard deferred |
| External Tools | Weather API, News API | ⚠️ Scaffolded; not live-connected |
| Experiment Tracking | Weights & Biases | ⚠️ Not implemented |

---

## 3. Module 01 — Contract Parser (EL/01)

### 3.1 Specification

The parser is the **source of truth** for the entire system. Its job is to extract 12 structured rule targets from a contract PDF and produce a validated `rule_store_{contract_id}.json`.

**Extraction Pipeline (4 stages):**
1. **PDF Preprocessing** — `pdfplumber`/`pypdf` → semantic chunks tagged with `{source_clause, page_number, section_type}`
2. **Embedding + Vector Store** — `all-MiniLM-L6-v2` → 384-dim vectors → `pgvector`
3. **Hierarchical Extraction** — LLM with 12-target extraction plan, top-5 chunks per target, few-shot prompts, JSON output
4. **Rule Store Assembly** — merge all targets → validate → write JSON

**12 Extraction Targets:**
milestones · liquidated_damages · performance_security · quality_assurance · force_majeure · eot_rules · variation_orders · termination · dispute_resolution · bonus · conditions_precedent · payment_workflow

**Validation Rules (post-extraction):**
- LD rate: `0 < x <= 1`
- LD cap: must equal 10% (universal NITI Aayog standard)
- PS submission deadline: must equal 15 days (CPWD Clause 1)
- FM notice deadline: must equal 7 days (NITI Aayog Article 19)
- Any null critical field → flagged `⚠️ UNRESOLVED`, requires Contract Manager review before activation

### 3.2 Implementation Status

**What was built:** Full parser agent in `agents/parser_agent.py` with all 4 stages implemented.

**Key deviation from spec — Deterministic Extraction Engine:**  
The spec requires LLM-based extraction (Stage 3). Due to severe RAM constraints (8GB total system RAM), `gemma4:e2b` and `sentence-transformers` cannot coexist in memory. The LLM extraction loop was **replaced with a deterministic regex engine** (`agents/extraction_engine.py`).

The regex engine covers all 12 targets:
- Milestones: pattern-matched from `Article 10.3.1` blocks with day-number extraction
- LD rates: extracted from `%...per day` patterns
- Performance Security: extracted from `5%...15 days` clause blocks
- FM, EoT, QA: pattern-matched from clause headers

**Known issue fixed:** M4 (Scheduled Completion Date) trigger_day was incorrectly regex-matching M2's day (401 vs. correct 730). Fixed by:
1. `extraction_engine.py`: Validation against max existing milestone day; sets `raw_m4_day = None` if invalid
2. `parser_agent.py`: Patches `M4.trigger_day = scp_days` when extraction returns None

**Rule Store outputs:**
- `data/rule_store/rule_store_{contract_id}.json` — 20 structured keys
- `data/audit/extraction_audit_{contract_id}.json` — which text chunks were used
- `data/audit/unresolved_{contract_id}.json` — null fields for human review

---

## 4. Module 02 — Data & Reporting (EL/02)

### 4.1 Specification

This module defines how real execution data enters the system. The Site Engineer uploads a **structured Markdown MPR file** monthly. The system parses it, validates it, and converts it into a typed execution record.

**MPR Structure (11 Sections):**

| Section | Contents |
|---|---|
| S1 | Project metadata, day number, appointed date |
| S2 | Planned vs actual physical + financial progress |
| S3 | BoQ execution table (item-wise quantities) |
| S4 | Material reconciliation (cement, steel, bitumen) |
| S5 | Labour & machinery deployment (planned vs actual) |
| S6 | QA results (test-wise pass/fail), NCRs, RFIs |
| S7 | Rainfall, working days lost, weather data |
| S8 | RoW handed over, utility shifting status |
| S9 | GFC drawing approval status |
| S10 | RA bill submission and payment status |
| S11 | Site Engineer declaration + co-signature |

**MPR Validation Rules (before ingestion):**
1. Date check — period end must be ≤ today and ≥ previous MPR
2. Monotonicity — actual physical % must be ≥ previous month
3. Labour sanity — actual cannot exceed 150% of planned
4. QA consistency — passed + failed must equal conducted
5. RA bill date — must be after reporting period ends
Failure on any → full rejection with specific error, not partial ingestion.

**Execution Data Schema:** 29 columns including computed fields (`s_curve_deviation_pct`, `milestone_m1_missed`, `ld_pct_of_cap`).

**Hindrance Register:** JSON schema per hindrance entry with 5 categories (AUTHORITY_DEFAULT, FORCE_MAJEURE_WEATHER, FORCE_MAJEURE_POLITICAL, STATUTORY_CLEARANCE, UTILITY_SHIFTING). Overlap-aware EoT computation via interval merging.

**Synthetic Data Generator:** Seeded from real delay probability distributions from MoP Report:
- `row_pending_km > 5`: 72% delay probability
- `gfc_drawings_pending > 10`: 65%
- `labour_utilisation < 70%`: 58%
- `milestone_m1_missed`: 84% chance of further slippage

### 4.2 Implementation Status

The execution data schema is fully consumed by the compliance engine and risk predictor via the `/run-compliance` and `/predict-risk` API endpoints. The MPR `.md` upload parser is scaffolded but the full Section-by-section parser (S3 BoQ tables, S4 material reconciliation) is not yet implemented — the system currently receives `exec_data` as a JSON POST body. The synthetic data generator is implemented in `agents/risk_predictor.py::generate_training_data()`.

---

## 5. Module 03 — Compliance Engine (EL/03)

### 5.1 Specification

The compliance engine is fully deterministic — no LLM. It runs **15 rule checks** per MPR cycle.

| Check | ID | What It Tests | Severity | Clause |
|---|---|---|---|---|
| Performance Security submission | C01 | PS submitted within 15 days of LoA | HIGH | CPWD Clause 1 |
| Performance Security quantum | C02 | PS amount = 5% of contract value | HIGH | CPWD Clause 1 |
| Milestone M1 | C03_M1 | 20% progress by Day 204 | HIGH | Article 10.3.1 |
| Milestone M2 | C03_M2 | 50% progress by Day 401 | HIGH | Article 10.3.1 |
| Milestone M3 | C03_M3 | 75% progress by Day 547 | HIGH | Article 10.3.1 |
| Milestone M4 (SCD) | C03_M4 | 100% progress by Day 730 | CRITICAL | Article 10.3.2 |
| LD cap warning | C04 | LD > 80% of cap | HIGH | Article 10.3.2 |
| LD cap breach | C04b | LD = 100% of cap | CRITICAL | Article 10.3.2 |
| Catch-up refund | C05 | SCD achieved → refund all intermediate LDs | INFO | Article 10.3.3 |
| QA test failures | C07a | Any test failure rate | MEDIUM | Article 11.14 |
| NCR unresolved | C07b | Open NCRs past deadline | MEDIUM/HIGH | CPWD Clause 10A |
| EoT application timeliness | C10 | EoT filed within 14 days of hindrance | MEDIUM | CPWD Clause 5 |
| Force Majeure notice | C11a | FM notice within 7 days | HIGH | Article 19.1 |
| FM weather evidence | C11b | IMD cross-check | MEDIUM | Article 19 |
| Termination threshold | C15 | 90 days beyond SCD net of EoT | CRITICAL | Article 23.1.1(c) |

**LD Calculation Logic:**
```
LD = (ld_rate_pct / 100) × basis_value × delay_days
basis_value = apportioned milestone value (M1/M2/M3) OR total contract price (M4)
Accumulated LD capped at max_cap_inr (10% of contract value)
```

**Catch-up Refund (Article 10.3.3):** If M4 achieved on time, ALL intermediate milestone LDs are reversed. This is an INFO-severity positive event.

### 5.2 Implementation Status

All 15 checks implemented in `agents/compliance_engine.py`. Wrapped by `ComplianceAgent` in `agents/compliance_agent.py`. Exposed via `POST /run-compliance` endpoint.

**End-to-end verified:**
- Day 450 scenario: M2 missed (35% actual vs 50% required)
- LD accrued: Rs. 30,62,500 (49-day delay × Rs. 62,500/day)
- Daily rate correctly computed from apportioned milestone value
- Report persisted to `data/compliance/compliance_{id}_{period}.json`

**Compliance Event Schema (per event):**
```json
{
  "event_id", "check_id", "severity", "status",
  "title", "clause", "description",
  "ld_accrued_inr", "ld_daily_rate_inr",
  "catch_up_refund_eligible",
  "action", "cure_period_days"
}
```

---

## 6. Module 04 — Risk Predictor (EL/04)

### 6.1 Specification

An XGBoost binary classifier predicting: **will this project miss its next milestone or SCD within the next 60 days?**

**25 features across 6 groups:**

| Group | Features | Source |
|---|---|---|
| A — Schedule | s_curve_deviation, milestone miss flags, days_elapsed_pct, progress velocity, required recovery velocity, LD cap %, EoT % | MPR S2, Rule Store |
| B — Resources | skilled/unskilled labour utilisation, machinery idle days | MPR S5 |
| C — Quality | test fail rate, NCRs pending, RFIs pending, GFC drawings pending | MPR S6, S9 |
| D — External | RoW pending %, utility shifting, railway clearance, forest clearance, cumulative rainfall days lost | MPR S7, S8 |
| E — Financial | payment delayed streak, variation order count, FM claim active, expenditure vs physical ratio | MPR S10 |
| F — Live Signals | weather anomaly score (IMD) | Weather tool |

**Model Configuration:**
```
n_estimators: 400 | max_depth: 6 | learning_rate: 0.05
subsample: 0.8 | colsample_bytree: 0.8 | scale_pos_weight: 3
eval_metric: aucpr | Target F1 >= 0.78, Recall >= 0.80
```

**Training Data Strategy:** Synthetic, 6-scenario distribution (~35% positive class). ADASYN for class imbalance.

**Risk Output:**
- `risk_score` (0.0–1.0)
- `risk_label` (LOW / MEDIUM / HIGH / CRITICAL)
- `top_risk_factors` (SHAP values, top 5)
- `time_to_default_estimate_days`

**Thresholds:** CRITICAL ≥ 0.75 | HIGH ≥ 0.55 | MEDIUM ≥ 0.35 | LOW < 0.35

### 6.2 Implementation Status

Fully implemented in `agents/risk_predictor.py`. Trained model serialized to `data/models/risk_predictor.pkl`.

**Training results:** 3000 synthetic samples, 34.9% positive class, model loaded/trained in ~3 seconds on CPU.

**SHAP integration:** `shap.TreeExplainer` used when SHAP is available; falls back to feature importance rankings.

**Heuristic fallback:** Weighted scoring formula when XGBoost unavailable.

**End-to-end verified (Day 450, at-risk scenario):**
- Risk score: **0.9964 (CRITICAL)**
- TTD: **84 days**
- Top SHAP factors: `required_velocity_to_recover` (+1.38), `labour_skilled_utilisation_pct` (+1.35), `s_curve_deviation_pct` (+1.16)

**Gap vs. spec:** ADASYN not implemented (class imbalance handled via `scale_pos_weight=3`). W&B experiment tracking not implemented.

---

## 7. Module 05 — Agent Engine (EL/05)

### 7.1 Specification

The Agent Engine defines the orchestration pattern, all specialist agents, the tool registry, and the escalation state machine.

**Orchestrator Trigger Types:**

| Trigger | Agent Sequence |
|---|---|
| MPR_UPLOADED | Compliance → Penalty → Risk → Explainer |
| FM_CLAIM_SUBMITTED | EoT (FM track) → Compliance → Explainer |
| HINDRANCE_LOGGED | EoT → Explainer |
| MILESTONE_DATE_REACHED | Compliance → Penalty → Escalation → Explainer |
| CURE_PERIOD_EXPIRED | Escalation → Explainer |
| LD_CAP_WARNING | Escalation → Explainer |

**Key design principle:** Each agent is stateless. The Orchestrator assembles full project context and passes it explicitly on every call.

**Specialist Agents (4 defined beyond compliance):**

**Penalty Agent:** Calculates exact LD amount, enforces 10% cap, checks catch-up refund eligibility, updates penalty ledger. Formula: `LD = (rate/100) × basis_value × delay_days`.

**EoT Agent:** Handles two tracks:
- Hindrance-based: 14-day application window, joint Hindrance Register, overlap-aware net days
- FM-based: 7-day notice, 4 required notice elements, IMD cross-check, 180-day termination threshold

**Escalation Agent (State Machine):**

| Contract Type | Step 1 | Step 2 | Step 3 | Step 4 |
|---|---|---|---|---|
| EPC | Notice of Intent (60-day cure) | Termination Notice | Amicable Conciliation (30d) | Arbitration |
| Item Rate | Show Cause (7d) | Contract Determination | SE Appeal (15d file, 30d decision) → DRC (15d file, 90d decision) | Arbitration (30d, missed = DRC final) |

**Tool Registry (8 tools):**
`query_rule_store` · `calculate_ld` · `get_weather` · `get_news` · `check_eot_timeliness` · `calculate_net_eot` · `get_s_curve_deviation` · `lookup_escalation_next_step` · `check_catchup_refund` · `calculate_early_completion_bonus`

### 7.2 Implementation Status

**Orchestrator:** Basic routing implemented in `agents/orchestrator.py`. Trigger queue and full stateful orchestration (sequential multi-agent cycles) are partially implemented — the current system calls agents directly via API endpoints rather than through the Orchestrator's trigger queue.

**Penalty Agent:** Logic embedded in `compliance_engine.py` (LD calculation, cap enforcement, catch-up check). Separate Penalty Agent as LLM wrapper not yet built.

**EoT Agent:** Basic checks (C10 — timeliness, C11a/b — FM validity) implemented in compliance engine. Full EoT decision schema with `eot_decision.json` output not yet built.

**Escalation Agent:** C15 termination threshold check implemented. Full escalation state machine (multi-step notice tracking, timer management) not yet built.

**Tool Registry:** `calculate_ld` and `check_eot_timeliness` implemented. `get_weather` and `get_news` scaffolded but not live-connected.

---

## 8. Module 06 — Explainer & Outputs (EL/06)

### 8.1 Specification

The Explainer is the final layer of every agent cycle. It produces:
- `compliance.md` — human-readable report for all roles
- `predictions.md` — risk narration for Project Manager / Auditor
- PDF exports (`fpdf2`) for formal records
- Streamlit dashboard (6 pages, role-gated)

**Compliance.md Structure:**
1. Header (project, contract type, value, period, day number)
2. Executive Summary table (progress, LD, violations, risk score)
3. Active Compliance Events (per-event: what happened, financial consequence, catch-up note, required action)
4. Penalty Ledger Summary
5. Contractor's Rights section
6. Audit Trail table

**Audience-aware narration:**
- SITE_ENGINEER: Simple language, bullet points, immediate actions
- PROJECT_MANAGER: Executive summary + detailed breakdown + risk context
- CONTRACTOR: Formal legal notice language — exact amounts, exact deadlines, appeal rights
- AUDITOR: Full audit trail, all clause references, all calculations shown

**Dashboard (6 Pages):**
1. Project Overview — progress ring, S-curve, risk badge, violation count
2. Compliance Status — event list, penalty ledger, EoT log
3. MPR Upload (site_engineer) — file upload, validation feedback, hindrance form
4. Risk & Predictions (PM/auditor) — SHAP waterfall, milestone forecast, news/weather panel
5. Notices & Claims (contractor) — received notices, FM/EoT/VO submission forms
6. Audit Trail (auditor) — full event log, agent attribution, PDF downloads

### 8.2 Implementation Status

**ExplainerAgent** implemented in `agents/explainer_agent.py`. Rule-based narrative (no LLM) due to RAM constraints.

**Outputs generated:**
- `data/reports/compliance_{id}_{period}.md` — full structured report
- `data/reports/risk_summary_{id}_{period}.json`

**compliance.md verified output (Day 450 scenario):**
```
6 events | 0 CRITICAL | 3 HIGH
LD Accumulated: Rs. 30.62 L (1.2% of cap)
Risk Score: 0.8866 (CRITICAL)
Top event: [HIGH] [C03_M2] Project Milestone II Missed
           LD: Rs. 30,62,500 | Daily: Rs. 62,500
           Clause: Article 10.3.1
```

**Streamlit Dashboard** implemented in `dashboard.py`:
- Role selector: Contract Manager / Project Manager / Site Engineer / Auditor / Contractor Rep
- Contract Upload panel (Contract Manager only)
- Rule Store overview (milestones table, contract parameters)
- MPR Analysis form (inputs: day, progress %, LD accumulated, labour, QA, RoW, GFC drawings)
- Results: risk metric, compliance event count, LD total, TTD estimate
- Download buttons for compliance.md and risk_summary.json
- Role-specific panels (Auditor trail, Site Engineer field actions, Contractor status)
- Live on `http://localhost:8501`

**Gap vs. spec:** PDF export not implemented. LLM-powered audience-specific narration not implemented (audience detection deferred). S-curve Plotly chart not implemented. SHAP waterfall chart not implemented in dashboard. Pages 3–6 are partially scaffolded.

---

## 9. Financial Logic Summary

The following financial rules from the EL spec are fully implemented and verified:

| Rule | Value | Source Clause | Implementation |
|---|---|---|---|
| LD rate (EPC) | 0.05%/day of milestone value | Article 10.3.1 | ✅ compliance_engine.py |
| LD rate (SCD) | 0.05%/day of total contract price | Article 10.3.2 | ✅ |
| LD cap | 10% of contract value | Article 10.3.2 | ✅ |
| LD cap warning threshold | 80% of cap | Article 10.3.2 | ✅ |
| Catch-up refund | 100% of intermediate LDs | Article 10.3.3 | ✅ |
| PS amount | 5% of contract value | CPWD Clause 1 | ✅ |
| PS deadline | 15 days from LoA | CPWD Clause 1 | ✅ |
| PS late fee | 0.1%/day | CPWD Clause 1 | ✅ |
| FM notice window | 7 days | Article 19.1 | ✅ |
| EoT application window | 14 days | CPWD Clause 5 | ✅ |
| FM termination threshold | 180 days continuous | Article 19 | ✅ |
| Contractor default (SCD) | 90 days net of EoT | Article 23.1.1(c) | ✅ |
| Early completion bonus | 1%/month, max 5% | CPWD Clause 2A | ⚠️ Scaffolded |
| Retention money | 5% of RA bill | CPWD Clause 7 | ⚠️ Not implemented |
| Payment deadline | 30 days from RA bill | CPWD Clause 7 | ⚠️ Not implemented |

---

## 10. API Endpoint Summary

| Endpoint | Method | Input | Output | Status |
|---|---|---|---|---|
| `/upload-contract` | POST | PDF + metadata | rule_store.json | ✅ |
| `/run-compliance` | POST | exec_data JSON | compliance report | ✅ |
| `/predict-risk` | POST | exec_data JSON | risk score + SHAP | ✅ |
| `/full-analysis` | POST | exec_data JSON | compliance + risk + compliance.md | ✅ |
| `/health` | GET | — | status | ✅ |

---

## 11. Gap Analysis — Spec vs. Built

### Fully Implemented ✅
- Rule store extraction (deterministic regex engine)
- All 15 compliance checks
- LD calculation engine with cap enforcement
- Catch-up refund logic
- XGBoost risk predictor (25 features, SHAP)
- ExplainerAgent (narrative + compliance.md)
- Streamlit dashboard (5 roles, analysis form, downloads)
- PostgreSQL + pgvector database (4 tables)
- `/full-analysis` endpoint (end-to-end pipeline)

### Partially Implemented ⚠️
- Orchestrator trigger queue (routing works; stateful multi-cycle not yet)
- EoT Agent (checks in compliance engine; full decision schema not built)
- Escalation Agent (C15 check done; state machine not built)
- Weather/News tool calls (scaffolded; not live-connected)
- Dashboard pages 3–6 (scaffolded; not full spec)

### Not Yet Implemented ❌
- LLM-based extraction (blocked by RAM; regex engine is production substitute)
- PDF export from dashboard (fpdf2 for compliance.pdf, predictions.pdf)
- RA bill / payment workflow tracking (Clause 7)
- MPR `.md` file parser (sections 3–11 table parsing)
- W&B experiment tracking
- ADASYN class balancing (using scale_pos_weight instead)
- S-curve Plotly chart
- SHAP waterfall chart in dashboard
- Item Rate (CPWD GCC) contract type (only EPC implemented)

---

## 12. Known Issues & Technical Decisions

| Issue | Decision |
|---|---|
| 8GB RAM — LLM + embeddings cannot coexist | Deterministic regex extraction; GC after embedding stage |
| M4 trigger_day regex matches wrong day | Validation against max existing milestone day; patched to `scp_days` |
| Mock contract M2/M4 duplicate `trigger_day` | Fixed in extraction engine; existing rule store patched |
| `gemma4:e2b` OOM on extraction | LLM used only for orchestrator routing; extraction fully deterministic |

---

## 13. Verified End-to-End Test Results

**Scenario:** Day 450 of 730 | Actual progress: 35% | Contract value: Rs. 25 Cr

| Check | Result |
|---|---|
| Compliance events generated | 6 total (0 CRITICAL, 3 HIGH) |
| M2 LD accrued | Rs. 30,62,500 (49 days × Rs. 62,500/day) |
| Risk score | 0.8866 — CRITICAL |
| Time to default estimate | 84 days |
| Top SHAP factor | `required_velocity_to_recover` (+1.38) |
| compliance.md generated | `data/reports/compliance_CONTRACT_001_2026-05.md` |
| Dashboard health | HTTP 200 at `localhost:8501` |

---

*Report generated from `EL/00_MASTER_ARCHITECTURE.md` through `EL/06_EXPLAINER_AND_OUTPUTS.md` cross-referenced with implemented code in `agents/`, `api/`, and `dashboard.py`.*

---

## 14. Addendum: Phase 6, 7 & 8 Updates (Final Implementation)

The following components were successfully implemented to complete the ContractGuard AI Engine, resolving the gaps identified in Section 11:

### A. Core Architecture & Infrastructure
- **Groq API Orchestration**: Integrated `utils/groq_client.py` for heavy LLM inference (`llama-3.3-70b-versatile`), overcoming local RAM constraints. Implemented round-robin API key rotation.
- **MPR Parser Engine**: Built `agents/mpr_parser.py` capable of fully extracting and validating all 11 sections of the EL/02 MPR format. Exposed via `POST /upload-mpr` endpoint.
- **Background Jobs**: Integrated `APScheduler` into `api/main.py` for continuous, automated tracking of expired cure periods and escalations.

### B. Agentic State Machines & Compliance
- **Item Rate Contracts**: Added full CPWD GCC logic to `compliance_engine.py` (1% monthly LD, 7-Day Show Cause pathways).
- **Payment Pathways**: Implemented C13a-c checks for >30-day delays, retention tracking, and mobilization recovery.
- **EoT Agent (`eot_agent.py`)**: Calculates *net eligible EoT* by automatically identifying and merging overlapping hindrance windows.
- **Escalation Agent (`escalation_agent.py`)**: Operates a definitive State Machine supporting EPC (60-day cure) and Item Rate (7-day show cause) paths. Employs Groq to draft precise legal notices based on contract state.

### C. Predictive Risk & Intelligence
- **SMOTE Class Balancing**: Swapped ADASYN for `SMOTE` (`imblearn.over_sampling`) within `agents/risk_predictor.py`, successfully retraining the XGBoost model to stabilize the 35% synthetic default rate.
- **News Tool (`tools/news_tool.py`)**: Connects to NewsAPI to mine public media for insolvency, NCLT, and strike signals against the contractor entity.
- **Weather Tool (`tools/weather_tool.py`)**: Calculates historical rainfall anomaly scores to statistically validate or reject Force Majeure claims.

### D. Dashboard Polish & Outputs
- **Audience-Aware Explainer**: Enhanced `agents/explainer_agent.py` to request persona-specific executive summaries (e.g., tailored for "Auditor" vs. "Site Engineer") from the Groq LLM.
- **PDF Generation (`pdf_exporter.py`)**: Replaced the missing PDF requirement by wrapping `fpdf2` to automatically format and output `.md` compliance reports into professional PDF documents.
- **Interactive Visualizations**: 
  - **S-Curve Chart**: Integrated Plotly to graph Planned vs. Actual progress based on `scp_days`.
  - **SHAP Feature Impact**: Integrated Plotly bar charts visualizing the top XGBoost risk drivers.
- **Role-Gated Dashboard**: Finished Streamlit UI implementation covering Contract Manager, Project Manager, Auditor, Site Engineer, and Contractor Rep, with explicit download logic for `.md`, `.json`, and `.pdf` artifacts.

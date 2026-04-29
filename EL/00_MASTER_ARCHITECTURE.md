# ContractGuard AI — Master Architecture
> Intelligent Infrastructure Contract Compliance System  
> Contract Types in Scope: **EPC (NITI Aayog Model)** + **Item Rate (CPWD GCC 2023)**  
> Agentic Pattern: **Multi-Agent + LLM Orchestrator + Tool-Calling**

---

## System Philosophy

ContractGuard AI is a **multi-agent compliance system** for Indian public infrastructure contracts. It does not replace engineers — it acts as an always-on compliance layer that reads contracts, watches project execution, enforces rules derived from real legal frameworks (NITI Aayog EPC, CPWD GCC 2023, NHAI Works Manual), and explains every decision in plain language.

The system follows a **3-layer agentic pattern**:

```
Layer 1: Specialist Agents     — each owns a domain (contracts, compliance, risk, payments)
Layer 2: Orchestrator Agent    — routes, coordinates, decides which agent to call next
Layer 3: Explanation Agent     — translates every agent output into human-readable form
```

---

## The Five Users and Their Roles

| Role | Real-World Title | What They Do in the System | Data They Produce | Data They Consume |
|---|---|---|---|---|
| **Contract Manager** | Engineer-in-Charge (EiC) / Divisional Engineer | Uploads the contract PDF. Reviews extracted rules. Approves the rule store. Sets project baseline. | Approved contract rule store | Extracted clauses, violation summaries |
| **Site Engineer** | Junior Engineer (JE) / Assistant Engineer (AE) | Uploads the Monthly Progress Report (MD). Logs hindrances. Submits RA Bill triggers. | MPR uploads, Hindrance Register entries | NCRs, compliance flags, EoT status |
| **Project Manager** | Superintending Engineer (SE) / Project Director | Monitors all active projects. Reviews risk scores. Approves or rejects EoT and variation orders. | EoT approvals, variation decisions | Risk dashboard, S-curve, agent alerts |
| **Contractor** | Site Contractor / Concessionaire | Views their own compliance status. Receives violation notices. Submits FM claims and EoT requests. | FM claims, EoT applications, quality test results | Violation reports, LD calculations, agent notices |
| **Auditor** | CAG / Internal Audit / Authority's Engineer | Read-only access to everything. Downloads compliance reports. Reviews penalty history. | — | Full audit trail, compliance.md, predictions.md |

---

## High-Level Data Flow

```
CONTRACT PDF (uploaded by Contract Manager)
        │
        ▼
┌─────────────────────────────────┐
│  MODULE 1: CONTRACT PARSER      │  ← Hierarchical RAG + LLM + Tools
│  Extracts: Milestones, LD rates,│
│  Performance Security, QA rules,│
│  Conditions Precedent, FM clause│
└────────────┬────────────────────┘
             │ rule_store.json
             ▼
      [Vector DB — pgvector]  ←──────── used by all downstream agents
             │
┌────────────┴──────────────────────────────────────────────┐
│                                                            │
▼                                                            ▼
┌──────────────────────┐              ┌──────────────────────────────┐
│  MODULE 2: DATA GEN  │              │  MODULE 3: COMPLIANCE ENGINE  │
│  Synthetic execution │──────────────│  Checks MPR uploads against   │
│  OR MPR uploads (MD) │  exec_data   │  rule store. Detects: delay,  │
│  by Site Engineer    │              │  LD breach, QA failure, FM    │
└──────────────────────┘              │  validity, EoT eligibility    │
                                      └──────────┬───────────────────┘
                                                 │ compliance_events.json
                                      ┌──────────┴───────────────────┐
                                      │                               │
                                      ▼                               ▼
                          ┌────────────────────┐      ┌─────────────────────────┐
                          │ MODULE 4: RISK      │      │ MODULE 5: AGENT ENGINE  │
                          │ PREDICTOR           │      │ Orchestrator decides:   │
                          │ XGBoost on features │      │ - Issue NCR             │
                          │ derived from real   │      │ - Deduct LD             │
                          │ contract indicators │      │ - Grant EoT             │
                          │ + weather/news tools│      │ - Escalate to DRC       │
                          └────────┬───────────┘      │ - Issue termination     │
                                   │ risk_scores       │   notice                │
                                   └──────┬────────────┘
                                          │
                                          ▼
                               ┌───────────────────────┐
                               │ MODULE 6: EXPLAINER    │
                               │ LLM converts every     │
                               │ decision into plain    │
                               │ English + clause refs  │
                               └───────────┬────────────┘
                                           │
                         ┌─────────────────┴──────────────────┐
                         │                                      │
                         ▼                                      ▼
                  compliance.md                        predictions.md
                  (per project)                        (per project)
                  → Dashboard                          → Dashboard
                  → Downloadable PDF                   → Downloadable PDF
                  → Used by Agents                     → Used by Agents
```

---

## Agentic Architecture Detail

### Orchestrator Agent
- Receives triggers: new MPR upload, new FM claim, LD cap approaching, milestone date
- Decides which specialist agent(s) to invoke
- Maintains conversation memory per project (full state passed each time)
- Uses tool-calling to query the rule store, pull weather data, fetch news

### Specialist Agents (each is an LLM + tools)

| Agent | Trigger | Tools Available | Output |
|---|---|---|---|
| **Parser Agent** | Contract PDF uploaded | PDF reader, chunker, pgvector writer | rule_store.json |
| **Compliance Agent** | MPR uploaded | Rule store query, LD calculator, date arithmetic | compliance_events.json |
| **Risk Agent** | After every MPR | XGBoost model, weather API, news API, S-curve calculator | risk_scores.json |
| **Penalty Agent** | Compliance event created | LD rate lookup, catch-up refund checker, payment deduction calculator | penalty_ledger.json |
| **EoT Agent** | FM claim or hindrance submitted | Hindrance Register reader, FM validator (weather API), overlap calculator | eot_decision.json |
| **Escalation Agent** | Notice not cured within window | Escalation matrix lookup, timer tracker | escalation_status.json |
| **Explanation Agent** | Any agent produces output | LLM (Groq), clause reference DB | Plain English report |

### Tool Registry (available to all agents)
- `query_rule_store(project_id, clause_type)` — pgvector semantic search
- `calculate_ld(contract_value, daily_rate, delay_days, cap_pct)` — deterministic math
- `get_weather(location, date_range)` — IMD/weather API for FM validation
- `get_news(keywords, date_range)` — for force majeure and external risk signals
- `get_s_curve_deviation(planned_pct, actual_pct, elapsed_pct)` — risk feature
- `check_eot_eligibility(hindrance_entries)` — overlap-aware EoT calculator
- `lookup_escalation_next_step(current_tier, days_elapsed)` — dispute matrix

---

## Databases

| Store | Technology | What it holds |
|---|---|---|
| **Vector DB** | PostgreSQL + pgvector | Contract clause embeddings, semantic search |
| **Relational DB** | PostgreSQL | Projects, users, milestones, execution logs, penalty ledger |
| **Rule Store** | JSON files (per contract) | Structured extracted rules: milestones, LD rates, QA thresholds |
| **Event Store** | PostgreSQL | All compliance events, agent decisions, audit trail |

---

## File Outputs Per Project

| File | Produced By | Consumed By |
|---|---|---|
| `rule_store_{contract_id}.json` | Parser Agent | All agents |
| `execution_data_{project_id}.csv` | Site Engineer upload / Data Gen | Compliance Agent, Risk Agent |
| `compliance_events_{project_id}.json` | Compliance Agent | Penalty Agent, Escalation Agent, Explainer |
| `risk_scores_{project_id}.json` | Risk Agent | Dashboard, Orchestrator |
| `penalty_ledger_{project_id}.json` | Penalty Agent | Dashboard, Auditor, Contractor |
| `eot_decisions_{project_id}.json` | EoT Agent | Dashboard, Compliance Agent |
| `compliance_{project_id}.md` | Explainer Agent | Dashboard, PDF export, Auditor |
| `predictions_{project_id}.md` | Risk + Explainer Agent | Dashboard, PDF export, Project Manager |

---

## Contract Types in Scope

### Type 1: EPC (NITI Aayog Model)
- 3 interim milestones at 28%, 55%, 75% of Scheduled Construction Period
- LD: 0.05% of contract value per day, capped at 10%
- Catch-up refund clause (Article 10.3.3)
- 60-day cure period for defaults (Article 23)
- FM procedure: 7-day notice, IMD proof, weekly updates (Article 19)

### Type 2: Item Rate (CPWD GCC 2023)
- Milestones based on absolute monthly targets
- LD: 1% per month (daily basis), capped at 10% of tendered value (Clause 2)
- 7-day show cause notice for defaults (Clause 3)
- Hindrance Register mandatory for EoT (Clause 5)
- Early completion bonus: 1%/month up to 5% cap (Clause 2A, if activated)

---

## Technology Stack

| Layer | Technology |
|---|---|
| LLM | Groq (claude-3 / llama-3.3) |
| Embeddings | sentence-transformers |
| Vector DB | PostgreSQL + pgvector |
| Relational DB | PostgreSQL |
| ML Model | XGBoost + ADASYN (imbalanced classes) |
| Explainability | SHAP |
| Experiment Tracking | Weights & Biases |
| Backend | Python (FastAPI) |
| Frontend | Streamlit (multi-page, role-gated) |
| PDF Generation | fpdf2 |
| External Tools | Weather API (OpenWeatherMap / IMD), News API |
| Env Management | python-dotenv |

---

## Module Index

| # | File | Purpose |
|---|---|---|
| 01 | `01_contract_parser.md` | RAG pipeline, rule extraction, mock contract spec |
| 02 | `02_data_and_reporting.md` | MPR template, execution data schema, Hindrance Register |
| 03 | `03_compliance_engine.md` | Violation detection logic, all rule types, EoT/FM handling |
| 04 | `04_risk_predictor.md` | ML features, model spec, prediction output |
| 05 | `05_agent_engine.md` | Orchestrator, all specialist agents, escalation matrix |
| 06 | `06_explainer_and_outputs.md` | LLM explanation, compliance.md, predictions.md, dashboard |

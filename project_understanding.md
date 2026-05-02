# ContractGuard AI: Project Understanding

## 1. Project Overview & Philosophy
ContractGuard AI is a multi-agent system designed to act as an always-on compliance layer for Indian public infrastructure projects (specifically EPC and Item Rate contracts). Its core premise is that contract violations, LD (Liquidated Damages) calculations, and risk metrics are largely deterministic and predictable. 

By reading contract documents (PDF/DOCX) and processing Monthly Progress Reports (MPRs), the system can enforce rules, predict project failure risks, and explain every decision in plain language with exact clause citations to five target personas: Contract Manager, Site Engineer, Project Manager, Contractor Rep, and Auditor.

## 2. Core Architecture & Modules
The architecture follows a 3-layer agentic pattern:
- **Layer 1 (Specialists):** Parser, Compliance, Risk, Penalty, EoT, Escalation, Explainer.
- **Layer 2 (Orchestrator):** Routes triggers and sequences specialist agent calls.
- **Layer 3 (Explainer):** Translates decisions to human-readable narratives.

### 2.1 Module 01: Contract Parser (`agents/parser_agent.py`, `agents/extraction_engine.py`)
- **Responsibility:** Extracts 12 structured rule targets (milestones, LD caps, Performance Security rules, Force Majeure notice windows, etc.) from contract documents into a JSON `rule_store`.
- **Implementation:** Due to local RAM constraints, the primary extraction pipeline is a deterministic regex engine (`extraction_engine.py`) that successfully handles complex table layouts. A secondary Groq LLM fallback acts as Stage 4b to resolve missing or ambiguous fields via semantic search.

### 2.2 Module 02: Data & Reporting (`agents/mpr_parser.py`)
- **Responsibility:** Parses execution data from uploaded Markdown (`.md`) or DOCX Monthly Progress Reports (MPRs).
- **Implementation:** Extracts structured data across 11 sections (e.g., actual vs. planned progress, Quality Assurance pass/fail rates, labour deployment, hindrances). Validates the data (e.g., monotonicity checks) before propagating it into the main execution payload.

### 2.3 Module 03: Compliance Engine (`agents/compliance_engine.py`)
- **Responsibility:** Runs 15 fully deterministic rule checks on the MPR execution data.
- **Implementation:** Handles sophisticated logic such as:
  - Multi-milestone Liquidated Damages (LD) calculation.
  - Enforcing the 10% LD Cap limit.
  - Tracking 15-day Performance Security submission deadlines.
  - Evaluating 7-day Force Majeure notice windows.
  - Calculating Catch-up refunds (Article 10.3.3) if the final milestone is reached on time despite intermediate delays.
  - Handles Item Rate CPWD GCC logic (1% monthly LD, 7-day show cause).

### 2.4 Module 04: Risk Predictor (`agents/risk_predictor.py`)
- **Responsibility:** Predicts whether a project will miss its next milestone or Scheduled Completion Date (SCD) within the next 60 days.
- **Implementation:** Utilizes an XGBoost binary classifier using 25 features across Schedule, Resources, Quality, External factors, Financials, and Live Signals. Trained on synthetic data balanced via `SMOTE`. Uses `shap.TreeExplainer` to provide explainability (identifying the top risk drivers). Integrated with Weights & Biases (W&B) for experiment tracking.

### 2.5 Module 05: Agent Engine (`agents/orchestrator.py`, `agents/eot_agent.py`, `agents/escalation_agent.py`)
- **Orchestrator:** Routes API triggers (e.g., `MPR_UPLOADED`, `FM_CLAIM_SUBMITTED`) to the correct sequence of agents.
- **EoT Agent:** Manages Extension of Time logic. Critically handles overlapping hindrance windows to calculate *net eligible EoT* days rather than gross days.
- **Escalation Agent:** A definitive State Machine tracking legal notice pathways (e.g., Notice of Intent -> Termination -> Arbitration). Persists its state to PostgreSQL (`EscalationEvent` table).

### 2.6 Module 06: Explainer & Outputs (`agents/explainer_agent.py`, `dashboard.py`)
- **Explainer Agent:** Synthesizes the outputs of the compliance engine and risk predictor into a highly structured `compliance.md` report. Utilizes Groq to tailor the executive summary for the specific audience persona.
- **Dashboard:** A role-gated Streamlit application serving as the primary frontend. Provides S-Curve progress visualizations, SHAP risk factor bar charts, file upload handling, and interactive forms for the Contractor Rep to submit FM/EoT claims.
- **PDF Export:** Wraps `fpdf2` to seamlessly convert Markdown compliance reports into professional PDF documents.

## 3. Tech Stack
- **Backend Framework:** FastAPI (`api/main.py`)
- **Database:** PostgreSQL + `pgvector` accessed via SQLAlchemy ORM.
- **Frontend:** Streamlit
- **Machine Learning:** XGBoost, SHAP, Imbalanced-learn (`SMOTE`)
- **LLM Integration:** Groq API (`llama-3.3-70b-versatile`) with key rotation (`utils/groq_client.py`).
- **Task Scheduling:** `APScheduler` (used for daily background checks of expired escalation tiers).

## 4. Current State & Recent Developments
The codebase has successfully transitioned from Phase 1-5 specifications into full implementation (Phases 6-8). Key recent milestones include:
1. Completing the end-to-end `POST /upload-mpr` pipeline that chains document parsing, compliance evaluation, risk prediction, and explanation into a single flow.
2. Hardening the Escalation Agent state machine by writing its state to a Postgres table (`escalation_events`) and running an `APScheduler` daily cron job to automatically advance expired notice tiers.
3. Perfecting the `mpr_parser.py` and `extraction_engine.py` to overcome initial layout-parsing bugs (such as capturing table headers instead of values for milestones, and handling overlapping hindrance EoT claims).
4. Activating Groq inference for dynamic content generation while maintaining fallback deterministic parsers due to environmental memory constraints.

The system is highly operational, with all APIs responding, models trained, and the database schema fully synchronized with application requirements.

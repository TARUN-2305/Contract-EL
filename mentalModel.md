# ContractGuard AI v2 — Mental Model

## Project Intent & Purpose
ContractGuard AI v2 is an intelligent compliance and risk monitoring system specifically designed for Indian public infrastructure contracts (EPC and CPWD GCC 2023). It automates the analysis of contracts and Monthly Progress Reports (MPRs) to identify compliance failures, predict project risks, and generate actionable insights for various stakeholders (Project Managers, Auditors, Contractors).

## Core Architecture

### Backend (FastAPI + Python)
- **API Layer (`backend/api/main.py`)**: Entry point for all requests. Handles file uploads (contracts, MPRs), CRUD for projects, and manual triggers.
- **Orchestration Layer (`backend/agents/orchestrator.py`, `backend/agents/pipeline_graph.py`)**: Uses a LangGraph-inspired state management approach to coordinate specialized agents.
- **Agent Layer (`backend/agents/`)**:
    - `compliance_engine.py`: Contains 15+ deterministic compliance checks (Performance Security, ROW, Milestone tracking, etc.).
    - `risk_predictor.py`: Uses XGBoost/LLM to predict risk scores and labels.
    - `explainer_agent.py`: Narrates findings for different audiences.
    - `eot_agent.py`: Specialized logic for Extension of Time (EoT) and Force Majeure (FM) claims.
    - `escalation_agent.py`: Manages the lifecycle of contract escalations.
    - `parser_agent.py` & `mpr_parser.py`: Handles structured data extraction from documents.
    - `llm_auto_extract.py`: LLM-powered field extraction for pre-filling forms.
- **Data Layer (`backend/db/`)**:
    - `models.py`: SQLAlchemy models for Users, Projects, MPRs, RuleStores, ComplianceEvents, and Escalations.
    - `database.py`: Session management.
    - `qdrant_store.py`: Vector database integration for clause retrieval.
- **Async Processing (`backend/workers/tasks.py`)**: Celery tasks for long-running operations like full contract parsing and MPR pipeline execution.

### Frontend (React + Vite)
- **Routing (`frontend/src/App.jsx`)**: Defines pages for Dashboard, Analysis, History, Escalations, and Admin.
- **State Management (`frontend/src/context/AppContext.jsx`)**: Global app state.
- **Components (`frontend/src/components/`)**: Shared UI elements like Sidebar and Dashboard widgets.

## Data Flow
1. **Onboarding**: User uploads a contract -> `ParserAgent` extracts key clauses and parameters -> Saved to `RuleStore`.
2. **Monitoring**: Monthly Progress Report (MPR) is uploaded -> `mpr_parser` extracts execution data -> `PipelineGraph` runs (Compliance -> Risk -> Explainer) -> Results stored in `MPRRecord` and `ComplianceEvent`.
3. **Action**: Stakeholders view the Dashboard (S-curves, Risk Scores) -> Drill down into `AnalysisPage` -> Manage `Escalations`.

## Key Technologies
- **LLM**: Groq (Llama 3.3/3.1) with Ollama (Gemma/Phi) as a local fallback.
- **Vector DB**: Qdrant for RAG-based clause lookup.
- **Job Queue**: Celery with Redis.
- **Database**: PostgreSQL (Relational + Audit).
- **Styling**: Vanilla CSS (based on project structure).

## File Map (Quick Reference)
- `backend/api/main.py`: Main API routes.
- `backend/agents/compliance_engine.py`: Core compliance logic.
- `backend/agents/pipeline_graph.py`: MPR analysis workflow definition.
- `backend/db/models.py`: Database schema.
- `frontend/src/pages/`: UI Page implementations.
- `backend/data/`: Local storage for reports and rule stores.

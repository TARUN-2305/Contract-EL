# Technical Completion Report: ContractGuard AI v2

## Project Overview
ContractGuard AI v2 is a specialized Enterprise Resource Planning (ERP) and Compliance Monitoring system designed for the Indian infrastructure sector. It digitizes physical contracts (PDF/DOCX) into a queryable **Rule Store** and cross-references them with Monthly Progress Reports (MPRs) to automate penalty accruals (Liquidated Damages), detect project slippage using Machine Learning, and verify Force Majeure claims via external environmental APIs.

---

## 1. System Architecture: Full-Stack Data Flow

### 1.1. Backend Infrastructure (FastAPI & PostgreSQL)
*   **Asynchronous Processing:** The backend is built on **FastAPI**, leveraging `asyncio` for non-blocking I/O operations, particularly during external API calls (Ollama, Weather, News).
*   **Relational Schema:** PostgreSQL 15 stores the system of record.
    *   `projects` table: Master metadata (Project ID, Value, SCD).
    *   `mpr_records` table: Time-series data of physical and financial progress.
    *   `clause_embeddings` table: High-dimensional vectors linked back to contract clause IDs for RAG (Retrieval-Augmented Generation).
*   **Task Orchestration:** **Celery 5.6** handles long-running tasks. When a contract is uploaded, a Celery worker is spawned to perform OCR/parsing, preventing API timeout. **Redis 7** acts as the transient message broker.

### 1.2. Frontend Infrastructure (React & Vite)
*   **Build Tooling:** **Vite 8** provides a Lightning-fast HMR (Hot Module Replacement) during development.
*   **Navigation:** `react-router-dom` v7 manages role-gated routing.
*   **Component Architecture:** Atomic design principles are used for UI components (e.g., `ComplianceEventCard` is a standalone functional component).
*   **API Client:** **Axios** with centralized interceptors for timeout management (300s for LLM extractions).

---

## 2. Core Agentic Pipeline: The LangGraph State Machine

The system follows a directed acyclic graph (DAG) pattern to process data:

### 2.1. Parser Agent (Ingestion Phase)
*   **OCR & Transformation:** Utilizes `pdfplumber` and `python-docx` to convert binary documents into clean Markdown.
*   **Dual-Extraction Strategy:**
    1.  **Regex Track:** Deterministic extraction of Agreement Number, Dates, and Numerical Values (Values, Percentages).
    2.  **LLM Track:** Uses `gemma4:e2b` (via Ollama) to extract complex "Trigger Clauses" (e.g., "What constitutes a default?").
*   **Vectorization:** Each clause is chunked and vectorized using the `nomic-embed-text` model. These vectors are stored in **Qdrant** with a payload containing the raw clause text.

### 2.2. Compliance Engine (The Deterministic Core)
*   **Execution Loop:** Iterates through 15+ "Checks" (Class-based logic).
*   **Check C02 (Appointed Date):** Verifies if `appointed_date` exists in Rule Store; triggers an alert if the project clock hasn't started.
*   **Check C06 (Resource Deployment):** Compares `labour_skilled_actual` vs `labour_skilled_planned`. Triggers a "Machinery Under-Deployment" event if the ratio is < 0.25.
*   **Check C10 (Monotonicity):** Backend logic: `assert record.actual_pct >= prev_record.actual_pct`.

### 2.3. Risk Predictor (XGBoost Classifier)
*   **Training Data:** Synthetically generated project lifecycle data (10,000+ samples).
*   **Feature Engineering:**
    *   `velocity_delta`: `(Current_Vel - 3_Month_Avg_Vel)`.
    *   `ld_exposure`: `Current_LD / Contract_Value`.
*   **Inference:** The model returns a probability (0.0 to 1.0) and a label (LOW, MEDIUM, HIGH, CRITICAL).
*   **SHAP Integration:** The `shap` library calculates the "Force" of each feature on the final score, identifying the "Primary Culprit" for high-risk flags.

---

## 3. External Intelligence & Integration Specifications

### 3.1. Weather Verification Tooling
*   **Endpoint:** Open-Meteo Historical Archive API.
*   **Request Payload:** `latitude`, `longitude`, `start_date`, `end_date`, `daily=precipitation_sum`.
*   **Verification Logic:** If a contractor claims a "Flood" delay on `2025-08-15`, the tool fetches the actual rainfall for that coordinate. If `rainfall_mm < 50mm`, the claim is flagged as "Potentially Invalid/Insufficient Evidence."

### 3.2. News & Adverse Signal Tooling
*   **Endpoint:** GNews API v4.
*   **Query Strategy:** `(Contractor_Name) AND (Default OR Bankruptcy OR Litigation OR Debarred)`.
*   **Signal Processing:** Articles are scored for "Sentiment" and "Relevance." A high-relevance adverse signal adds a +0.1 penalty to the XGBoost Risk Score.

### 3.3. LLM Fallback Architecture
*   **Routing:** `utils/llm_client.py` implements a retry-and-fallback wrapper.
*   **Chain:** `Groq (Llama 3.3)` -> `Ollama (Gemma 2)` -> `Ollama (Phi 3)`.
*   **Failure Handling:** If the primary cloud LLM exceeds rate limits (TPM/RPM), the system automatically re-routes the JSON extraction request to the local Ollama instance.

---

## 4. Key Technical Features & Math Logic

### 4.1. S-Curve & Velocity Mathematics
*   **Planned Velocity ($V_p$):** $V_p = \frac{Planned\_Physical\_Pct}{Elapsed\_Days}$
*   **Actual Velocity ($V_a$):** $V_a = \frac{Actual\_Physical\_Pct}{Elapsed\_Days}$
*   **Recovery Velocity ($V_r$):** $V_r = \frac{100 - Actual\_Physical\_Pct}{SCD\_Date - Current\_Date}$
*   **Alert Trigger:** If $V_r > 2 \times V_a$, the system issues a "Physical Impossibility" warning.

### 4.2. LD (Liquidated Damages) Accumulation
*   **Per-Day Penalty:** Defined as 0.05% of the Contract Price for each day of delay.
*   **Cap Management:** Logic ensures $\sum LD \leq 0.1 \times Contract\_Price$.
*   **Catch-up Refund:** Implements EPC Art. 10.3.3 logic where if a contractor misses M1 but recovers M2, the M1 penalties are "Held in Suspense" or refunded.

### 4.3. Docker Network & Volume Isolation
*   **Network:** All containers reside on a custom bridge network (`contractguard_default`).
*   **Volumes:**
    *   `./backend:/app`: Live code sync for Python logic.
    *   `./frontend:/app`: Live code sync for React/Vite logic.
    *   `postgres_data`, `qdrant_data`, `ollama_data`: Persistent named volumes for database integrity across container restarts.

---

## 5. Deployment & Runtime Verification

*   **Port Mapping:**
    *   `5173`: React Frontend (Vite Dev Server).
    *   `8000`: FastAPI (Uvicorn).
    *   `5432`: PostgreSQL.
    *   `11434`: Ollama (Local Inference).
*   **Health Checks:**
    *   PostgreSQL: `pg_isready` check ensures DB is UP before API starts.
    *   Redis: `redis-cli ping` ensures broker is ready before Worker starts.
*   **Automated Initialization:** `api/main.py` startup event triggers `Base.metadata.create_all(bind=engine)`, ensuring the schema is always current with `db/models.py`.

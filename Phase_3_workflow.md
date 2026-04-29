# Phase 3: Data Ingestion + Compliance Engine

## Objective
Build the MPR upload pipeline (Module 02) and the deterministic Compliance Engine (Module 03) — the legal brain of ContractGuard AI.

## Execution Steps

### Part A — MPR Upload Pipeline (Module 02)

1. **MPR Parser:** Build `modules/mpr_parser.py` implementing `parse_mpr()` as defined in `02_DATA_AND_REPORTING.md`:
   - Parse the structured Markdown MPR using regex + markdown table parsing.
   - Extract all fields into the typed execution record schema.
   - Compute derived fields: `s_curve_deviation_pct`, `labour_utilisation_pct`, `test_fail_rate_pct`.

2. **Validation Engine:** Implement the 5 validation rules from `02_DATA_AND_REPORTING.md`:
   - Date monotonicity, labour sanity, QA consistency, RA bill date check.
   - Rejected MPRs return specific error messages — no partial ingestion.

3. **Hindrance Register:** Build `modules/hindrance_register.py`:
   - CRUD operations for hindrance entries (JSON schema from `02_DATA_AND_REPORTING.md`).
   - Overlap deduction logic: `calculate_net_eot()` with interval merging.

4. **Execution Data Store:** Write parsed MPR rows to `execution_data_{project_id}.csv` and persist to DB.

5. **Synthetic Data Generator:** Build `scripts/generate_synthetic_data.py` using the `DELAY_PROBABILITY_SEEDS` from `02_DATA_AND_REPORTING.md` for testing and ML training.

6. **FastAPI Endpoints:** Add `POST /upload-mpr` and `POST /hindrance`.

### Part B — Compliance Engine (Module 03)

7. **Compliance Engine Core:** Build `modules/compliance_engine.py` with all 15 deterministic checks from `03_COMPLIANCE_ENGINE.md`:
   - CHECK 01: Performance Security
   - CHECK 03: Milestone progress + LD calculation
   - CHECK 04: LD cap proximity
   - CHECK 05: Catch-up refund (EPC only)
   - CHECK 07: Quality NCR status
   - CHECK 10: EoT application timeliness (14-day rule)
   - CHECK 11: Force Majeure validity (with weather tool)
   - CHECK 15: Termination threshold proximity
   - All other checks (02, 06, 08, 09, 12, 13, 14).

8. **Compliance Event Schema:** Implement the `ComplianceEvent` dataclass with all fields (severity, clause, financial_impact, action, cure_period).

9. **LD Ledger:** Build `modules/penalty_ledger.py` — per-project running LD total with cap enforcement.

10. **Wire to Orchestrator:** Register Compliance Agent so `MPR_UPLOADED` triggers invoke it after parsing.

## Verification
- Upload a sample MPR → verify parsed execution record matches expected schema.
- Run compliance checks against mock rule store → verify correct events are generated.
- Verify LD calculations match the formulas in `03_COMPLIANCE_ENGINE.md`.

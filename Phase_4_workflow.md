# Phase 4: Risk Predictor + Specialist Agents

## Objective
Build the XGBoost Risk Predictor (Module 04) and all remaining specialist agents from Module 05 (Penalty, EoT, Escalation).

## Execution Steps

### Part A — Risk Predictor (Module 04)

1. **Feature Engineering:** Build `modules/risk_features.py` implementing all 6 feature groups from `04_RISK_PREDICTOR.md`:
   - Group A: Schedule & Progress (s_curve_deviation, milestone_missed, velocity).
   - Group B: Resource Deployment (labour utilisation, machinery idle days).
   - Group C: Quality & Technical (test_fail_rate, ncrs_pending, gfc_pending).
   - Group D: External & Statutory (row_pending, utility/forest/railway clearance).
   - Group E: Financial & Contractual (payment_delayed_streak, variation_claims).
   - Group F: Live External Signals (weather_anomaly_score via `get_weather()` tool, news via `get_news()` tool).

2. **Training Pipeline:** Build `scripts/train_risk_model.py`:
   - Use synthetic data from Phase 3's generator with the scenario distribution from `04_RISK_PREDICTOR.md`.
   - Apply ADASYN for class imbalance.
   - Train XGBoost with `MODEL_CONFIG` from the spec.
   - SHAP explainer for top-5 feature contributions per prediction.
   - Target: F1 >= 0.78, Recall >= 0.80.

3. **Risk Scoring:** Build `modules/risk_scorer.py`:
   - Accepts execution data → produces `risk_scores_{project_id}.json` with the full schema from `04_RISK_PREDICTOR.md`.
   - Includes `time_to_default_estimate`, `recovery_feasibility`, and `recommendations`.

4. **S-Curve Visualisation:** Build `modules/scurve_chart.py` using Plotly — planned vs actual vs forecast with milestone markers.

### Part B — Specialist Agents (Module 05)

5. **Penalty Agent:** Build `agents/penalty_agent.py`:
   - Implements `PENALTY_AGENT_PROMPT` from `05_AGENT_ENGINE.md`.
   - Tool calls: `calculate_ld()`, `check_catchup_refund()`, `update_penalty_ledger()`.
   - Produces `penalty_ledger_{project_id}.json`.

6. **EoT Agent:** Build `agents/eot_agent.py`:
   - Implements `EOT_AGENT_PROMPT` from `05_AGENT_ENGINE.md`.
   - Handles both hindrance-based (CPWD Clause 5) and FM-based (NITI Aayog Article 19) tracks.
   - Tool calls: `check_eot_timeliness()`, `calculate_net_eot()`, `get_weather()`, `validate_fm_notice()`.
   - Produces `eot_decisions_{project_id}.json`.

7. **Escalation Agent:** Build `agents/escalation_agent.py`:
   - Implements `ESCALATION_AGENT_PROMPT` and the full escalation state machine from `05_AGENT_ENGINE.md`.
   - Separate tracks for EPC (Article 23/26) and Item Rate (Clause 3/25).
   - Tool calls: `lookup_escalation_next_step()`.
   - Produces `escalation_status_{project_id}.json`.

8. **Tool Registry:** Build `tools/registry.py` implementing all tools from `05_AGENT_ENGINE.md`:
   - `query_rule_store`, `calculate_ld`, `get_weather`, `get_news`, `check_eot_timeliness`, `calculate_net_eot`, `get_s_curve_deviation`, `lookup_escalation_next_step`, `check_catchup_refund`, `calculate_early_completion_bonus`.

9. **Wire All Agents to Orchestrator:** Update `agents/orchestrator.py` to actually invoke specialist agents (not just mock-log).

10. **Agent Output Logging:** Implement the audit trail schema from `05_AGENT_ENGINE.md` — every agent call is logged with input/output summaries, tools called, and duration.

## Verification
- Train risk model on synthetic data → verify F1 ≥ 0.78.
- Send an `MPR_UPLOADED` trigger → verify full pipeline: Compliance → Penalty → Risk → Explainer.
- Verify EoT Agent correctly handles the 14-day rule and overlap deduction.
- Verify Escalation Agent correctly follows the EPC and Item Rate state machines.

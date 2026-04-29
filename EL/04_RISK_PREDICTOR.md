# Module 04 — Risk Predictor
> XGBoost · Real Contract-Derived Features · Weather + News Tools  
> Produces: `risk_scores_{project_id}.json` · `predictions_{project_id}.md`

---

## Purpose

The Risk Predictor turns the execution data record into a **forward-looking risk score**: the probability that the project will miss its next milestone or the Scheduled Completion Date. Unlike the Compliance Engine (which reports what *has* happened), the Risk Predictor warns about what *will* happen if current trends continue.

It uses an **XGBoost classifier** whose features are derived directly from the real leading indicators identified in the MoP Committee Report, NITI Aayog EPC Agreement, and Smart City MPR data. It is augmented by **live weather and news tools** for additional predictive context.

---

## Model Architecture

```
execution_data (current + historical)
          +
weather_tool (current forecast + historical anomaly)
          +
news_tool (external risk signals: strikes, clearance delays)
          │
          ▼
   Feature Engineering
          │
          ▼
   XGBoost Classifier
          │
          ├── risk_score (0.0 – 1.0)
          ├── risk_label (LOW / MEDIUM / HIGH / CRITICAL)
          ├── top_risk_factors (SHAP values)
          └── time_to_default_estimate (days)
```

---

## Feature Set

All features are derived from real contract indicators. Each is mapped to its source document.

### Group A — Schedule & Progress Features (Most Predictive)

| Feature | Computation | Source | Why Predictive |
|---|---|---|---|
| `s_curve_deviation_pct` | `actual_pct - planned_pct` | MPR S2 | Primary early warning signal — NITI Aayog |
| `milestone_m1_missed` | Day ≥ M1 trigger AND actual < 20% | Rule Store | MoP: M1 miss = 84% chance of further slippage |
| `days_elapsed_pct` | `day_number / scp_days` | Rule Store | How far into the project we are |
| `progress_velocity` | `(pct_this_month - pct_last_month) / days_in_month` | MPR history | Acceleration/deceleration signal |
| `required_velocity_to_recover` | `(100 - actual_pct) / remaining_days` | computed | If this > historical max velocity → recovery impossible |
| `ld_cap_utilised_pct` | `accumulated_ld / max_ld × 100` | Penalty ledger | Direct financial distress signal |
| `eot_days_consumed_pct` | `eot_granted / scp_days × 100` | EoT Agent | Proxy for how many delays have occurred |

### Group B — Resource Deployment Features

| Feature | Computation | Source | Why Predictive |
|---|---|---|---|
| `labour_skilled_utilisation_pct` | `actual_skilled / planned_skilled × 100` | MPR S5 | MoP: under-mobilization = leading delay signal |
| `labour_unskilled_utilisation_pct` | `actual_unskilled / planned_unskilled × 100` | MPR S5 | Low unskilled labour = earthwork stalled |
| `machinery_idle_days` | Direct from MPR | MPR S5 | Idle machinery = work stopped |

### Group C — Quality & Technical Features

| Feature | Computation | Source | Why Predictive |
|---|---|---|---|
| `test_fail_rate_pct` | `failed / total × 100` | MPR S6 | Rework destroys schedule — NITI Aayog NCR chain |
| `ncrs_pending` | Direct from MPR | MPR S6 | Unresolved NCRs block payment certification |
| `rfis_pending` | Direct from MPR | MPR S6 | Pending inspections stall work |
| `gfc_drawings_pending` | Direct from MPR | MPR S9 | MoP: design backlog = physical work halt |

### Group D — External & Statutory Features

| Feature | Computation | Source | Why Predictive |
|---|---|---|---|
| `row_pending_km` | Direct from MPR | MPR S8 | NHAI: land acquisition avg 12–24 months |
| `utility_shifting_pending` | Boolean from MPR | MPR S8 | NHAI: causes 6–12 month localized delays |
| `railway_clearance_pending` | Boolean from MPR | MPR S8 | NHAI: ROB/RUB approval = 1–2 year risk |
| `forest_clearance_pending` | Boolean from MPR | MPR S8 | MoP: statutory clearance = #2 delay cause |
| `days_lost_rainfall_cumulative` | Sum over all months | MPR S7 | Proxy for monsoon impact |

### Group E — Financial & Contractual Features

| Feature | Computation | Source | Why Predictive |
|---|---|---|---|
| `payment_delayed_streak` | Consecutive months with delayed payment | MPR S10 | MoP: payment delay → cash crunch → slow procurement |
| `variation_claims_count` | Count of open variation claims | Compliance events | MoP: high variation = scope creep + disputes |
| `fm_claim_active` | Boolean | Compliance events | Active FM = legal uncertainty |
| `expenditure_vs_physical_ratio` | `financial_pct / physical_pct` | MPR S2 | Ratio >> 1 means money spent but no physical progress |

### Group F — Live External Signals (Tool-Augmented)

| Feature | Source | Tool | Update Frequency |
|---|---|---|---|
| `weather_anomaly_score` | IMD / OpenWeatherMap | `get_weather()` | Per MPR cycle |
| `monsoon_forecast_risk` | IMD seasonal forecast | `get_weather()` | Monthly |
| `local_strike_risk` | News API | `get_news()` | Monthly |
| `material_price_spike_risk` | News (steel, cement, bitumen) | `get_news()` | Monthly |
| `policy_change_risk` | News (clearance policy changes) | `get_news()` | Monthly |

**Weather Anomaly Scoring:**
```python
def compute_weather_anomaly_score(location: str, month: int, year: int) -> float:
    """
    Compares actual monthly rainfall against 30-year IMD normal for that region/month.
    Returns 0.0 (normal) to 1.0 (extreme anomaly — qualifies as FM).
    Threshold for FM evidence: score >= 0.75 (i.e., > 2 std devs above normal).
    """
    actual_mm = weather_tool.get_monthly_rainfall(location, month, year)
    normal_mm = imd_normals.get(location, month)  # pre-loaded from IMD dataset
    z_score = (actual_mm - normal_mm) / imd_std_dev.get(location, month)
    return min(1.0, max(0.0, z_score / 3))  # clip to [0, 1]
```

---

## Target Variable

```python
TARGET = "will_miss_next_milestone_or_completion"

# Positive class (1) definition:
# Project misses next milestone date OR final SCD within next 60 days
# given current trajectory continues unchanged

# This is a BINARY CLASSIFICATION problem
# Class imbalance handled with ADASYN (Adaptive Synthetic Sampling)
```

---

## Model Spec

```python
import xgboost as xgb
from imblearn.over_sampling import ADASYN
import shap

MODEL_CONFIG = {
    "n_estimators": 400,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "scale_pos_weight": 3,        # adjust for class imbalance
    "eval_metric": "aucpr",       # PR-AUC preferred over ROC-AUC for imbalanced classes
    "early_stopping_rounds": 30,
    "random_state": 42
}

# Evaluation metrics to track (W&B)
METRICS = ["precision", "recall", "f1", "pr_auc", "confusion_matrix"]
# Target: F1 >= 0.78, Recall >= 0.80 (penalize false negatives more — missing a real risk is costly)

# SHAP for explainability
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)
# Top-5 SHAP features per prediction = sent to Explainer Agent
```

**No data leakage:** Test rows are strictly from months not used to generate any training feature. Features are computed from data available *at prediction time* — no future data is used.

---

## Risk Score Output Schema

```json
{
  "project_id": "CONTRACT_001",
  "scored_on": "2025-06-01",
  "day_number": 61,
  "risk_score": 0.73,
  "risk_label": "HIGH",
  "time_to_default_estimate_days": 42,
  "next_milestone": {
    "id": "M1",
    "due_day": 204,
    "days_remaining": 143,
    "required_progress_pct": 20,
    "current_progress_pct": 6.1,
    "required_velocity_to_recover_pct_per_day": 0.098,
    "current_velocity_pct_per_day": 0.041,
    "recovery_feasibility": "VERY_DIFFICULT"
  },
  "top_risk_factors": [
    {
      "feature": "s_curve_deviation_pct",
      "value": -2.1,
      "shap_contribution": 0.18,
      "explanation": "Actual progress is 2.1% behind planned schedule"
    },
    {
      "feature": "gfc_drawings_pending",
      "value": 17,
      "shap_contribution": 0.14,
      "explanation": "17 Good for Construction drawings not yet approved — blocks physical work"
    },
    {
      "feature": "labour_skilled_utilisation_pct",
      "value": 72.9,
      "shap_contribution": 0.12,
      "explanation": "Skilled labour deployed at only 72.9% of planned level"
    },
    {
      "feature": "row_pending_km",
      "value": 3.2,
      "shap_contribution": 0.11,
      "explanation": "3.2 km of Right of Way not yet handed over (Km 238–241.2)"
    },
    {
      "feature": "weather_anomaly_score",
      "value": 0.31,
      "shap_contribution": 0.07,
      "explanation": "Rainfall within normal seasonal range — no FM support"
    }
  ],
  "external_signals": {
    "monsoon_forecast": "Above-normal rainfall forecast for June–September (IMD)",
    "news_flags": ["Steel prices up 8% MoM — may affect procurement"],
    "weather_fm_eligible": false
  },
  "recommendations": [
    "Accelerate GFC drawing approvals — 17 pending is critical path risk",
    "Escalate RoW acquisition at Km 238–241.2 to District Collector",
    "Increase skilled labour to at least 85/day (planned level)",
    "Current trajectory: Milestone-I will be missed by approximately 34 days"
  ]
}
```

---

## S-Curve Deviation Visualisation

The system generates a per-project S-curve chart (Plotly) for the dashboard:

```python
def plot_scurve(project_id: str, execution_history: list) -> plotly.Figure:
    """
    Plots:
    - Planned cumulative progress (baseline S-curve, from rule store)
    - Actual cumulative progress (from MPR history)
    - Forecast trajectory (linear extrapolation of current velocity)
    - Milestone markers (M1, M2, M3, SCD)
    - Shaded danger zone (when forecast crosses 90-day termination threshold)
    """
```

---

## Experiment Tracking (Weights & Biases)

```python
import wandb

wandb.init(project="contractguard-risk-model", config=MODEL_CONFIG)
wandb.log({
    "precision": precision,
    "recall": recall,
    "f1": f1,
    "pr_auc": pr_auc,
    "feature_importance": dict(zip(feature_names, model.feature_importances_))
})
```

---

## Training Data Strategy

Since no real historical project data exists yet, the synthetic generator (Module 02) produces training data with the following scenario distribution:

| Scenario | % of Training Data | Label |
|---|---|---|
| On-track project (no delays) | 40% | 0 |
| Mild delay (< M1 miss) | 20% | 0 |
| M1 missed, recovering | 15% | 1 |
| M1 + M2 missed | 15% | 1 |
| Approaching LD cap | 7% | 1 |
| FM event, valid | 3% | 0 (FM excused) |

Class imbalance: ~40% positive → ADASYN to oversample minority class in training.

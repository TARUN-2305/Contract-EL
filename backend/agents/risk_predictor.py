"""
Risk Predictor — XGBoost-based project risk classification
Per EL/04_RISK_PREDICTOR.md

Features: 25 contract-derived indicators across 6 groups
Target: will_miss_next_milestone_or_completion (binary)
"""
import json
import os
import pickle
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    print("[RiskPredictor] xgboost not available — using heuristic fallback")

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

try:
    from imblearn.over_sampling import ADASYN
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
    print("[RiskPredictor] imbalanced-learn not available — skipping ADASYN")

MODEL_PATH = "/app/data/models/risk_predictor.pkl"
FEATURE_NAMES = [
    # Group A — Schedule & Progress
    "s_curve_deviation_pct",
    "milestone_m1_missed",
    "milestone_m2_missed",
    "days_elapsed_pct",
    "progress_velocity",
    "required_velocity_to_recover",
    "ld_cap_utilised_pct",
    "eot_days_consumed_pct",
    # Group B — Resources
    "labour_skilled_utilisation_pct",
    "labour_unskilled_utilisation_pct",
    "machinery_idle_days",
    # Group C — Quality
    "test_fail_rate_pct",
    "ncrs_pending",
    "rfis_pending",
    "gfc_drawings_pending",
    # Group D — External & Statutory
    "row_pending_pct",
    "utility_shifting_pending",
    "railway_clearance_pending",
    "forest_clearance_pending",
    "days_lost_rainfall_cumulative",
    # Group E — Financial & Contractual
    "payment_delayed_streak",
    "variation_claims_count",
    "fm_claim_active",
    "expenditure_vs_physical_ratio",
    # Group F — External signals (simplified)
    "weather_anomaly_score",
]


# ── Feature Engineering ────────────────────────────────────────────────

def engineer_features(exec_data: dict, rule_store: dict) -> dict:
    """Compute all 25 features from execution data + rule store."""
    scp_days = rule_store.get("scp_days") or 730
    cv = rule_store.get("contract_value_inr") or 1
    day_number = exec_data.get("day_number") or 1
    actual_pct = exec_data.get("actual_physical_pct") or 0
    milestones = rule_store.get("milestones") or []

    # Planned progress at this day (linear S-curve approximation)
    planned_pct = min(100.0, (day_number / scp_days) * 100)
    s_curve_deviation = actual_pct - planned_pct

    # Milestone miss flags
    m1_missed = 0
    m2_missed = 0
    for m in milestones:
        if m.get("id") == "M1" and day_number >= (m.get("trigger_day") or 999999):
            if actual_pct < (m.get("required_physical_progress_pct") or 20):
                m1_missed = 1
        if m.get("id") == "M2" and day_number >= (m.get("trigger_day") or 999999):
            if actual_pct < (m.get("required_physical_progress_pct") or 50):
                m2_missed = 1

    # Progress velocity (pct per day)
    prev_pct = exec_data.get("prev_physical_pct") or max(0, actual_pct - 2)
    days_since_last = exec_data.get("days_since_last_report") or 30
    progress_velocity = (actual_pct - prev_pct) / max(1, days_since_last)

    # Required velocity to recover
    remaining_days = max(1, scp_days - day_number)
    required_velocity = (100 - actual_pct) / remaining_days

    # LD cap utilisation
    ld_info = rule_store.get("liquidated_damages") or {}
    max_ld = ld_info.get("max_cap_inr") or (cv * (ld_info.get("max_cap_pct") or 10) / 100)
    ld_accumulated = exec_data.get("ld_accumulated_inr") or 0
    ld_cap_pct = (ld_accumulated / max_ld * 100) if max_ld > 0 else 0

    # EoT consumed
    eot_granted = exec_data.get("eot_granted_days") or 0
    eot_pct = (eot_granted / scp_days * 100) if scp_days > 0 else 0

    # Resources
    labour_skilled = exec_data.get("labour_skilled_utilisation_pct") or exec_data.get("labour_deployment_pct") or 100
    labour_unskilled = exec_data.get("labour_unskilled_utilisation_pct") or 100
    machinery_idle = exec_data.get("machinery_idle_days") or 0

    # Quality
    ncrs = exec_data.get("ncrs_pending") or len(exec_data.get("open_ncrs") or [])
    rfis = exec_data.get("rfis_pending") or 0
    gfc_pending = exec_data.get("gfc_drawings_pending") or 0
    fail_rate = exec_data.get("test_fail_rate_pct") or 0

    # External
    row_pending = max(0, 100 - (exec_data.get("row_handover_pct") or 100))
    utility = int(exec_data.get("utility_shifting_pending") or False)
    railway = int(exec_data.get("railway_clearance_pending") or False)
    forest = int(exec_data.get("forest_clearance_pending") or False)
    rainfall_days = exec_data.get("days_lost_rainfall_cumulative") or 0

    # Financial
    payment_streak = exec_data.get("payment_delayed_streak") or 0
    vo_count = len(exec_data.get("variation_orders") or [])
    fm_active = int(bool(exec_data.get("force_majeure_events")))
    expenditure_pct = exec_data.get("financial_progress_pct") or actual_pct
    exp_vs_physical = (expenditure_pct / max(0.01, actual_pct))

    # Weather
    weather_score = exec_data.get("weather_anomaly_score") or 0.0

    return {
        "s_curve_deviation_pct": s_curve_deviation,
        "milestone_m1_missed": m1_missed,
        "milestone_m2_missed": m2_missed,
        "days_elapsed_pct": (day_number / scp_days) * 100,
        "progress_velocity": progress_velocity,
        "required_velocity_to_recover": required_velocity,
        "ld_cap_utilised_pct": ld_cap_pct,
        "eot_days_consumed_pct": eot_pct,
        "labour_skilled_utilisation_pct": labour_skilled,
        "labour_unskilled_utilisation_pct": labour_unskilled,
        "machinery_idle_days": machinery_idle,
        "test_fail_rate_pct": fail_rate,
        "ncrs_pending": ncrs,
        "rfis_pending": rfis,
        "gfc_drawings_pending": gfc_pending,
        "row_pending_pct": row_pending,
        "utility_shifting_pending": utility,
        "railway_clearance_pending": railway,
        "forest_clearance_pending": forest,
        "days_lost_rainfall_cumulative": rainfall_days,
        "payment_delayed_streak": payment_streak,
        "variation_claims_count": vo_count,
        "fm_claim_active": fm_active,
        "expenditure_vs_physical_ratio": exp_vs_physical,
        "weather_anomaly_score": weather_score,
    }


# ── Synthetic Training Data ─────────────────────────────────────────────

def generate_training_data(n_samples: int = 2000) -> pd.DataFrame:
    """
    Generate synthetic MPR records based on real EL contract patterns.
    Class distribution: ~35% at-risk (1), ~65% on-track (0) — realistic for infra projects.
    """
    rng = np.random.default_rng(42)
    records = []

    for _ in range(n_samples):
        # Base scenario — at-risk or on-track
        at_risk = rng.random() < 0.35

        if at_risk:
            s_curve_dev = rng.uniform(-30, -5)
            m1_missed = int(rng.random() < 0.7)
            m2_missed = int(rng.random() < 0.6)
            days_elapsed = rng.uniform(30, 95)
            velocity = rng.uniform(0.01, 0.08)
            req_velocity = rng.uniform(0.15, 0.5)
            ld_cap = rng.uniform(5, 95)
            eot_pct = rng.uniform(0, 40)
            labour_skilled = rng.uniform(40, 75)
            labour_unskilled = rng.uniform(40, 80)
            machinery_idle = rng.integers(3, 20)
            fail_rate = rng.uniform(5, 30)
            ncrs = rng.integers(2, 10)
            rfis = rng.integers(1, 8)
            gfc = rng.integers(3, 15)
            row_pend = rng.uniform(15, 60)
            utility = int(rng.random() < 0.4)
            railway = int(rng.random() < 0.25)
            forest = int(rng.random() < 0.2)
            rainfall = rng.integers(10, 40)
            pay_streak = rng.integers(1, 5)
            vo_count = rng.integers(1, 6)
            fm_active = int(rng.random() < 0.3)
            exp_ratio = rng.uniform(0.8, 2.5)
            weather = rng.uniform(0.3, 1.0)
        else:
            s_curve_dev = rng.uniform(-5, 15)
            m1_missed = int(rng.random() < 0.1)
            m2_missed = int(rng.random() < 0.05)
            days_elapsed = rng.uniform(10, 80)
            velocity = rng.uniform(0.08, 0.25)
            req_velocity = rng.uniform(0.05, 0.15)
            ld_cap = rng.uniform(0, 15)
            eot_pct = rng.uniform(0, 10)
            labour_skilled = rng.uniform(75, 110)
            labour_unskilled = rng.uniform(80, 115)
            machinery_idle = rng.integers(0, 4)
            fail_rate = rng.uniform(0, 8)
            ncrs = rng.integers(0, 3)
            rfis = rng.integers(0, 3)
            gfc = rng.integers(0, 4)
            row_pend = rng.uniform(0, 15)
            utility = int(rng.random() < 0.1)
            railway = int(rng.random() < 0.08)
            forest = int(rng.random() < 0.05)
            rainfall = rng.integers(0, 15)
            pay_streak = rng.integers(0, 2)
            vo_count = rng.integers(0, 3)
            fm_active = int(rng.random() < 0.05)
            exp_ratio = rng.uniform(0.9, 1.2)
            weather = rng.uniform(0.0, 0.4)

        records.append({
            "s_curve_deviation_pct": s_curve_dev,
            "milestone_m1_missed": m1_missed,
            "milestone_m2_missed": m2_missed,
            "days_elapsed_pct": days_elapsed,
            "progress_velocity": velocity,
            "required_velocity_to_recover": req_velocity,
            "ld_cap_utilised_pct": ld_cap,
            "eot_days_consumed_pct": eot_pct,
            "labour_skilled_utilisation_pct": labour_skilled,
            "labour_unskilled_utilisation_pct": labour_unskilled,
            "machinery_idle_days": int(machinery_idle),
            "test_fail_rate_pct": fail_rate,
            "ncrs_pending": int(ncrs),
            "rfis_pending": int(rfis),
            "gfc_drawings_pending": int(gfc),
            "row_pending_pct": row_pend,
            "utility_shifting_pending": utility,
            "railway_clearance_pending": railway,
            "forest_clearance_pending": forest,
            "days_lost_rainfall_cumulative": int(rainfall),
            "payment_delayed_streak": int(pay_streak),
            "variation_claims_count": int(vo_count),
            "fm_claim_active": fm_active,
            "expenditure_vs_physical_ratio": exp_ratio,
            "weather_anomaly_score": weather,
            "target": int(at_risk),
        })

    return pd.DataFrame(records)


# ── Model Training ─────────────────────────────────────────────────────

def train_model() -> object:
    """Train XGBoost model on synthetic data. Returns trained model."""
    print("[RiskPredictor] Generating synthetic training data...")
    df = generate_training_data(n_samples=3000)
    X = df[FEATURE_NAMES]
    y = df["target"]

    print(f"[RiskPredictor] Original training set: {len(df)} samples, {y.mean():.1%} positive class")

    if IMBLEARN_AVAILABLE:
        print("[RiskPredictor] Applying ADASYN for class balancing...")
        adasyn = ADASYN(random_state=42)
        try:
            X_resampled, y_resampled = adasyn.fit_resample(X, y)
            print(f"[RiskPredictor] ADASYN resampled training set: {len(y_resampled)} samples, {y_resampled.mean():.1%} positive class")
        except ValueError as e:
            from imblearn.over_sampling import SMOTE
            print(f"[RiskPredictor] ADASYN failed ({e}), falling back to SMOTE")
            X_resampled, y_resampled = SMOTE(random_state=42).fit_resample(X, y)
        X, y = X_resampled, y_resampled

    if not XGB_AVAILABLE:
        raise RuntimeError("xgboost not installed")

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    
    try:
        import wandb
        wandb.init(project="ContractGuard-AI", name="risk_predictor_training")
        wandb.config.update({
            "n_estimators": 400,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "resampling": "ADASYN" if IMBLEARN_AVAILABLE else "None",
            "samples": len(X)
        })
    except ImportError:
        wandb = None
        
    model.fit(X, y, verbose=False)
    
    if wandb:
        from sklearn.metrics import average_precision_score
        y_pred_proba = model.predict_proba(X)[:, 1]
        aucpr = average_precision_score(y, y_pred_proba)
        wandb.log({"train_aucpr": aucpr})
        wandb.finish()
        
    print("[RiskPredictor] Model trained successfully")
    return model


def load_or_train_model():
    """Load model from disk, train if not present."""
    os.makedirs("/app/data/models", exist_ok=True)
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        print(f"[RiskPredictor] Model loaded from {MODEL_PATH}")
        return model
    print("[RiskPredictor] No model found — training fresh...")
    model = train_model()
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"[RiskPredictor] Model saved to {MODEL_PATH}")
    return model


# ── Heuristic fallback (no XGBoost) ────────────────────────────────────

def heuristic_score(features: dict) -> float:
    """Simple weighted heuristic when XGBoost is unavailable."""
    score = 0.0
    score += max(0, -features["s_curve_deviation_pct"]) * 0.03
    score += features["milestone_m1_missed"] * 0.20
    score += features["milestone_m2_missed"] * 0.25
    score += features["ld_cap_utilised_pct"] * 0.005
    score += max(0, 100 - features["labour_skilled_utilisation_pct"]) * 0.003
    score += features["ncrs_pending"] * 0.02
    score += features["gfc_drawings_pending"] * 0.01
    score += features["weather_anomaly_score"] * 0.10
    return min(1.0, max(0.0, score))


# ── RiskPredictor class ─────────────────────────────────────────────────

@dataclass
class RiskPrediction:
    project_id: str
    contract_id: str
    reporting_period: str
    risk_score: float
    risk_label: str
    top_risk_factors: list
    time_to_default_estimate_days: Optional[int]
    features: dict
    model_type: str


RISK_LABELS = [
    (0.75, "CRITICAL"),
    (0.55, "HIGH"),
    (0.35, "MEDIUM"),
    (0.0,  "LOW"),
]

def score_to_label(score: float) -> str:
    for threshold, label in RISK_LABELS:
        if score >= threshold:
            return label
    return "LOW"


class RiskPredictor:
    def __init__(self):
        self.model = None
        self._load()

    def _load(self):
        try:
            self.model = load_or_train_model()
        except Exception as e:
            print(f"[RiskPredictor] Model load/train failed: {e} — using heuristic")
            self.model = None

    def predict(self, exec_data: dict, rule_store: dict) -> RiskPrediction:
        features = engineer_features(exec_data, rule_store)
        feature_vector = [features[f] for f in FEATURE_NAMES]

        if self.model is not None and XGB_AVAILABLE:
            X = pd.DataFrame([features])[FEATURE_NAMES]
            risk_score = float(self.model.predict_proba(X)[0][1])
            model_type = "xgboost"

            # SHAP top factors
            top_factors = []
            if SHAP_AVAILABLE:
                try:
                    explainer = shap.TreeExplainer(self.model)
                    shap_vals = explainer.shap_values(X)[0]
                    factor_pairs = sorted(
                        zip(FEATURE_NAMES, shap_vals),
                        key=lambda x: abs(x[1]),
                        reverse=True,
                    )
                    top_factors = [
                        {"feature": name, "shap_value": round(float(val), 4), "direction": "increases_risk" if val > 0 else "decreases_risk"}
                        for name, val in factor_pairs[:5]
                    ]
                except Exception:
                    pass
            if not top_factors:
                # Fallback: use feature importances
                importances = self.model.feature_importances_
                factor_pairs = sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1])
                top_factors = [
                    {"feature": name, "importance": round(float(imp), 4)}
                    for name, imp in factor_pairs[:5]
                ]
        else:
            risk_score = heuristic_score(features)
            model_type = "heuristic"
            # Top factors from feature values
            factor_contributions = {
                "s_curve_deviation_pct": max(0, -features["s_curve_deviation_pct"]) * 0.03,
                "milestone_m1_missed": features["milestone_m1_missed"] * 0.20,
                "milestone_m2_missed": features["milestone_m2_missed"] * 0.25,
                "ld_cap_utilised_pct": features["ld_cap_utilised_pct"] * 0.005,
                "ncrs_pending": features["ncrs_pending"] * 0.02,
            }
            top_factors = [
                {"feature": k, "contribution": round(v, 4)}
                for k, v in sorted(factor_contributions.items(), key=lambda x: -x[1])[:5]
            ]

        risk_label = score_to_label(risk_score)

        # Estimate time-to-default
        remaining_days = max(1, (rule_store.get("scp_days") or 730) - (exec_data.get("day_number") or 0))
        if risk_score > 0.7:
            ttd = int(remaining_days * 0.3)
        elif risk_score > 0.5:
            ttd = int(remaining_days * 0.6)
        else:
            ttd = None

        return RiskPrediction(
            project_id=exec_data.get("project_id") or exec_data.get("contract_id"),
            contract_id=exec_data.get("contract_id"),
            reporting_period=exec_data.get("reporting_period", ""),
            risk_score=round(risk_score, 4),
            risk_label=risk_label,
            top_risk_factors=top_factors,
            time_to_default_estimate_days=ttd,
            features=features,
            model_type=model_type,
        )


# ── CLI ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick train test
    model = load_or_train_model()
    print(f"[RiskPredictor] Model type: {type(model).__name__}")
    df = generate_training_data(200)
    X = df[FEATURE_NAMES]
    y = df["target"]
    preds = model.predict(X)
    from sklearn.metrics import classification_report
    print(classification_report(y, preds))

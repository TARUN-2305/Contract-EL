"""Test the /predict-risk endpoint with a high-risk scenario."""
import httpx, json, sys
sys.stdout.reconfigure(encoding='utf-8')

exec_data = {
    "contract_id": "CONTRACT_001",
    "project_id": "CONTRACT_001",
    "reporting_period": "2026-05",
    "report_date": "2026-05-26",
    "appointed_date": "2025-04-01",
    "day_number": 450,
    "actual_physical_pct": 35.0,
    "prev_physical_pct": 30.0,
    "days_since_last_report": 30,
    "ld_accumulated_inr": 2800000,
    "eot_granted_days": 20,
    "financial_progress_pct": 65.0,
    "labour_skilled_utilisation_pct": 60.0,
    "labour_unskilled_utilisation_pct": 65.0,
    "machinery_idle_days": 8,
    "test_fail_rate_pct": 12.0,
    "ncrs_pending": 4,
    "rfis_pending": 3,
    "gfc_drawings_pending": 7,
    "row_handover_pct": 80.0,
    "utility_shifting_pending": True,
    "railway_clearance_pending": False,
    "forest_clearance_pending": False,
    "days_lost_rainfall_cumulative": 22,
    "payment_delayed_streak": 2,
    "variation_orders": [{"vo_id": "VO-001"}],
    "force_majeure_events": [],
    "weather_anomaly_score": 0.45,
}

r = httpx.post("http://127.0.0.1:8000/predict-risk", json=exec_data, timeout=30)
print(f"Status: {r.status_code}")
d = r.json()
print(f"\n=== RISK PREDICTION ===")
print(f"Score  : {d.get('risk_score'):.4f}")
print(f"Label  : {d.get('risk_label')}")
print(f"Model  : {d.get('model_type')}")
print(f"TTD    : {d.get('time_to_default_estimate_days')} days")
print(f"\n--- Top Risk Factors ---")
for f in d.get("top_risk_factors", []):
    print(f"  {f}")

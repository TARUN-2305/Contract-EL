"""End-to-end full-analysis pipeline test."""
import httpx, json, sys, os
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
    "intermediate_ld_deducted_inr": 800000,
    "eot_granted_days": 15,
    "financial_progress_pct": 52.0,
    "performance_security_submitted": True,
    "ps_submission_date": "2025-04-20",
    "row_handover_pct": 85.0,
    "labour_deployment_pct": 65.0,
    "labour_skilled_utilisation_pct": 65.0,
    "machinery_deployment_pct": 80.0,
    "machinery_idle_days": 5,
    "test_fail_rate_pct": 12.0,
    "ncrs_pending": 3,
    "rfis_pending": 2,
    "gfc_drawings_pending": 7,
    "hindrance_register_unsigned_entries": 0,
    "hindrances": [],
    "force_majeure_events": [],
    "variation_orders": [{"vo_id": "VO-001"}],
    "ra_bills": [],
    "weather_anomaly_score": 0.35,
    "open_ncrs": [{"id": "NCR-001", "defect": "Compaction", "issued_date": "2025-11-01", "rectification_deadline_days": 30}],
}

r = httpx.post("http://127.0.0.1:8000/full-analysis", json=exec_data, timeout=60)
print(f"Status: {r.status_code}")
d = r.json()
print(f"Message : {d.get('message')}")
comp = d.get("compliance", {})
risk = d.get("risk", {})
print(f"\nCompliance: {comp.get('total_events')} events, {comp.get('critical_count')} CRITICAL, LD=Rs.{comp.get('total_ld_accrued_inr',0):,.0f}")
print(f"Risk     : {risk.get('score'):.4f} {risk.get('label')} (TTD: {risk.get('ttd_days')} days)")
print(f"\nReports  : {d.get('reports')}")

md_path = d.get("reports", {}).get("compliance_md", "")
if os.path.exists(md_path):
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    print(f"\n--- compliance.md preview (first 800 chars) ---")
    print(content[:800])

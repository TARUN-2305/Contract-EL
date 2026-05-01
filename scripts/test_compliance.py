"""
Test the Compliance Engine via /run-compliance endpoint.
Simulates a Month-3 MPR for NH-44 Karnataka Road Widening project.
"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Month-3 execution data — Day 204 (M1 trigger), actual progress only 15% (should be 20%)
exec_data = {
    "contract_id": "CONTRACT_001",
    "project_id": "CONTRACT_001",
    "reporting_period": "2025-12",
    "report_date": "2025-12-31",
    "appointed_date": "2025-04-01",
    "day_number": 274,                        # Past M1 trigger (Day 204) and M2 (Day 401)
    "actual_physical_pct": 35.0,              # Behind: M1 needs 20% (ok), M2 needs 50% (missed)
    "ld_accumulated_inr": 1200000,            # Rs. 12 lakh accumulated
    "intermediate_ld_deducted_inr": 0,
    "performance_security_submitted": True,
    "ps_submission_date": "2025-04-20",       # 19 days after appointed date (deadline 15 days) — late
    "row_handover_pct": 85.0,
    "labour_deployment_pct": 65.0,            # Under-deployed
    "machinery_deployment_pct": 78.0,
    "test_fail_rate_pct": 4.5,                # OK
    "open_ncrs": [
        {
            "id": "NCR-001",
            "defect": "Subgrade compaction failure",
            "issued_date": "2025-12-21",
            "rectification_deadline_days": 30
        }
    ],
    "gfc_drawings_pending": 3,
    "hindrance_register_unsigned_entries": 2,
    "hindrances": [
        {
            "hindrance_id": "H-001",
            "nature": "Rain — Monsoon",
            "date_of_occurrence": "2025-09-01",
            "eot_application_submitted": True,
            "eot_application_date": "2025-09-20"  # 19 days — 5 days late
        }
    ],
    "force_majeure_events": [],
    "variation_orders": [
        {
            "vo_id": "VO-001",
            "vo_issued_date": "2025-11-01",
            "claim_submitted_date": None     # Missed claim window
        }
    ],
    "ra_bills": [
        {
            "bill_id": "RA-003",
            "submitted_date": "2025-12-05",
            "amount_inr": 5000000,
            "verified": False,
            "paid": False
        }
    ]
}

client = httpx.Client(timeout=60.0)
r = client.post("http://127.0.0.1:8000/run-compliance", json=exec_data)
print(f"Status: {r.status_code}")
data = r.json()
print(f"\n=== COMPLIANCE REPORT ===")
print(f"Total Events : {data.get('total_events')}")
print(f"CRITICAL      : {data.get('critical_count')}")
print(f"HIGH          : {data.get('high_count')}")
print(f"LD Accrued    : Rs. {data.get('total_ld_accrued_inr', 0):,.0f}")
print(f"\n--- Events ---")
for e in data.get("events", []):
    print(f"[{e['severity']:8s}] {e['check_id']:10s} {e['title']}")
    if e.get('ld_accrued_inr'):
        print(f"             LD: Rs. {e['ld_accrued_inr']:,.0f} | Action: {e['action']}")
    else:
        print(f"             Action: {e['action']}")

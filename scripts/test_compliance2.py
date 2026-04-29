"""Patch M4 trigger_day in existing rule store and re-run compliance with full milestone scenario."""
import json
import httpx
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Patch existing rule store
with open('data/rule_store/rule_store_CONTRACT_001.json', encoding='utf-8') as f:
    rs = json.load(f)

for m in rs.get('milestones', []):
    if m['id'] == 'M4' and m.get('trigger_day', 0) <= 547:
        m['trigger_day'] = rs['scp_days']  # 730
        print(f"Patched M4 trigger_day -> {rs['scp_days']}")

with open('data/rule_store/rule_store_CONTRACT_001.json', 'w', encoding='utf-8') as f:
    json.dump(rs, f, indent=2)

print("Rule store patched. Running compliance test...")

# Day 450 — past M2 trigger (Day 401), actual 35% (needs 50%) -> M2 LD fires
exec_data = {
    "contract_id": "CONTRACT_001",
    "project_id": "CONTRACT_001",
    "reporting_period": "2026-05",
    "report_date": "2026-05-26",
    "appointed_date": "2025-04-01",
    "day_number": 450,
    "actual_physical_pct": 35.0,         # M2 missed (needs 50%), M3 also at risk
    "ld_accumulated_inr": 2800000,        # Rs 28 lakh — 87.5% of 10% cap warning zone
    "intermediate_ld_deducted_inr": 1500000,
    "performance_security_submitted": True,
    "ps_submission_date": "2025-04-16",   # 1 day late
    "row_handover_pct": 90.0,
    "labour_deployment_pct": 75.0,
    "machinery_deployment_pct": 82.0,
    "test_fail_rate_pct": 3.0,
    "open_ncrs": [],
    "gfc_drawings_pending": 2,
    "hindrance_register_unsigned_entries": 0,
    "hindrances": [],
    "force_majeure_events": [],
    "variation_orders": [],
    "ra_bills": []
}

client = httpx.Client(timeout=60.0)
r = client.post("http://127.0.0.1:8000/run-compliance", json=exec_data)
print(f"\nStatus: {r.status_code}")
data = r.json()
print(f"\n=== COMPLIANCE REPORT (Day 450) ===")
print(f"Total Events : {data.get('total_events')}")
print(f"CRITICAL      : {data.get('critical_count')}")
print(f"HIGH          : {data.get('high_count')}")
print(f"LD Accrued    : Rs. {data.get('total_ld_accrued_inr', 0):,.0f}")
print(f"\n--- Events ---")
for e in data.get("events", []):
    print(f"[{e['severity']:8s}] {e['check_id']:12s} {e['title']}")
    if e.get('ld_accrued_inr'):
        print(f"               LD: Rs. {e['ld_accrued_inr']:,.0f} | Daily: Rs. {e.get('ld_daily_rate_inr',0):,.0f}")
    print(f"               Clause: {e['clause']}")
    print(f"               Action: {e['action']}")
    print()

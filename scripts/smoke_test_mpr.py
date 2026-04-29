"""Smoke test all 5 MPR docx scenarios."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
# Navigate to project root regardless of how script is invoked
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from agents.mpr_parser import parse_mpr_docx

scenarios = [
    ("A - ON TRACK",     "MPR_A_ON_TRACK_Month3_Day91.docx"),
    ("B - AT RISK",      "MPR_B_AT_RISK_Month7_Day214_M1Missed.docx"),
    ("C - DEFAULTING",   "MPR_C_DEFAULTING_Month14_Day426_LDCap62pct.docx"),
    ("D - VALID FM",     "MPR_D_VALID_FM_Month5_Day152_Flood.docx"),
    ("E - INVALID FM",   "MPR_E_INVALID_FM_LateEoT_Month6_Day183.docx"),
    ("F - NEAR COMPLETE","MPR_F_NEAR_COMPLETE_Bonus_CatchUp_Month22.docx"),
]

all_ok = True
for label, fname in scenarios:
    path = f"Fake contracts and reports/{fname}"
    try:
        d = parse_mpr_docx(path, bypass_date_check=True)
        print(f"[OK]  {label}")
        print(f"      Day={d['day_number']}  Actual={d['actual_physical_pct']}%  "
              f"Labour={d['labour_skilled_utilisation_pct']}%  "
              f"NCRs={d['ncrs_pending']}  GFC={d['gfc_drawings_pending']}  "
              f"Rainfall={d['rainfall_mm_monthly']}mm  "
              f"PayDelay={d['payment_delay_days']}d")
    except Exception as e:
        print(f"[ERR] {label}: {e}")
        all_ok = False

print()
print("ALL OK" if all_ok else "SOME FAILURES")

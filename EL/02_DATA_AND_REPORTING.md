# Module 02 — Data & Reporting
> MPR Upload Pipeline · Execution Data Schema · Hindrance Register  
> Produces: `execution_data_{project_id}.csv` · `hindrance_{project_id}.json`

---

## Purpose

This module defines how **real execution data enters the system**. The Site Engineer is the primary data producer. They upload a structured Markdown file (the Monthly Progress Report) each month. This module parses it, validates it, and converts it into the structured execution record that feeds the Compliance Engine and Risk Predictor.

There is no synthetic data in production — but a **synthetic data generator** is available for testing and demos, seeded from real MPR field definitions.

---

## Who Uploads What

| Role | Upload | Frequency | Format |
|---|---|---|---|
| Site Engineer | Monthly Progress Report | Monthly (by 5th of next month) | `.md` file |
| Site Engineer | Hindrance Register entry | On occurrence of any hindrance | Form in dashboard |
| Contractor | Force Majeure claim | On occurrence | Form in dashboard |
| Contractor | Quality test results | Per test event | Form in dashboard |

---

## The Monthly Progress Report (MPR) — Markdown Template

This is the **exact MD file the Site Engineer fills and uploads**. The parser reads field labels as keys. All fields are mandatory unless marked `[OPTIONAL]`.

```markdown
# Monthly Progress Report
## Section 1 — Project Metadata
- **Project Name:** NH-44 Karnataka Road Widening (Km 220–260)
- **Agreement Number:** NHAI/KA/EPC/2025/001
- **Contractor Name:** XYZ Constructions Pvt. Ltd.
- **Engineer-in-Charge:** [Name]
- **Reporting Period:** 2025-05-01 to 2025-05-31
- **Stipulated Date of Completion:** 2027-03-31
- **Approved EoT Date:** [OPTIONAL — fill if EoT has been granted]
- **Day Number (from Appointed Date):** 61

## Section 2 — Physical & Financial Progress
- **Planned Physical Progress to Date (%):** 8.2
- **Actual Physical Progress to Date (%):** 6.1
- **Variance (%):** -2.1
- **Cumulative Expenditure to Date (₹):** 11500000
- **Planned Expenditure to Date (₹):** 14200000
- **Financial Progress (%):** 4.6

## Section 3 — BoQ Execution Data
| BoQ Item | Unit | Total Qty | Prev Cumulative | This Month | Cumulative | % Complete |
|---|---|---|---|---|---|---|
| Earthwork Embankment | Cum | 450000 | 12000 | 18500 | 30500 | 6.8 |
| Granular Sub-Base (GSB) | Cum | 85000 | 0 | 0 | 0 | 0.0 |
| Wet Mix Macadam (WMM) | Cum | 72000 | 0 | 0 | 0 | 0.0 |
| M30 Concrete (Bridges) | Cum | 12000 | 280 | 410 | 690 | 5.75 |
| Pile Foundation | RM | 4200 | 180 | 240 | 420 | 10.0 |

## Section 4 — Material Reconciliation
| Material | Opening Balance | Received | Consumed | Closing Balance | Theoretical Consumption |
|---|---|---|---|---|---|
| Cement (bags) | 1200 | 4800 | 4650 | 1350 | 4700 |
| Steel (MT) | 12 | 48 | 45 | 15 | 46 |
| Bitumen (MT) | 0 | 0 | 0 | 0 | 0 |

## Section 5 — Labour & Machinery Deployment
- **Planned Skilled Labour (daily avg):** 85
- **Actual Skilled Labour (daily avg):** 62
- **Planned Unskilled Labour (daily avg):** 210
- **Actual Unskilled Labour (daily avg):** 148
- **Key Machinery Deployed:** 3 Excavators, 2 Tipper Trucks, 1 Concrete Batching Plant
- **Machinery Idle Days (if any):** 0

## Section 6 — Quality Assurance
| Test Type | Material | Tests Conducted | Tests Passed | Tests Failed | Remarks |
|---|---|---|---|---|---|
| Cube Strength (7-day) | M30 Concrete | 6 | 5 | 1 | 1 batch below 20 MPa |
| Field Density Test | Embankment Soil | 4 | 4 | 0 | All ≥97% MDD |
| Slump Test | M30 Concrete | 18 | 18 | 0 | Within range |

- **NCRs Issued This Month:** 1
- **NCRs Pending Closure:** 1
- **RFIs Submitted:** 3
- **RFIs Approved:** 2
- **RFIs Pending:** 1

## Section 7 — External Disruptions & Hindrance Data
- **Working Days in Month:** 31
- **Days Lost to Rainfall:** 4
- **Days Lost to Other Hindrances:** 0
- **Daily Rainfall (avg mm):** 12.4
- **Cumulative Rainfall this Month (mm):** 48.2
- **Avg Temperature (°C):** 28.5
- **Avg Humidity (%):** 74

## Section 8 — Land Acquisition & Utilities Status
- **Total RoW Required (km):** 40
- **RoW Handed Over (km):** 36.8
- **RoW Pending (km):** 3.2
- **Pending Chainage:** Km 238 to Km 241.2
- **HT Power Lines Shifted (Y/N):** N
- **Utility Shifting Status:** 2 HT lines pending — BESCOM advised 45-day timeline
- **Tree Felling Clearance (Y/N):** Y

## Section 9 — GFC Drawing Status
- **Total GFC Drawings Required:** 48
- **GFC Drawings Approved:** 31
- **GFC Drawings Pending:** 17
- **Critical Pending Drawing:** Pier design for Bridge at Km 231 — submitted 2025-04-18, awaiting AE approval

## Section 10 — RA Bill & Payment Status
- **RA Bill Number:** RA-02
- **RA Bill Amount (₹):** 5850000
- **RA Bill Submitted Date:** 2025-05-05
- **Previous Bill Payment Received (Y/N):** Y
- **Previous Bill Payment Date:** 2025-04-28
- **Payment Delay (days, if any):** 0

## Section 11 — Site Engineer Declaration
- **Reported By:** [Site Engineer Name]
- **Designation:** Junior Engineer
- **Signature Date:** 2025-06-02
- **Verified By (AE/JE co-sign):** [Name]
```

---

## MPR Parser Logic

```python
def parse_mpr(md_file_path: str) -> dict:
    """
    Reads the structured MPR markdown and returns a typed execution record.
    Uses regex + markdown table parser.
    Falls back to LLM extraction for malformed fields.
    """
    raw = read_md(md_file_path)
    record = {
        "project_id": extract_field(raw, "Agreement Number"),
        "reporting_period_end": extract_field(raw, "Reporting Period").split(" to ")[1],
        "day_number": int(extract_field(raw, "Day Number")),
        "planned_physical_pct": float(extract_field(raw, "Planned Physical Progress to Date")),
        "actual_physical_pct": float(extract_field(raw, "Actual Physical Progress to Date")),
        "variance_pct": float(extract_field(raw, "Variance")),
        "cumulative_expenditure_inr": float(extract_field(raw, "Cumulative Expenditure to Date")),
        "planned_expenditure_inr": float(extract_field(raw, "Planned Expenditure to Date")),
        "labour_skilled_planned": int(extract_field(raw, "Planned Skilled Labour")),
        "labour_skilled_actual": int(extract_field(raw, "Actual Skilled Labour")),
        "ncrs_pending": int(extract_field(raw, "NCRs Pending Closure")),
        "rfis_pending": int(extract_field(raw, "RFIs Pending")),
        "days_lost_rainfall": int(extract_field(raw, "Days Lost to Rainfall")),
        "row_pending_km": float(extract_field(raw, "RoW Pending")),
        "gfc_drawings_pending": int(extract_field(raw, "GFC Drawings Pending")),
        "ra_bill_submitted": extract_field(raw, "RA Bill Submitted Date"),
        "boq_items": parse_table(raw, "Section 3"),
        "qa_results": parse_table(raw, "Section 6"),
        "hindrance_days": calculate_hindrance_days(raw),
    }
    return record
```

---

## Execution Data Schema (CSV)

Each parsed MPR becomes one row in the execution data CSV:

| Column | Type | Source | Description |
|---|---|---|---|
| `project_id` | str | metadata | Unique project identifier |
| `contract_type` | str | metadata | `EPC` or `ITEM_RATE` |
| `reporting_month` | int | MPR | Month number from Appointed Date (1–24) |
| `day_number` | int | MPR | Day from Appointed Date |
| `planned_physical_pct` | float | MPR S2 | Planned cumulative progress % |
| `actual_physical_pct` | float | MPR S2 | Actual cumulative progress % |
| `s_curve_deviation_pct` | float | computed | `actual - planned` |
| `cumulative_expenditure_inr` | float | MPR S2 | Total money spent to date |
| `expenditure_variance_inr` | float | computed | `planned_exp - actual_exp` |
| `labour_skilled_utilisation_pct` | float | computed | `actual/planned × 100` |
| `labour_unskilled_utilisation_pct` | float | computed | `actual/planned × 100` |
| `ncrs_pending` | int | MPR S6 | Open non-conformance reports |
| `test_fail_rate_pct` | float | MPR S6 | `failed/total × 100` |
| `rfis_pending` | int | MPR S6 | Unapproved inspection requests |
| `days_lost_rainfall` | int | MPR S7 | Working days lost this month |
| `rainfall_mm_monthly` | float | MPR S7 | Total rainfall this month |
| `row_pending_km` | float | MPR S8 | Unacquired land |
| `utility_shifting_pending` | bool | MPR S8 | Any HT lines / pipes pending |
| `gfc_drawings_pending` | int | MPR S9 | Drawings not yet approved |
| `payment_delayed` | bool | MPR S10 | Previous RA bill paid late |
| `milestone_m1_missed` | bool | computed | Did contractor miss M1? |
| `milestone_m2_missed` | bool | computed | Did contractor miss M2? |
| `milestone_m3_missed` | bool | computed | Did contractor miss M3? |
| `ld_accumulated_inr` | float | Penalty Agent | Cumulative LD deducted |
| `ld_pct_of_cap` | float | computed | `ld_accumulated / max_ld_cap × 100` |
| `eot_granted_days` | int | EoT Agent | Total EoT days approved so far |
| `fm_claim_active` | bool | FM module | Active Force Majeure claim? |
| `risk_score` | float | Risk Agent | 0–1 delay risk score |
| `risk_label` | str | Risk Agent | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |

---

## Hindrance Register — Data Schema

Stored as JSON, one array per project. Each entry:

```json
{
  "hindrance_id": "HR-001",
  "project_id": "CONTRACT_001",
  "nature_of_hindrance": "Delayed GFC Drawing — Pier at Km 231",
  "boq_items_blocked": ["M30 Concrete (Bridges)", "Pile Foundation"],
  "date_of_occurrence": "2025-05-18",
  "date_of_removal": null,
  "total_days": null,
  "overlapping_hindrance_ids": [],
  "overlapping_days": 0,
  "net_extension_justified_days": null,
  "hindrance_category": "AUTHORITY_DEFAULT",
  "logged_by": "site_engineer_001",
  "jae_signature_date": "2025-05-18",
  "ee_authenticated": false,
  "eot_application_submitted": false,
  "eot_application_date": null,
  "status": "OPEN"
}
```

**Hindrance Categories:**
- `AUTHORITY_DEFAULT` — land not handed over, drawings not issued, materials not supplied
- `FORCE_MAJEURE_WEATHER` — abnormal rainfall (IMD certified), earthquake, flood
- `FORCE_MAJEURE_POLITICAL` — strike, riot, curfew (FIR/government order required)
- `STATUTORY_CLEARANCE` — pending forest/env clearance, railway GAD approval
- `UTILITY_SHIFTING` — HT lines, water mains, OFC pending by state agency

**Overlap Deduction Logic:**
```python
def calculate_net_eot(hindrances: list) -> int:
    """
    Merge overlapping date ranges across all hindrance entries.
    Sum of merged ranges = net days eligible for EoT.
    Prevents double-counting of concurrent delays.
    """
    date_ranges = [(h["date_of_occurrence"], h["date_of_removal"])
                   for h in hindrances if h["status"] == "CLOSED"]
    merged = merge_date_ranges(date_ranges)  # standard interval merge
    return sum((end - start).days for start, end in merged)
```

---

## Synthetic Data Generator (for testing only)

Generates realistic execution data seeded from real contract parameters and known delay patterns from the MoP Report and NHAI Works Manual.

```python
DELAY_PROBABILITY_SEEDS = {
    "row_pending_km_gt_5": 0.72,          # MoP: land delay = #1 cause
    "gfc_drawings_pending_gt_10": 0.65,   # slow design approvals
    "labour_utilisation_lt_70pct": 0.58,  # under-mobilization
    "test_fail_rate_gt_15pct": 0.51,      # rework destroys schedule
    "milestone_m1_missed": 0.84,           # NITI Aayog: M1 miss = strong predictor
    "payment_delayed_consecutive_2mo": 0.69, # MoP: delayed payments → slow work
}

def generate_project(
    contract_value: float,
    scp_days: int,
    seed_scenario: str = "at_risk"  # "on_track", "at_risk", "defaulting"
) -> pd.DataFrame:
    ...
```

---

## Validation Rules on MPR Upload

Before accepting the MPR, the system runs:

1. **Date check** — `reporting_period_end` must be ≤ today, ≥ previous MPR date
2. **Monotonicity** — `actual_physical_pct` must be ≥ previous month's value
3. **Labour sanity** — actual labour cannot exceed 150% of planned (flags data entry error)
4. **QA consistency** — `tests_passed + tests_failed` must equal `tests_conducted`
5. **RA bill date** — must be after the reporting period ends

Any failed validation → MPR is **rejected with specific error message** and returned to Site Engineer for correction. It is not partially ingested.

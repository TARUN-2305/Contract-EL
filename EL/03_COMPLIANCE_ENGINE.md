# Module 03 — Compliance Engine
> Rule-Based Violation Detection · LD Calculator · EoT/FM Handler  
> Produces: `compliance_events_{project_id}.json`

---

## Purpose

The Compliance Engine is the **legal brain** of the system. After every MPR upload, it fires sequentially through every rule type, compares execution data against the rule store, and produces a structured list of compliance events. Each event carries: what was violated, the exact clause, the financial consequence, and the recommended action.

This module is **deterministic** — same inputs always produce the same outputs. No LLM is used for the rule checks themselves. The LLM (Explainer Agent) is only called to narrate the results.

---

## Trigger

Fires automatically after every successful MPR parse and validation.

Input: `execution_data_current_month` + `rule_store_{contract_id}.json` + `historical_events`

---

## Compliance Check Sequence

Checks run in this order. If a critical check fails, subsequent checks still run (full audit, not fail-fast).

```
CHECK 01: Performance Security submission
CHECK 02: Conditions Precedent status
CHECK 03: Milestone progress (M1, M2, M3, Final)
CHECK 04: LD accumulation and cap proximity
CHECK 05: Catch-up refund eligibility (EPC only)
CHECK 06: Labour & machinery adequacy
CHECK 07: Quality assurance — NCR status
CHECK 08: GFC Drawing backlog
CHECK 09: Hindrance Register completeness
CHECK 10: EoT application timeliness (14-day rule)
CHECK 11: Force Majeure claim validity
CHECK 12: Variation order claim timeliness (14-day rule)
CHECK 13: RA Bill payment cycle
CHECK 14: Early completion bonus eligibility (if near completion)
CHECK 15: Termination threshold proximity
```

---

## Check Definitions

### CHECK 01 — Performance Security
```python
def check_performance_security(exec_data, rule_store):
    deadline = appointed_date + timedelta(days=rule_store["performance_security"]["submission_deadline_days"])
    max_deadline = deadline + timedelta(days=rule_store["performance_security"]["max_extension_days"])

    if exec_data["performance_security_submitted"]:
        if exec_data["ps_submission_date"] > deadline:
            late_days = (exec_data["ps_submission_date"] - deadline).days
            late_fee = late_days * (rule_store["performance_security"]["late_fee_pct_per_day"] / 100) \
                       * rule_store["performance_security"]["amount_inr"]
            return ComplianceEvent(
                check_id="C01", severity="MEDIUM",
                title="Late Performance Security Submission",
                clause="CPWD GCC Clause 1",
                description=f"Performance Security submitted {late_days} days late.",
                financial_impact=late_fee,
                action="DEDUCT_LATE_FEE"
            )
    else:
        if today > max_deadline:
            return ComplianceEvent(
                check_id="C01", severity="CRITICAL",
                title="Performance Security NOT Submitted",
                clause="CPWD GCC Clause 1",
                description="LoA is deemed cancelled. EMD must be forfeited.",
                financial_impact=rule_store["performance_security"]["amount_inr"],
                action="CANCEL_LOA_FORFEIT_EMD"
            )
```

---

### CHECK 03 — Milestone Progress

```python
def check_milestones(exec_data, rule_store):
    events = []
    for milestone in rule_store["milestones"]:
        if exec_data["day_number"] >= milestone["trigger_day"]:
            if exec_data["actual_physical_pct"] < milestone["required_physical_progress_pct"]:
                shortfall_pct = milestone["required_physical_progress_pct"] - exec_data["actual_physical_pct"]
                delay_days = exec_data["day_number"] - milestone["trigger_day"]

                # LD calculation
                if milestone["ld_basis"] == "apportioned_milestone_value":
                    basis = rule_store["contract_value_inr"] * (milestone["required_physical_progress_pct"] / 100)
                else:
                    basis = rule_store["contract_value_inr"]

                ld_today = (milestone["ld_rate_pct_per_day"] / 100) * basis * delay_days
                ld_capped = min(ld_today, rule_store["contract_value_inr"] * (rule_store["liquidated_damages"]["max_cap_pct"] / 100))

                events.append(ComplianceEvent(
                    check_id=f"C03_{milestone['id']}",
                    severity="HIGH" if milestone["id"] != "M4" else "CRITICAL",
                    title=f"{milestone['name']} Missed",
                    clause=milestone["source_clause"],
                    description=(
                        f"Required {milestone['required_physical_progress_pct']}% progress by Day "
                        f"{milestone['trigger_day']}. Actual: {exec_data['actual_physical_pct']}%. "
                        f"Shortfall: {shortfall_pct:.1f}%. Delay: {delay_days} days."
                    ),
                    ld_accrued_inr=ld_capped,
                    ld_daily_rate_inr=(milestone["ld_rate_pct_per_day"] / 100) * basis,
                    catch_up_refund_eligible=milestone["catch_up_refund_eligible"],
                    action="DEDUCT_LD_NOTIFY_CONTRACTOR"
                ))
    return events
```

---

### CHECK 04 — LD Cap Proximity

```python
def check_ld_cap(exec_data, rule_store):
    max_ld = rule_store["liquidated_damages"]["max_cap_inr"]
    accumulated = exec_data["ld_accumulated_inr"]
    cap_pct = (accumulated / max_ld) * 100

    if cap_pct >= 100:
        return ComplianceEvent(
            check_id="C04", severity="CRITICAL",
            title="LD Cap Exhausted — Contractor Default",
            clause="Article 10.3.2 / CPWD Clause 2",
            description=f"Accumulated LD ₹{accumulated:,.0f} has reached the 10% cap of ₹{max_ld:,.0f}. "
                        f"This constitutes Contractor Default. Issue Notice of Intent to Terminate.",
            action="ISSUE_NOTICE_OF_DEFAULT"
        )
    elif cap_pct >= 80:
        return ComplianceEvent(
            check_id="C04", severity="HIGH",
            title=f"LD Cap at {cap_pct:.1f}% — Warning",
            clause="Article 10.3.2",
            description=f"Accumulated LD is ₹{accumulated:,.0f} ({cap_pct:.1f}% of cap). "
                        f"₹{max_ld - accumulated:,.0f} remaining before Contractor Default.",
            action="ALERT_PROJECT_MANAGER"
        )
```

---

### CHECK 05 — Catch-Up Refund (EPC Only)

```python
def check_catchup_refund(exec_data, rule_store):
    """
    NITI Aayog Article 10.3.3:
    If final milestone achieved on time despite intermediate misses,
    all intermediate LDs must be refunded.
    """
    if rule_store["contract_type"] != "EPC":
        return None

    final_milestone = rule_store["milestones"][-1]
    if exec_data["day_number"] >= final_milestone["trigger_day"]:
        if exec_data["actual_physical_pct"] >= 100:
            # Final milestone achieved on time
            intermediate_ld = sum_intermediate_ld_deductions(exec_data["project_id"])
            if intermediate_ld > 0:
                return ComplianceEvent(
                    check_id="C05", severity="INFO",
                    title="Catch-Up Clause Triggered — LD Refund Due",
                    clause="NITI Aayog Article 10.3.3",
                    description=f"Contractor achieved final Scheduled Completion Date on time. "
                                f"₹{intermediate_ld:,.0f} in intermediate milestone LDs must be refunded without interest.",
                    financial_impact=-intermediate_ld,  # negative = refund
                    action="PROCESS_LD_REFUND"
                )
```

---

### CHECK 07 — Quality: NCR Status

```python
def check_quality(exec_data, rule_store):
    events = []

    # Test failure rate
    if exec_data["test_fail_rate_pct"] > 10:
        events.append(ComplianceEvent(
            check_id="C07a", severity="HIGH",
            title=f"High QA Failure Rate: {exec_data['test_fail_rate_pct']:.1f}%",
            clause="NITI Aayog Article 11.14 / CPWD Clause 16",
            description="Test failure rate exceeds 10%. Non-Conformance Reports must be issued. "
                        "Contractor must demolish and reconstruct affected works.",
            action="ISSUE_NCR_WITHHOLD_PAYMENT"
        ))

    # Stale NCRs
    for ncr in get_open_ncrs(exec_data["project_id"]):
        age_days = (today - ncr["issued_date"]).days
        if age_days > ncr["rectification_deadline_days"]:
            events.append(ComplianceEvent(
                check_id="C07b", severity="HIGH",
                title=f"NCR {ncr['id']} Not Rectified — {age_days} Days Old",
                clause="NITI Aayog Article 11.14",
                description=f"NCR for {ncr['defect']} issued {age_days} days ago. "
                            f"Deadline was {ncr['rectification_deadline_days']} days. "
                            f"Authority may now suspend related works and hire third party.",
                action="SUSPEND_WORK_HIRE_THIRD_PARTY"
            ))
    return events
```

---

### CHECK 10 — EoT Application Timeliness

```python
def check_eot_timeliness(exec_data, rule_store):
    """
    CPWD Clause 5: EoT application must be filed within 14 days of hindrance.
    If missed, the EoT claim is legally forfeit.
    """
    events = []
    for hindrance in get_hindrances(exec_data["project_id"]):
        deadline = hindrance["date_of_occurrence"] + timedelta(days=14)
        if hindrance["eot_application_submitted"]:
            if hindrance["eot_application_date"] > deadline:
                events.append(ComplianceEvent(
                    check_id="C10", severity="MEDIUM",
                    title=f"Late EoT Application for Hindrance {hindrance['hindrance_id']}",
                    clause="CPWD GCC Clause 5",
                    description=f"EoT application was submitted {(hindrance['eot_application_date'] - deadline).days} days late. "
                                f"Claim may be rejected under Clause 5.",
                    action="FLAG_FOR_ENGINEER_REVIEW"
                ))
        elif today > deadline and not hindrance["eot_application_submitted"]:
            events.append(ComplianceEvent(
                check_id="C10", severity="HIGH",
                title=f"EoT Claim Window Missed for Hindrance {hindrance['hindrance_id']}",
                clause="CPWD GCC Clause 5",
                description=f"Hindrance '{hindrance['nature_of_hindrance']}' occurred on "
                            f"{hindrance['date_of_occurrence']}. The 14-day window to apply for EoT "
                            f"expired on {deadline.date()}. No EoT can now be claimed for this period.",
                action="LD_APPLIES_NO_EOT_ELIGIBLE"
            ))
    return events
```

---

### CHECK 11 — Force Majeure Validity

```python
def check_force_majeure(fm_claim, rule_store, weather_tool):
    """
    Validates FM claims against contractual requirements.
    Uses real weather API to cross-check weather-based claims.
    """
    events = []

    # Rule 1: 7-day notice requirement
    notice_deadline = fm_claim["event_date"] + timedelta(days=7)
    if fm_claim["notice_submitted_date"] > notice_deadline:
        return ComplianceEvent(
            check_id="C11a", severity="HIGH",
            title="FM Notice Filed Late — Relief Forfeited",
            clause="NITI Aayog Article 19.1",
            description=f"FM notice was due by {notice_deadline.date()} but filed on "
                        f"{fm_claim['notice_submitted_date']}. Contractor has forfeited right to FM relief.",
            action="REJECT_FM_CLAIM"
        )

    # Rule 2: Weather-based FM — cross-check with IMD data
    if fm_claim["category"] == "FORCE_MAJEURE_WEATHER":
        weather_data = weather_tool.get(location=fm_claim["location"], date=fm_claim["event_date"])
        if weather_data["rainfall_mm"] < 100:  # threshold for "abnormal"
            events.append(ComplianceEvent(
                check_id="C11b", severity="MEDIUM",
                title="FM Weather Claim — Insufficient Evidence",
                clause="NITI Aayog Article 19",
                description=f"Contractor claims weather FM on {fm_claim['event_date']}. "
                            f"IMD data shows {weather_data['rainfall_mm']}mm — within seasonal norms. "
                            f"IMD certification of statistical abnormality required.",
                action="REQUEST_IMD_CERTIFICATE"
            ))

    # Rule 3: Continuous FM — check 180-day termination threshold
    fm_duration_days = (today - fm_claim["event_date"]).days
    if fm_duration_days > 120:
        events.append(ComplianceEvent(
            check_id="C11c", severity="HIGH",
            title=f"FM Event Ongoing for {fm_duration_days} Days — Approaching Termination Threshold",
            clause="NITI Aayog Article 19",
            description=f"Force Majeure has been active for {fm_duration_days} days. "
                        f"Either party may issue termination notice after 180 continuous days.",
            action="ALERT_BOTH_PARTIES"
        ))

    return events
```

---

### CHECK 15 — Termination Threshold

```python
def check_termination_proximity(exec_data, rule_store):
    events = []

    # Days beyond scheduled completion
    if exec_data["day_number"] > rule_store["milestones"][-1]["trigger_day"]:
        days_beyond = exec_data["day_number"] - rule_store["milestones"][-1]["trigger_day"]
        eot_granted = exec_data.get("eot_granted_days", 0)
        net_days_beyond = max(0, days_beyond - eot_granted)

        if net_days_beyond >= 90:
            events.append(ComplianceEvent(
                check_id="C15", severity="CRITICAL",
                title="Contractor Default — 90-Day Termination Threshold Breached",
                clause="NITI Aayog Article 23.1.1(c)",
                description=f"Contractor is {net_days_beyond} days beyond the Scheduled Completion Date "
                            f"(net of {eot_granted} EoT days). This constitutes Contractor Default. "
                            f"Authority has right to terminate, forfeit Performance Security, and expel contractor.",
                action="ISSUE_NOTICE_OF_INTENT_TO_TERMINATE",
                cure_period_days=60
            ))
        elif net_days_beyond >= 60:
            events.append(ComplianceEvent(
                check_id="C15", severity="HIGH",
                title=f"Warning: {net_days_beyond} Days Beyond Completion — Default Risk",
                clause="NITI Aayog Article 23",
                description=f"Project is {net_days_beyond} days delayed beyond the Scheduled Completion Date. "
                            f"Termination threshold is 90 days. {90 - net_days_beyond} days remaining.",
                action="ALERT_PROJECT_MANAGER_ESCALATE"
            ))
    return events
```

---

## Compliance Event Schema

Every check produces zero or more `ComplianceEvent` objects:

```json
{
  "event_id": "EVT-2025-05-001",
  "project_id": "CONTRACT_001",
  "check_id": "C03_M1",
  "severity": "HIGH",
  "status": "OPEN",
  "created_date": "2025-06-01",
  "title": "Project Milestone-I Missed",
  "clause": "NITI Aayog Article 10.3.1",
  "description": "Required 20% progress by Day 204. Actual: 16.2%. Shortfall: 3.8%. Delay: 22 days.",
  "ld_accrued_inr": 550000,
  "ld_daily_rate_inr": 25000,
  "catch_up_refund_eligible": true,
  "financial_impact": -550000,
  "action": "DEDUCT_LD_NOTIFY_CONTRACTOR",
  "cure_period_days": 60,
  "cure_deadline": "2025-07-31",
  "assigned_to": "contractor_001",
  "resolved_date": null,
  "resolution_notes": null
}
```

**Severity Levels:**

| Severity | Meaning | Dashboard Colour |
|---|---|---|
| `INFO` | Positive event (refund, bonus due) | Green |
| `LOW` | Advisory — no immediate penalty | Blue |
| `MEDIUM` | Procedural breach, warning issued | Yellow |
| `HIGH` | Active violation, LD or NCR active | Orange |
| `CRITICAL` | Default threshold reached, termination risk | Red |

---

## LD Ledger

All LD deductions across all checks are accumulated in a per-project ledger:

```json
{
  "project_id": "CONTRACT_001",
  "contract_value_inr": 250000000,
  "max_ld_inr": 25000000,
  "entries": [
    {
      "date": "2025-06-01",
      "check_id": "C03_M1",
      "event": "Milestone-I missed — Day 22 of delay",
      "ld_today_inr": 550000,
      "cumulative_ld_inr": 550000,
      "cap_utilised_pct": 2.2
    }
  ],
  "total_ld_deducted_inr": 550000,
  "total_ld_refunded_inr": 0,
  "net_ld_inr": 550000,
  "cap_utilised_pct": 2.2
}
```

---

## Escalation Matrix (Dispute Resolution)

When a contractor contests a compliance event, the Escalation Agent tracks:

### EPC Track (NITI Aayog Article 26)
```
Day 0:    Contractor contests → Amicable Conciliation triggered
Day 30:   If unresolved → Arbitration (3-member tribunal)
Day 30+:  Authority may continue with site takeover during arbitration
```

### Item Rate Track (CPWD GCC Clause 25)
```
Day 0:    Contractor appeals to Superintending Engineer (SE)
           → Must file within 15 days of penal order
Day 30:   SE must give written decision
Day 45:   If rejected → Dispute Redressal Committee (DRC)
           → Must file within 15 days of SE decision
Day 135:  DRC issues decision (90 days max, +30 days extension)
Day 165:  If rejected → Arbitration
           → Must file within 30 days of DRC decision
           → Missed window = DRC decision is final and binding
```

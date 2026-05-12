"""
Compliance Engine — 15 Deterministic Checks
Per EL/03_COMPLIANCE_ENGINE.md
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Optional


# ── Compliance Event ───────────────────────────────────────────────────

@dataclass
class ComplianceEvent:
    check_id: str
    severity: str          # CRITICAL | HIGH | MEDIUM | LOW | INFO
    title: str
    clause: str
    description: str
    action: str
    financial_impact_inr: float = 0.0
    ld_accrued_inr: float = 0.0
    ld_daily_rate_inr: float = 0.0
    catch_up_refund_eligible: bool = False
    metadata: dict = field(default_factory=dict)


def _parse_date(d) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, (date, datetime)):
        return d.date() if isinstance(d, datetime) else d
    try:
        return date.fromisoformat(str(d))
    except Exception:
        return None


# ── CHECK 01 — Performance Security ───────────────────────────────────

def check_performance_security(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    ps = rule_store.get("performance_security") or {}
    appointed = _parse_date(exec_data.get("appointed_date"))
    if not appointed:
        return None

    deadline_days = ps.get("submission_deadline_days") or 15
    ext_days = ps.get("max_extension_days") or 15
    deadline = appointed + timedelta(days=deadline_days)
    max_deadline = deadline + timedelta(days=ext_days)
    amount = ps.get("amount_inr") or (
        (rule_store.get("contract_value_inr") or 0) * (ps.get("pct_of_contract_value") or 5) / 100
    )
    submitted = exec_data.get("performance_security_submitted", False)
    sub_date = _parse_date(exec_data.get("ps_submission_date"))

    if submitted and sub_date:
        if sub_date > deadline:
            late_days = (sub_date - deadline).days
            late_fee = late_days * ((ps.get("late_fee_pct_per_day") or 0.1) / 100) * amount
            return ComplianceEvent(
                check_id="C01", severity="MEDIUM",
                title=f"Late Performance Security Submission ({late_days} days)",
                clause="CPWD GCC Clause 1",
                description=f"Performance Security submitted {late_days} days late (deadline: {deadline}). Late fee applicable.",
                financial_impact_inr=late_fee,
                action="DEDUCT_LATE_FEE",
            )
    elif not submitted:
        if today > max_deadline:
            return ComplianceEvent(
                check_id="C01", severity="CRITICAL",
                title="Performance Security NOT Submitted — LoA Deemed Cancelled",
                clause="CPWD GCC Clause 1",
                description=f"Performance Security not submitted within extended deadline ({max_deadline}). LoA deemed cancelled, EMD forfeited.",
                financial_impact_inr=amount,
                action="CANCEL_LOA_FORFEIT_EMD",
            )
        elif today > deadline:
            return ComplianceEvent(
                check_id="C01", severity="HIGH",
                title="Performance Security Overdue — Grace Period Active",
                clause="CPWD GCC Clause 1",
                description=f"Performance Security not submitted (deadline: {deadline}). {(max_deadline - today).days} days remaining in grace period.",
                action="URGENT_REMINDER_TO_CONTRACTOR",
            )
    return None


# ── CHECK 02 — Conditions Precedent ────────────────────────────────────

def check_conditions_precedent(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    row_pct = exec_data.get("row_handover_pct", 0)
    if row_pct < 80:
        events.append(ComplianceEvent(
            check_id="C02a", severity="HIGH",
            title=f"Right of Way Handover Incomplete ({row_pct:.1f}%)",
            clause="NITI Aayog Article 4",
            description=f"Only {row_pct:.1f}% of Right of Way has been handed over. Work cannot proceed fully.",
            action="EXPEDITE_ROW_HANDOVER",
        ))
    if not exec_data.get("appointed_date"):
        events.append(ComplianceEvent(
            check_id="C02b", severity="MEDIUM",
            title="Appointed Date Not Set",
            clause="NITI Aayog Article 4",
            description="Appointed Date has not been recorded. SCP clock cannot start.",
            action="RECORD_APPOINTED_DATE",
        ))
    return events


# ── CHECK 03 — Milestone Progress ──────────────────────────────────────

def check_milestones(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    milestones = rule_store.get("milestones") or []
    contract_type = rule_store.get("contract_type", "EPC")
    day_number = exec_data.get("day_number", 0)
    actual_pct = exec_data.get("actual_physical_pct", 0)
    cv = rule_store.get("contract_value_inr", 0)
    ld_info = rule_store.get("liquidated_damages") or {}
    max_ld_pct = ld_info.get("max_cap_pct") or 10
    max_ld = cv * max_ld_pct / 100

    for milestone in milestones:
        trigger_day = milestone.get("trigger_day") or 0
        required_pct = milestone.get("required_physical_progress_pct") or 0
        if trigger_day and day_number >= trigger_day:
            if actual_pct < required_pct:
                shortfall = required_pct - actual_pct
                delay_days = day_number - trigger_day
                mid = milestone.get("id", "M?")

                # ── LD calculation: EPC vs Item Rate ──────────────────
                if contract_type == "ITEM_RATE":
                    # CPWD GCC Clause 2: 1%/month of tendered value (daily basis)
                    # daily_rate = 1% / 30.4 = 0.032895%/day
                    daily_rate_pct = 1.0 / 30.4 / 100  # fraction per day
                    ld_today = daily_rate_pct * cv * delay_days
                    ld_daily = daily_rate_pct * cv
                    source_clause = "CPWD GCC Clause 2"
                    catch_up = False
                else:
                    # NITI Aayog EPC: 0.05%/day of apportioned or total value
                    if milestone.get("ld_basis") == "apportioned_milestone_value" and milestone.get("id") != "M4":
                        ld_basis_pct = milestone.get("required_physical_progress_pct") or 100
                        basis = cv * (ld_basis_pct / 100)
                    else:
                        basis = cv  # M4 and all "total_contract_price" basis milestones use full CV
                    ld_rate = (milestone.get("ld_rate_pct_per_day") or 0.05) / 100
                    ld_today = ld_rate * basis * delay_days
                    ld_daily = ld_rate * basis
                    source_clause = milestone.get("source_clause", "Article 10.3.1")
                    catch_up = milestone.get("catch_up_refund_eligible", False)

                ld_capped = min(ld_today, max_ld)
                severity = "CRITICAL" if mid == "M4" else "HIGH"

                events.append(ComplianceEvent(
                    check_id=f"C03_{mid}",
                    severity=severity,
                    title=f"{milestone.get('name', mid)} Missed",
                    clause=source_clause,
                    description=(
                        f"Required {required_pct}% progress by Day {trigger_day}. "
                        f"Actual: {actual_pct:.1f}%. Shortfall: {shortfall:.1f}%. "
                        f"Delay: {delay_days} days."
                    ),
                    ld_accrued_inr=ld_capped,
                    ld_daily_rate_inr=ld_daily,
                    catch_up_refund_eligible=catch_up,
                    action="DEDUCT_LD_NOTIFY_CONTRACTOR",
                    metadata={"ld_uncapped": ld_today, "ld_capped": ld_capped, "contract_type": contract_type},
                ))
    return events


# ── CHECK 04 — LD Cap Proximity ────────────────────────────────────────

def check_ld_cap(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    ld_info = rule_store.get("liquidated_damages") or {}
    cv = rule_store.get("contract_value_inr", 0)
    max_ld = ld_info.get("max_cap_inr") or (cv * (ld_info.get("max_cap_pct") or 10) / 100)
    accumulated = exec_data.get("ld_accumulated_inr", 0)
    if max_ld <= 0:
        return None
    cap_pct = (accumulated / max_ld) * 100

    if cap_pct >= 100:
        return ComplianceEvent(
            check_id="C04", severity="CRITICAL",
            title="LD Cap Exhausted — Contractor Default",
            clause="Article 10.3.2 / CPWD Clause 2",
            description=f"Accumulated LD Rs.{accumulated:,.0f} has reached the 10% cap of Rs.{max_ld:,.0f}. Contractor Default.",
            action="ISSUE_NOTICE_OF_DEFAULT",
        )
    elif cap_pct >= 80:
        return ComplianceEvent(
            check_id="C04", severity="HIGH",
            title=f"LD Cap at {cap_pct:.1f}% — Warning",
            clause="Article 10.3.2",
            description=f"Accumulated LD Rs.{accumulated:,.0f} ({cap_pct:.1f}% of cap). Rs.{max_ld - accumulated:,.0f} remaining before default.",
            action="ALERT_PROJECT_MANAGER",
        )
    return None


# ── CHECK 05 — Catch-Up Refund ─────────────────────────────────────────

def check_catchup_refund(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    if rule_store.get("contract_type") != "EPC":
        return None
    milestones = rule_store.get("milestones") or []
    if not milestones:
        return None
    final = milestones[-1]
    day_number = exec_data.get("day_number", 0)
    actual_pct = exec_data.get("actual_physical_pct", 0)
    if day_number >= (final.get("trigger_day") or 999999) and actual_pct >= 100:
        intermediate_ld = exec_data.get("intermediate_ld_deducted_inr", 0)
        if intermediate_ld > 0:
            return ComplianceEvent(
                check_id="C05", severity="INFO",
                title="Catch-Up Clause Triggered — LD Refund Due",
                clause="NITI Aayog Article 10.3.3",
                description=f"Contractor achieved final completion on time. Rs.{intermediate_ld:,.0f} in intermediate LDs must be refunded without interest.",
                financial_impact_inr=-intermediate_ld,
                action="PROCESS_LD_REFUND",
            )
    return None


# ── CHECK 06 — Labour & Machinery Adequacy ─────────────────────────────

def check_labour_machinery(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    labour_pct = exec_data.get("labour_deployment_pct", 100)
    machinery_pct = exec_data.get("machinery_deployment_pct", 100)
    if labour_pct < 70:
        events.append(ComplianceEvent(
            check_id="C06a", severity="MEDIUM",
            title=f"Labour Under-Deployment ({labour_pct:.0f}% of planned)",
            clause="Article 10 / CPWD Clause 5",
            description=f"Only {labour_pct:.0f}% of planned labour deployed. Risk of milestone slippage.",
            action="ISSUE_SHOW_CAUSE_NOTICE",
        ))
    if machinery_pct < 70:
        events.append(ComplianceEvent(
            check_id="C06b", severity="MEDIUM",
            title=f"Machinery Under-Deployment ({machinery_pct:.0f}% of planned)",
            clause="Article 10 / CPWD Clause 5",
            description=f"Only {machinery_pct:.0f}% of planned machinery deployed.",
            action="ISSUE_SHOW_CAUSE_NOTICE",
        ))
    return events


# ── CHECK 07 — Quality / NCR Status ───────────────────────────────────

def check_quality(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    fail_rate = exec_data.get("test_fail_rate_pct", 0)
    if fail_rate > 10:
        events.append(ComplianceEvent(
            check_id="C07a", severity="HIGH",
            title=f"High QA Failure Rate: {fail_rate:.1f}%",
            clause="NITI Aayog Article 11.14 / CPWD Clause 16",
            description=f"Test failure rate {fail_rate:.1f}% exceeds 10%. NCRs must be issued.",
            action="ISSUE_NCR_WITHHOLD_PAYMENT",
        ))
    open_ncrs = exec_data.get("open_ncrs", [])
    for ncr in open_ncrs:
        issued = _parse_date(ncr.get("issued_date"))
        deadline_days = ncr.get("rectification_deadline_days", 30)
        if issued:
            age = (today - issued).days
            if age > deadline_days:
                events.append(ComplianceEvent(
                    check_id="C07b", severity="HIGH",
                    title=f"NCR {ncr.get('id','?')} Overdue — {age} Days",
                    clause="NITI Aayog Article 11.14",
                    description=f"NCR for '{ncr.get('defect','')}' issued {age} days ago. Deadline was {deadline_days} days.",
                    action="SUSPEND_WORK_HIRE_THIRD_PARTY",
                ))
    return events


# ── CHECK 08 — GFC Drawing Backlog ────────────────────────────────────

def check_gfc_drawings(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    pending = exec_data.get("gfc_drawings_pending", 0)
    if pending > 5:
        return ComplianceEvent(
            check_id="C08", severity="MEDIUM",
            title=f"{pending} GFC Drawings Pending",
            clause="Article 10 / Contract Schedule",
            description=f"{pending} Good-for-Construction drawings awaiting approval. May impede work.",
            action="EXPEDITE_GFC_APPROVAL",
        )
    return None


# ── CHECK 09 — Hindrance Register Completeness ────────────────────────

def check_hindrance_register(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    unsigned = exec_data.get("hindrance_register_unsigned_entries", 0)
    if unsigned > 0:
        return ComplianceEvent(
            check_id="C09", severity="MEDIUM",
            title=f"Hindrance Register: {unsigned} Unsigned Entries",
            clause="CPWD GCC Clause 5",
            description=f"{unsigned} hindrance register entries not co-signed by JE/AE. These entries are inadmissible for EoT claims.",
            action="GET_HINDRANCE_REGISTER_SIGNED",
        )
    return None


# ── CHECK 10 — EoT Application Timeliness ─────────────────────────────

def check_eot_timeliness(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    deadline_days = (rule_store.get("eot_rules") or {}).get("application_deadline_days") or 14
    for hindrance in exec_data.get("hindrances", []):
        occurred = _parse_date(hindrance.get("date_of_occurrence"))
        if not occurred:
            continue
        deadline = occurred + timedelta(days=deadline_days)
        submitted = hindrance.get("eot_application_submitted", False)
        app_date = _parse_date(hindrance.get("eot_application_date"))
        hid = hindrance.get("hindrance_id", "H?")
        if submitted and app_date and app_date > deadline:
            late = (app_date - deadline).days
            events.append(ComplianceEvent(
                check_id="C10", severity="MEDIUM",
                title=f"Late EoT Application for Hindrance {hid} ({late} days)",
                clause="CPWD GCC Clause 5",
                description=f"EoT application submitted {late} days after the 14-day deadline. Claim may be rejected.",
                action="FLAG_FOR_ENGINEER_REVIEW",
            ))
        elif not submitted and today > deadline:
            events.append(ComplianceEvent(
                check_id="C10", severity="HIGH",
                title=f"EoT Window Missed for Hindrance {hid}",
                clause="CPWD GCC Clause 5",
                description=f"Hindrance '{hindrance.get('nature','')}' on {occurred}. 14-day window expired {deadline}. No EoT claimable.",
                action="LD_APPLIES_NO_EOT_ELIGIBLE",
            ))
    return events


# ── CHECK 11 — Force Majeure Claim Validity ────────────────────────────

def check_force_majeure(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    fm_rules = rule_store.get("force_majeure") or {}
    notice_deadline = fm_rules.get("notice_deadline_days") or 7
    for fm in exec_data.get("force_majeure_events", []):
        occurred = _parse_date(fm.get("date_of_occurrence"))
        notice_date = _parse_date(fm.get("notice_submitted_date"))
        fid = fm.get("event_id", "FM?")
        if occurred:
            deadline = occurred + timedelta(days=notice_deadline)
            if not notice_date:
                events.append(ComplianceEvent(
                    check_id="C11a", severity="HIGH",
                    title=f"Force Majeure Notice Not Submitted for {fid}",
                    clause="NITI Aayog Article 19.1",
                    description=f"FM event '{fm.get('description','')}' on {occurred}. Notice must be filed within {notice_deadline} days.",
                    action="FILE_FM_NOTICE_IMMEDIATELY",
                ))
            elif notice_date > deadline:
                late = (notice_date - deadline).days
                events.append(ComplianceEvent(
                    check_id="C11b", severity="HIGH",
                    title=f"Late Force Majeure Notice for {fid} ({late} days)",
                    clause="NITI Aayog Article 19.1",
                    description=f"FM notice submitted {late} days late. All FM relief for this event may be forfeited.",
                    action="FLAG_DISPUTED_FM_CLAIM",
                ))
    return events


# ── CHECK 12 — Variation Order Claim Timeliness ────────────────────────

def check_variation_orders(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    vo_rules = rule_store.get("variation_orders") or {}
    claim_deadline = vo_rules.get("claim_notice_deadline_days") or 14
    for vo in exec_data.get("variation_orders", []):
        issued = _parse_date(vo.get("vo_issued_date"))
        claim_date = _parse_date(vo.get("claim_submitted_date"))
        vid = vo.get("vo_id", "VO?")
        if issued:
            deadline = issued + timedelta(days=claim_deadline)
            if not claim_date and today > deadline:
                events.append(ComplianceEvent(
                    check_id="C12", severity="MEDIUM",
                    title=f"VO Claim Window Missed for {vid}",
                    clause="Article 13 / Clause 12",
                    description=f"Variation Order {vid} issued {issued}. Claim deadline was {deadline}.",
                    action="DOCUMENT_LATE_CLAIM_RISK",
                ))
    return events


# ── CHECK 13 — RA Bill Payment Cycle (C13a / C13b / C13c) ─────────────
# Per EL next_action_plan.md and CPWD Clause 7 / Article 22.2

def check_payment_cycle(exec_data: dict, rule_store: dict, today: date) -> list[ComplianceEvent]:
    events = []
    pw = rule_store.get("payment_workflow") or {}
    verify_days = pw.get("verification_deadline_days") or 15
    release_days = pw.get("payment_release_deadline_days") or 30
    interest_rate_monthly = 0.01  # 1% per month per Article 22.2 / CPWD Clause 7

    for bill in exec_data.get("ra_bills", []):
        submitted = _parse_date(bill.get("submitted_date"))
        if not submitted:
            continue
        verify_deadline = submitted + timedelta(days=verify_days)
        release_deadline = submitted + timedelta(days=release_days)
        bid = bill.get("bill_id", "RA?")
        amount = bill.get("amount_inr", 0)

        # C13a — Payment delayed beyond 30 days → interest at 1%/month (Article 22.2)
        paid_date = _parse_date(bill.get("paid_date"))
        if bill.get("verified") and not bill.get("paid") and today > release_deadline:
            overdue = (today - release_deadline).days
            interest = amount * interest_rate_monthly / 30 * overdue
            events.append(ComplianceEvent(
                check_id="C13a", severity="HIGH",
                title=f"RA Bill {bid} Payment Overdue ({overdue} days) — Interest Accruing",
                clause="CPWD Clause 7 / Article 22.2",
                description=(
                    f"Bill {bid} (Rs.{amount:,.0f}) verified but payment not released. "
                    f"{overdue} days past 30-day deadline. Contractor entitled to interest: "
                    f"Rs.{interest:,.0f} @ 1% per month (Article 22.2)."
                ),
                financial_impact_inr=interest,
                action="RELEASE_PAYMENT_IMMEDIATELY",
            ))
        elif not bill.get("verified") and today > verify_deadline:
            overdue = (today - verify_deadline).days
            events.append(ComplianceEvent(
                check_id="C13a", severity="MEDIUM",
                title=f"RA Bill {bid} Verification Overdue ({overdue} days)",
                clause="CPWD Clause 7",
                description=f"Bill {bid} submitted {submitted}. Verification deadline {verify_deadline} missed by {overdue} days.",
                action="ESCALATE_TO_SE_FOR_VERIFICATION",
            ))

    # C13b — Retention not released after DLP expiry
    dlp_end = _parse_date(exec_data.get("dlp_end_date"))
    retention_released = exec_data.get("retention_released", False)
    total_retention = exec_data.get("total_retention_withheld_inr", 0)
    if dlp_end and today > dlp_end and not retention_released and total_retention > 0:
        overdue = (today - dlp_end).days
        events.append(ComplianceEvent(
            check_id="C13b", severity="HIGH",
            title=f"Retention Money Not Released — {overdue} Days Past DLP Expiry",
            clause="CPWD Clause 7",
            description=(
                f"Defects Liability Period ended {dlp_end}. Retention of Rs.{total_retention:,.0f} "
                f"not yet released to contractor. {overdue} days overdue."
            ),
            financial_impact_inr=total_retention,
            action="RELEASE_RETENTION_MONEY",
        ))

    # C13c — Mobilisation advance recovery not on track
    mob_advance = exec_data.get("mobilisation_advance_inr", 0)
    mob_recovered_pct = exec_data.get("mob_advance_recovered_pct", 100.0)
    actual_pct = exec_data.get("actual_physical_pct", 0)
    # Per standard: recovery should be proportional to progress (linear from 10% to 80% progress)
    if mob_advance > 0 and actual_pct >= 10:
        expected_recovery_pct = min(100.0, (actual_pct - 10) / 70 * 100) if actual_pct > 10 else 0
        if mob_recovered_pct < expected_recovery_pct - 10:  # 10% tolerance
            shortfall_inr = mob_advance * (expected_recovery_pct - mob_recovered_pct) / 100
            events.append(ComplianceEvent(
                check_id="C13c", severity="MEDIUM",
                title=f"Mobilisation Advance Recovery Behind Schedule",
                clause="CPWD Clause 7",
                description=(
                    f"Mob. advance of Rs.{mob_advance:,.0f}: expected {expected_recovery_pct:.0f}% recovered "
                    f"at current progress ({actual_pct:.1f}%), actual only {mob_recovered_pct:.0f}%. "
                    f"Shortfall: Rs.{shortfall_inr:,.0f} to deduct."
                ),
                financial_impact_inr=shortfall_inr,
                action="DEDUCT_MOB_ADVANCE_RECOVERY",
            ))

    return events


# ── CHECK 14 — Early Completion Bonus ─────────────────────────────────

def check_bonus_eligibility(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    bonus = rule_store.get("bonus") or {}
    if not bonus.get("applicable"):
        return None
    milestones = rule_store.get("milestones") or []
    if not milestones:
        return None
    final = milestones[-1]
    day_number = exec_data.get("day_number", 0)
    actual_pct = exec_data.get("actual_physical_pct", 0)
    scp_days = rule_store.get("scp_days") or 730
    if actual_pct >= 100 and day_number < (final.get("trigger_day") or scp_days):
        early_days = (final.get("trigger_day") or scp_days) - day_number
        early_months = early_days / 30
        cv = rule_store.get("contract_value_inr", 0)
        rate = (bonus.get("rate_pct_per_month") or 1) / 100
        cap_pct = (bonus.get("max_cap_pct") or 5) / 100
        bonus_amount = min(rate * cv * early_months, cap_pct * cv)
        return ComplianceEvent(
            check_id="C14", severity="INFO",
            title=f"Early Completion Bonus Eligible — Rs.{bonus_amount:,.0f}",
            clause="CPWD Clause 2A",
            description=f"Project completed {early_days} days early ({early_months:.1f} months). Bonus of Rs.{bonus_amount:,.0f} due with Final Bill.",
            financial_impact_inr=-bonus_amount,
            action="PROCESS_EARLY_COMPLETION_BONUS",
        )
    return None


# ── CHECK 15 — Termination Threshold Proximity ────────────────────────
# EPC: 90 days beyond SCD → Notice of Intent to Terminate (Article 23.1.1)
# Item Rate: 7-day Show Cause Notice on default (CPWD Clause 3)

def check_termination_proximity(exec_data: dict, rule_store: dict, today: date) -> Optional[ComplianceEvent]:
    contract_type = rule_store.get("contract_type", "EPC")
    term = rule_store.get("termination") or {}
    triggers = term.get("contractor_default_triggers") or []
    day_number = exec_data.get("day_number", 0)
    milestones = rule_store.get("milestones") or []
    final_day = milestones[-1].get("trigger_day") if milestones else None
    if not final_day:
        return None

    if day_number > final_day:
        overrun = day_number - final_day
        eot_granted = exec_data.get("eot_granted_days", 0)
        net_overrun = max(0, overrun - eot_granted)

        if contract_type == "ITEM_RATE":
            # CPWD Clause 3: 7-day show cause notice on default; no fixed 90-day threshold
            if net_overrun >= 14:  # 14 days beyond SCD — mandatory show cause
                return ComplianceEvent(
                    check_id="C15", severity="CRITICAL",
                    title=f"Item Rate Default — {net_overrun} Days Beyond SCD — Show Cause Notice Required",
                    clause="CPWD GCC Clause 3",
                    description=(
                        f"Contractor is {net_overrun} days beyond Scheduled Completion Date (net of "
                        f"{eot_granted} EoT days). Under CPWD Clause 3, a 7-day Show Cause Notice "
                        f"must be issued. If response unsatisfactory, contract may be determined."
                    ),
                    action="ISSUE_7DAY_SHOW_CAUSE_NOTICE",
                    metadata={"notice_response_deadline_days": 7},
                )
            elif net_overrun >= 7:
                return ComplianceEvent(
                    check_id="C15", severity="HIGH",
                    title=f"Warning: {net_overrun} Days Beyond SCD — Show Cause Notice Imminent",
                    clause="CPWD GCC Clause 3",
                    description=(
                        f"Contractor is {net_overrun} days delayed beyond SCD. "
                        f"Show Cause Notice threshold (14 days) approaches in {14 - net_overrun} days."
                    ),
                    action="ALERT_PROJECT_MANAGER_ESCALATE",
                )
        else:
            # EPC: Article 23.1.1 — 90 days net of EoT
            threshold = 90
            for t in triggers:
                if t.get("trigger") == "delay_beyond_completion":
                    threshold = t.get("threshold_days") or 90
                    break
            if net_overrun >= threshold:
                return ComplianceEvent(
                    check_id="C15", severity="CRITICAL",
                    title=f"EPC Contractor Default — {net_overrun} Days Beyond SCD (net of EoT)",
                    clause="NITI Aayog Article 23.1.1(c)",
                    description=(
                        f"Contractor is {net_overrun} days beyond SCD (net of {eot_granted} EoT days). "
                        f"This constitutes Contractor Default under Article 23. Authority may issue "
                        f"Notice of Intent to Terminate and forfeit Performance Security."
                    ),
                    action="ISSUE_NOTICE_OF_INTENT_TO_TERMINATE",
                    metadata={"cure_period_days": 60},
                )
            elif net_overrun >= threshold * 0.67:  # 60 days — warning
                return ComplianceEvent(
                    check_id="C15", severity="HIGH",
                    title=f"Warning: {net_overrun}/{threshold} Days Beyond SCD — Default Risk",
                    clause="NITI Aayog Article 23",
                    description=(
                        f"Project is {net_overrun} days delayed. Termination threshold is {threshold} days. "
                        f"{threshold - net_overrun} days remaining."
                    ),
                    action="ALERT_PROJECT_MANAGER_ESCALATE",
                )
    return None


# ── Master compliance runner ───────────────────────────────────────────

def run_all_checks(exec_data: dict, rule_store: dict) -> dict:
    """Run all 15 compliance checks. Returns structured compliance report."""
    today = _parse_date(exec_data.get("report_date")) or date.today()
    events: list[ComplianceEvent] = []

    def _add(result):
        if result is None:
            return
        if isinstance(result, list):
            events.extend(result)
        else:
            events.append(result)

    _add(check_performance_security(exec_data, rule_store, today))
    _add(check_conditions_precedent(exec_data, rule_store, today))
    _add(check_milestones(exec_data, rule_store, today))
    _add(check_ld_cap(exec_data, rule_store, today))
    _add(check_catchup_refund(exec_data, rule_store, today))
    _add(check_labour_machinery(exec_data, rule_store, today))
    _add(check_quality(exec_data, rule_store, today))
    _add(check_gfc_drawings(exec_data, rule_store, today))
    _add(check_hindrance_register(exec_data, rule_store, today))
    _add(check_eot_timeliness(exec_data, rule_store, today))
    _add(check_force_majeure(exec_data, rule_store, today))
    _add(check_variation_orders(exec_data, rule_store, today))
    _add(check_payment_cycle(exec_data, rule_store, today))
    _add(check_bonus_eligibility(exec_data, rule_store, today))
    _add(check_termination_proximity(exec_data, rule_store, today))

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    events.sort(key=lambda e: severity_order.get(e.severity, 9))

    total_ld = sum(e.ld_accrued_inr for e in events)
    total_financial = sum(e.financial_impact_inr for e in events)
    critical_count = sum(1 for e in events if e.severity == "CRITICAL")
    high_count = sum(1 for e in events if e.severity == "HIGH")

    return {
        "project_id": exec_data.get("project_id"),
        "contract_id": exec_data.get("contract_id"),
        "report_date": str(today),
        "reporting_period": exec_data.get("reporting_period"),
        "day_number": exec_data.get("day_number"),
        "total_events": len(events),
        "critical_count": critical_count,
        "high_count": high_count,
        "total_ld_accrued_inr": total_ld,
        "total_financial_impact_inr": total_financial,
        "events": [asdict(e) for e in events],
    }

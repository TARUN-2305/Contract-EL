"""
EoT Agent — agents/eot_agent.py
Full Extension of Time decision engine per EL/05.

Handles two tracks:
  A) Hindrance-based EoT (CPWD GCC Clause 5)
  B) Force Majeure EoT (NITI Aayog Article 19)

Output: eot_decision.json per EL/05 schema + revised milestone dates.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Optional

from agents.compliance_engine import _parse_date


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class EoTDecision:
    decision_id: str
    project_id: str
    claim_type: str           # HINDRANCE | FM
    hindrance_id: Optional[str]
    decision: str             # APPROVED | PARTIALLY_APPROVED | REJECTED
    eot_days_approved: int
    eot_days_claimed: int
    rejection_reason: Optional[str]
    clause: str
    new_milestone_dates: dict
    decided_by: str = "eot_agent"
    decided_on: str = ""

    def __post_init__(self):
        if not self.decided_on:
            self.decided_on = str(date.today())


# ── Overlap-Aware EoT Calculation ─────────────────────────────────────────

def calculate_net_eot(hindrances: list, today: date = None) -> tuple[int, int]:
    """
    Compute net eligible EoT days from a list of hindrance entries.
    Merges overlapping date ranges to prevent double-counting.

    Per EL/02 and EL/05: overlap_deduction_required = True

    Returns:
        (net_eot_days, overlap_deducted_days)
    """
    today = today or date.today()
    ranges = []
    for h in hindrances:
        start = _parse_date(h.get("date_of_occurrence"))
        if not start:
            continue
            
        if h.get("status") == "OPEN":
            end = today
        else:
            end = _parse_date(h.get("date_of_removal"))
            if not end:
                end = start
                
        if end >= start:
            ranges.append((start, end))

    if not ranges:
        return 0, 0

    # Sort by start date
    ranges.sort(key=lambda x: x[0])

    # Merge overlapping intervals
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Use raw ranges for gross calc
    gross_days = 0
    for h in hindrances:
        start = _parse_date(h.get("date_of_occurrence"))
        if not start:
            continue
            
        if h.get("status") == "OPEN":
            end = today
        else:
            end = _parse_date(h.get("date_of_removal"))
            if not end:
                end = start
                
        gross_days += (end - start).days

    net_days = sum((e - s).days for s, e in merged)
    overlap_deducted = max(0, gross_days - net_days)

    return net_days, overlap_deducted


# ── Revised Milestone Dates ───────────────────────────────────────────────

def compute_revised_milestones(rule_store: dict, eot_days: int) -> dict:
    """
    Add eot_days to all milestone trigger days and SCD.
    Returns dict of {milestone_id: new_date_str} for the decision record.
    """
    appointed_date_raw = rule_store.get("appointed_date")
    appointed = _parse_date(appointed_date_raw)
    if not appointed:
        return {}

    revised = {}
    for m in rule_store.get("milestones", []):
        orig_day = m.get("trigger_day") or 0
        new_date = appointed + timedelta(days=orig_day + eot_days)
        revised[m.get("id", "?")] = str(new_date)

    return revised


# ── FM Notice Validation ──────────────────────────────────────────────────

def validate_fm_notice(fm_claim: dict, notice_deadline_days: int = 7) -> tuple[bool, Optional[str]]:
    """
    Validate FM notice against Article 19 requirements.

    Required elements (EL/05 §EoT Agent):
      1. event_description
      2. impact_assessment
      3. estimated_duration
      4. mitigation_strategy

    Returns: (is_valid, rejection_reason)
    """
    occurred = _parse_date(fm_claim.get("event_date") or fm_claim.get("date_of_occurrence"))
    notice_date = _parse_date(fm_claim.get("notice_submitted_date"))

    if not occurred:
        return False, "Event date not provided."

    if not notice_date:
        return False, "FM notice not submitted."

    deadline = occurred + timedelta(days=notice_deadline_days)
    if notice_date > deadline:
        late = (notice_date - deadline).days
        return False, f"FM notice filed {late} days late (deadline: {deadline}). All FM relief forfeited per Article 19.1."

    # Check 4 required elements
    required = ["event_description", "impact_assessment", "estimated_duration", "mitigation_strategy"]
    missing = [r for r in required if not fm_claim.get(r)]
    if missing:
        return False, f"FM notice missing required elements: {', '.join(missing)}. Claim is incomplete."

    return True, None


# ── Main EoT Agent ────────────────────────────────────────────────────────

class EoTAgent:
    """
    Processes EoT claims from the hindrance register or FM submissions.
    Produces eot_decision.json and revised milestone dates.
    """

    def process_hindrance_eot(
        self,
        project_id: str,
        hindrance_id: str,
        hindrances: list,
        rule_store: dict,
        today: date = None,
    ) -> EoTDecision:
        """
        Handle hindrance-based EoT claim (CPWD GCC Clause 5).

        Rules (per EL/05):
        1. Application filed within 14 days of hindrance?
        2. Hindrance Register jointly signed by contractor AND JE/AE?
        3. Hindrance category valid?
        4. Net eligible days = gross - overlapping days
        """
        today = today or date.today()
        eot_rules = rule_store.get("eot_rules") or {}
        deadline_days = eot_rules.get("application_deadline_days") or 14

        # Find the specific hindrance
        hindrance = next((h for h in hindrances if h.get("hindrance_id") == hindrance_id), None)
        if not hindrance:
            return EoTDecision(
                decision_id=f"EOT-{uuid.uuid4().hex[:8].upper()}",
                project_id=project_id,
                claim_type="HINDRANCE",
                hindrance_id=hindrance_id,
                decision="REJECTED",
                eot_days_approved=0,
                eot_days_claimed=0,
                rejection_reason=f"Hindrance ID '{hindrance_id}' not found in register.",
                clause="CPWD GCC Clause 5",
                new_milestone_dates={},
            )

        occurred = _parse_date(hindrance.get("date_of_occurrence"))
        app_date = _parse_date(hindrance.get("eot_application_date"))
        app_submitted = hindrance.get("eot_application_submitted", False)
        jae_signed = bool(hindrance.get("jae_signature_date"))
        claimed_days = hindrance.get("total_days") or 0

        # Rule 1: Timeliness
        if occurred:
            deadline = occurred + timedelta(days=deadline_days)
            if not app_submitted or not app_date:
                return EoTDecision(
                    decision_id=f"EOT-{uuid.uuid4().hex[:8].upper()}",
                    project_id=project_id,
                    claim_type="HINDRANCE",
                    hindrance_id=hindrance_id,
                    decision="REJECTED",
                    eot_days_approved=0,
                    eot_days_claimed=claimed_days,
                    rejection_reason=f"EoT application not submitted. Deadline was {deadline} (14 days from hindrance).",
                    clause="CPWD GCC Clause 5",
                    new_milestone_dates={},
                )
            if app_date > deadline:
                late = (app_date - deadline).days
                return EoTDecision(
                    decision_id=f"EOT-{uuid.uuid4().hex[:8].upper()}",
                    project_id=project_id,
                    claim_type="HINDRANCE",
                    hindrance_id=hindrance_id,
                    decision="REJECTED",
                    eot_days_approved=0,
                    eot_days_claimed=claimed_days,
                    rejection_reason=f"Application filed {late} days past the 14-day deadline. Claim forfeited under CPWD Clause 5.",
                    clause="CPWD GCC Clause 5",
                    new_milestone_dates={},
                )

        # Rule 2: Joint signature
        if not jae_signed:
            return EoTDecision(
                decision_id=f"EOT-{uuid.uuid4().hex[:8].upper()}",
                project_id=project_id,
                claim_type="HINDRANCE",
                hindrance_id=hindrance_id,
                decision="REJECTED",
                eot_days_approved=0,
                eot_days_claimed=claimed_days,
                rejection_reason="Hindrance Register entry not co-signed by JE/AE. Entry inadmissible under CPWD Clause 5.",
                clause="CPWD GCC Clause 5",
                new_milestone_dates={},
            )

        # Rule 3: Valid category
        valid_categories = {
            "AUTHORITY_DEFAULT", "FORCE_MAJEURE_WEATHER",
            "FORCE_MAJEURE_POLITICAL", "STATUTORY_CLEARANCE", "UTILITY_SHIFTING"
        }
        if hindrance.get("hindrance_category") not in valid_categories:
            return EoTDecision(
                decision_id=f"EOT-{uuid.uuid4().hex[:8].upper()}",
                project_id=project_id,
                claim_type="HINDRANCE",
                hindrance_id=hindrance_id,
                decision="PARTIALLY_APPROVED",
                eot_days_approved=0,
                eot_days_claimed=claimed_days,
                rejection_reason=f"Hindrance category '{hindrance.get('hindrance_category')}' not in approved list. Requires Engineer review.",
                clause="CPWD GCC Clause 5",
                new_milestone_dates={},
            )

        # Rule 4: Overlap-aware net days
        target_start = _parse_date(hindrance.get("date_of_occurrence"))
        target_end = _parse_date(hindrance.get("date_of_removal")) or today

        # Calculate gross days for this hindrance
        gross_this = (target_end - target_start).days if target_start and target_end else 0

        # Calculate overlap with OTHER hindrances (not this one)
        other_hindrances = [h for h in hindrances if h.get("hindrance_id") != hindrance_id]
        overlap_days = 0
        for other in other_hindrances:
            other_start = _parse_date(other.get("date_of_occurrence"))
            other_end = _parse_date(other.get("date_of_removal")) or today
            if other_start and other_end and target_start and target_end:
                # Days of overlap between this hindrance and the other
                overlap_start = max(target_start, other_start)
                overlap_end = min(target_end, other_end)
                if overlap_end > overlap_start:
                    overlap_days += (overlap_end - overlap_start).days

        net_this = max(0, gross_this - overlap_days)
        approved = min(net_this, claimed_days) if claimed_days > 0 else net_this
        revised = compute_revised_milestones(rule_store, approved)

        decision = "APPROVED" if approved == claimed_days else "PARTIALLY_APPROVED"
        reason = None if decision == "APPROVED" else f"Overlap deduction of {overlap} days applied. Net approved: {approved} days."

        return EoTDecision(
            decision_id=f"EOT-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            claim_type="HINDRANCE",
            hindrance_id=hindrance_id,
            decision=decision,
            eot_days_approved=approved,
            eot_days_claimed=claimed_days,
            rejection_reason=reason,
            clause="CPWD GCC Clause 5",
            new_milestone_dates=revised,
        )

    def process_fm_eot(
        self,
        project_id: str,
        fm_claim: dict,
        rule_store: dict,
        today: date = None,
    ) -> EoTDecision:
        """
        Handle Force Majeure EoT claim (NITI Aayog Article 19).
        """
        today = today or date.today()
        fm_rules = rule_store.get("force_majeure") or {}
        notice_deadline = fm_rules.get("notice_deadline_days") or 7
        max_suspension = fm_rules.get("max_suspension_days_before_termination") or 180

        # Validate notice
        valid, reason = validate_fm_notice(fm_claim, notice_deadline_days=notice_deadline)
        if not valid:
            return EoTDecision(
                decision_id=f"EOT-FM-{uuid.uuid4().hex[:8].upper()}",
                project_id=project_id,
                claim_type="FM",
                hindrance_id=fm_claim.get("event_id"),
                decision="REJECTED",
                eot_days_approved=0,
                eot_days_claimed=fm_claim.get("claimed_days", 0),
                rejection_reason=reason,
                clause="NITI Aayog Article 19.1",
                new_milestone_dates={},
            )

        # FM duration check
        occurred = _parse_date(fm_claim.get("event_date") or fm_claim.get("date_of_occurrence"))
        fm_end = _parse_date(fm_claim.get("date_ended")) or today
        fm_days = (fm_end - occurred).days if occurred else 0
        claimed_days = fm_claim.get("claimed_days") or fm_days

        # Approaching termination (120+ days warning, 180 days right)
        if fm_days > max_suspension:
            return EoTDecision(
                decision_id=f"EOT-FM-{uuid.uuid4().hex[:8].upper()}",
                project_id=project_id,
                claim_type="FM",
                hindrance_id=fm_claim.get("event_id"),
                decision="PARTIALLY_APPROVED",
                eot_days_approved=max_suspension,
                eot_days_claimed=claimed_days,
                rejection_reason=f"FM event exceeds {max_suspension}-day limit. Either party may now terminate (Article 19).",
                clause="NITI Aayog Article 19",
                new_milestone_dates=compute_revised_milestones(rule_store, max_suspension),
            )

        revised = compute_revised_milestones(rule_store, fm_days)
        return EoTDecision(
            decision_id=f"EOT-FM-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            claim_type="FM",
            hindrance_id=fm_claim.get("event_id"),
            decision="APPROVED",
            eot_days_approved=fm_days,
            eot_days_claimed=claimed_days,
            rejection_reason=None,
            clause="NITI Aayog Article 19",
            new_milestone_dates=revised,
        )

    def save_decision(self, decision: EoTDecision, output_dir: str = "data/eot") -> str:
        """Persist EoT decision to JSON file."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"eot_{decision.project_id}_{decision.decision_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(decision), f, indent=2, default=str)
        return path


# ── CLI test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    agent = EoTAgent()

    rule_store = {
        "contract_type": "EPC",
        "contract_value_inr": 25_000_000,
        "scp_days": 730,
        "appointed_date": "2025-04-01",
        "milestones": [
            {"id": "M1", "trigger_day": 204, "required_physical_progress_pct": 20},
            {"id": "M2", "trigger_day": 401, "required_physical_progress_pct": 50},
            {"id": "M3", "trigger_day": 547, "required_physical_progress_pct": 75},
            {"id": "M4", "trigger_day": 730, "required_physical_progress_pct": 100},
        ],
        "eot_rules": {"application_deadline_days": 14},
        "force_majeure": {"notice_deadline_days": 7, "max_suspension_days_before_termination": 180},
    }

    hindrances = [
        {
            "hindrance_id": "HR-001",
            "nature_of_hindrance": "GFC Drawing Delayed",
            "hindrance_category": "AUTHORITY_DEFAULT",
            "date_of_occurrence": "2025-05-10",
            "date_of_removal": "2025-05-24",
            "total_days": 14,
            "status": "CLOSED",
            "jae_signature_date": "2025-05-10",
            "eot_application_submitted": True,
            "eot_application_date": "2025-05-20",
        },
        {
            "hindrance_id": "HR-002",
            "nature_of_hindrance": "Rainfall Disruption",
            "hindrance_category": "FORCE_MAJEURE_WEATHER",
            "date_of_occurrence": "2025-05-15",  # overlaps HR-001 by 9 days
            "date_of_removal": "2025-05-22",
            "total_days": 7,
            "status": "CLOSED",
            "jae_signature_date": "2025-05-15",
            "eot_application_submitted": True,
            "eot_application_date": "2025-05-22",
        },
    ]

    decision = agent.process_hindrance_eot("CONTRACT_001", "HR-001", hindrances, rule_store)
    print(f"✅ EoT Decision: {decision.decision}")
    print(f"   Approved: {decision.eot_days_approved} days | Claimed: {decision.eot_days_claimed} days")
    print(f"   Revised M1: {decision.new_milestone_dates.get('M1')}")
    print(f"   Revised SCD: {decision.new_milestone_dates.get('M4')}")
    if decision.rejection_reason:
        print(f"   Note: {decision.rejection_reason}")

"""
Escalation Agent — agents/escalation_agent.py
State machine per EL/05 §Escalation Agent and EL/03 §Escalation Matrix.

EPC states:    NONE → NOTICE_OF_INTENT (60d cure) → TERMINATION_NOTICE → CONCILIATION (30d) → ARBITRATION
Item Rate:     NONE → SHOW_CAUSE (7d) → CONTRACT_DETERMINED → SE_APPEAL (15d/30d) → DRC (15d/90d) → ARBITRATION (30d)

Uses Groq to draft notice template text.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from typing import Optional

from agents.compliance_engine import _parse_date
from utils.groq_client import groq_narrate


# ── State Definitions ─────────────────────────────────────────────────────

EPC_STATES = ["NONE", "NOTICE_OF_INTENT", "TERMINATION_NOTICE", "CONCILIATION", "ARBITRATION"]
ITEM_RATE_STATES = ["NONE", "SHOW_CAUSE", "CONTRACT_DETERMINED", "SE_APPEAL", "DRC", "ARBITRATION"]

EPC_TRANSITIONS = {
    "NONE": {
        "next_state": "NOTICE_OF_INTENT",
        "action": "Issue Notice of Intent to Terminate",
        "deadline_days": 60,
        "responsible_party": "Authority's Engineer / Project Manager",
        "clause": "NITI Aayog Article 23.1",
    },
    "NOTICE_OF_INTENT": {
        "next_state": "TERMINATION_NOTICE",
        "action": "Issue Final Termination Notice",
        "deadline_days": 0,
        "responsible_party": "Authority",
        "clause": "NITI Aayog Article 23.2",
    },
    "TERMINATION_NOTICE": {
        "next_state": "CONCILIATION",
        "action": "Initiate Amicable Conciliation",
        "deadline_days": 30,
        "responsible_party": "Either party",
        "clause": "NITI Aayog Article 26.1",
    },
    "CONCILIATION": {
        "next_state": "ARBITRATION",
        "action": "File for Arbitration (3-member tribunal)",
        "deadline_days": None,
        "responsible_party": "Either party",
        "clause": "NITI Aayog Article 26.3 / Arbitration & Conciliation Act 1996",
    },
    "ARBITRATION": {
        "next_state": "CLOSED",
        "action": "Await arbitration award",
        "deadline_days": None,
        "responsible_party": "Arbitral Tribunal",
        "clause": "Arbitration & Conciliation Act 1996",
    },
}

ITEM_RATE_TRANSITIONS = {
    "NONE": {
        "next_state": "SHOW_CAUSE",
        "action": "Issue 7-Day Show Cause Notice",
        "deadline_days": 7,
        "responsible_party": "Engineer-in-Charge",
        "clause": "CPWD GCC Clause 3",
    },
    "SHOW_CAUSE": {
        "next_state": "CONTRACT_DETERMINED",
        "action": "Issue Contract Determination Order",
        "deadline_days": 0,
        "responsible_party": "Superintending Engineer",
        "clause": "CPWD GCC Clause 3",
    },
    "CONTRACT_DETERMINED": {
        "next_state": "SE_APPEAL",
        "action": "Contractor may file appeal to Superintending Engineer (within 15 days)",
        "deadline_days": 15,
        "responsible_party": "Contractor",
        "clause": "CPWD GCC Clause 25",
    },
    "SE_APPEAL": {
        "next_state": "DRC",
        "action": "File appeal to Dispute Redressal Committee (within 15 days of SE decision)",
        "deadline_days": 15,
        "responsible_party": "Contractor",
        "clause": "CPWD GCC Clause 25",
    },
    "DRC": {
        "next_state": "ARBITRATION",
        "action": "File for Arbitration (within 30 days of DRC decision — MISSED = DRC decision is FINAL)",
        "deadline_days": 30,
        "responsible_party": "Contractor",
        "clause": "CPWD GCC Clause 25",
    },
    "ARBITRATION": {
        "next_state": "CLOSED",
        "action": "Await arbitration award",
        "deadline_days": None,
        "responsible_party": "Arbitral Tribunal",
        "clause": "Arbitration & Conciliation Act 1996",
    },
}


# ── Escalation Record ─────────────────────────────────────────────────────

@dataclass
class EscalationRecord:
    event_id: str
    project_id: str
    contract_type: str
    current_tier: str
    tier_entered_date: str
    tier_deadline: Optional[str]
    responsible_party: str
    next_action: str
    clause: str
    notice_text: Optional[str] = None
    is_final: bool = False
    history: list = field(default_factory=list)

    def days_remaining(self) -> Optional[int]:
        if not self.tier_deadline:
            return None
        deadline = _parse_date(self.tier_deadline)
        if deadline:
            return max(0, (deadline - date.today()).days)
        return None


# ── Notice Template Generator (Groq) ─────────────────────────────────────

def _generate_notice_text(
    contract_type: str,
    tier: str,
    project_name: str,
    contractor_name: str,
    violation_summary: str,
    clause: str,
) -> str:
    """Use Groq to draft a formal notice in appropriate legal language."""
    prompt = f"""
Draft a formal {tier.replace('_', ' ').title()} notice for an Indian infrastructure contract.

Contract Type: {contract_type}
Project: {project_name}
Contractor: {contractor_name}
Violation Summary: {violation_summary}
Governing Clause: {clause}

Requirements:
- Use formal legal language appropriate for a government infrastructure contract
- Reference the exact clause number
- State the specific violation and its financial/schedule impact
- State the required response and deadline clearly
- Keep it under 200 words
- End with: "Issued by: [Authority's Engineer / Engineer-in-Charge]"

Return ONLY the notice text, no preamble.
"""
    result = groq_narrate(
        system_prompt="You are a legal drafter for Indian public infrastructure contracts. Draft formal notices in precise, authoritative language.",
        user_content=prompt,
    )
    return result or f"[Notice template generation failed — draft manually per {clause}]"


# ── Escalation Agent ──────────────────────────────────────────────────────

class EscalationAgent:
    """
    Determines and advances the escalation state for a compliance event.
    Per EL/05 §Escalation Agent.
    """

    def _get_transitions(self, contract_type: str) -> dict:
        return EPC_TRANSITIONS if contract_type == "EPC" else ITEM_RATE_TRANSITIONS

    def advance_escalation(
        self,
        event_id: str,
        project_id: str,
        contract_type: str,
        current_tier: str,
        violation_summary: str,
        project_name: str = "Unknown Project",
        contractor_name: str = "Contractor",
        today: date = None,
        generate_notice: bool = True,
    ) -> EscalationRecord:
        """
        Given the current escalation tier, determine next required action and deadline.

        Args:
            current_tier: current state (e.g., "NONE", "NOTICE_OF_INTENT")
            generate_notice: if True, call Groq to draft the formal notice text
        """
        today = today or date.today()
        transitions = self._get_transitions(contract_type)

        if current_tier not in transitions:
            # Unknown or terminal state
            return EscalationRecord(
                event_id=event_id,
                project_id=project_id,
                contract_type=contract_type,
                current_tier=current_tier,
                tier_entered_date=str(today),
                tier_deadline=None,
                responsible_party="N/A",
                next_action="No further escalation defined.",
                clause="N/A",
                is_final=True,
            )

        transition = transitions[current_tier]
        next_state = transition["next_state"]
        deadline_days = transition["deadline_days"]
        tier_deadline = str(today + timedelta(days=deadline_days)) if deadline_days else None

        # Generate notice text via Groq
        notice_text = None
        if generate_notice:
            try:
                notice_text = _generate_notice_text(
                    contract_type=contract_type,
                    tier=next_state,
                    project_name=project_name,
                    contractor_name=contractor_name,
                    violation_summary=violation_summary,
                    clause=transition["clause"],
                )
            except Exception as e:
                notice_text = f"[Groq unavailable: {e}] Draft manually per {transition['clause']}"

        return EscalationRecord(
            event_id=event_id,
            project_id=project_id,
            contract_type=contract_type,
            current_tier=next_state,
            tier_entered_date=str(today),
            tier_deadline=tier_deadline,
            responsible_party=transition["responsible_party"],
            next_action=transition["action"],
            clause=transition["clause"],
            notice_text=notice_text,
            is_final=(next_state == "CLOSED"),
        )

    def check_expired_tiers(self, records: list[EscalationRecord]) -> list[EscalationRecord]:
        """
        Review a list of escalation records and advance any whose cure period has expired.
        Called by APScheduler background job.
        """
        today = date.today()
        updated = []
        for record in records:
            if record.tier_deadline:
                deadline = _parse_date(record.tier_deadline)
                if deadline and today > deadline and not record.is_final:
                    # Auto-advance to next tier
                    updated.append(
                        self.advance_escalation(
                            event_id=record.event_id,
                            project_id=record.project_id,
                            contract_type=record.contract_type,
                            current_tier=record.current_tier,
                            violation_summary=f"Cure period expired on {deadline}",
                            generate_notice=True,
                        )
                    )
                else:
                    updated.append(record)
            else:
                updated.append(record)
        return updated

    def save_record(self, record: EscalationRecord, output_dir: str = "data/escalation") -> str:
        """Persist escalation record to JSON."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"escalation_{record.project_id}_{record.event_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(record), f, indent=2, default=str)
        return path


# ── CLI Test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    agent = EscalationAgent()

    print("=== EPC Escalation Test ===")
    rec = agent.advance_escalation(
        event_id="EVT-C15-001",
        project_id="CONTRACT_001",
        contract_type="EPC",
        current_tier="NONE",
        violation_summary="Contractor is 95 days beyond SCD. LD cap at 88%. Project Milestone IV missed.",
        project_name="NH-44 Karnataka Road Widening",
        contractor_name="XYZ Constructions Pvt. Ltd.",
        generate_notice=True,
    )
    print(f"  New tier: {rec.current_tier}")
    print(f"  Next action: {rec.next_action}")
    print(f"  Deadline: {rec.tier_deadline} ({rec.days_remaining()} days)")
    print(f"  Notice:\n{rec.notice_text}")

    print("\n=== Item Rate Escalation Test ===")
    rec2 = agent.advance_escalation(
        event_id="EVT-C15-002",
        project_id="CONTRACT_002",
        contract_type="ITEM_RATE",
        current_tier="NONE",
        violation_summary="Contractor 18 days beyond SCD. Monthly targets missed for 3 consecutive months.",
        project_name="Gandhinagar Road Repair Package 3",
        contractor_name="ABC Engineers",
        generate_notice=True,
    )
    print(f"  New tier: {rec2.current_tier}")
    print(f"  Next action: {rec2.next_action}")
    print(f"  Deadline: {rec2.tier_deadline} ({rec2.days_remaining()} days)")

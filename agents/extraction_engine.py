"""
Deterministic regex-based contract extraction.
Primary extraction engine — more reliable than LLM for structured contracts.
LLM used only as fallback for ambiguous fields.
"""
import re
import json
from typing import Optional


def _find(pattern: str, text: str, flags=re.IGNORECASE | re.DOTALL, group=1):
    m = re.search(pattern, text, flags)
    return m.group(group).strip() if m else None


def _float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s = re.sub(r"[^\d.]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _int(s: Optional[str]) -> Optional[int]:
    v = _float(s)
    return int(v) if v is not None else None


# ── Milestone extraction ───────────────────────────────────────────────

MILESTONE_PATTERN = re.compile(
    r"(Project\s+Milestone[-\s]*(?:I{1,3}|[1-4]|IV)[^\n]*?\n.*?)(?=Project\s+Milestone|Scheduled\s+Completion|$)",
    re.IGNORECASE | re.DOTALL,
)

def extract_milestones(text: str) -> list:
    milestones = []
    blocks = MILESTONE_PATTERN.findall(text)

    for i, block in enumerate(blocks):
        pct_scp = _int(_find(r"(\d+)%\s*of\s*(?:the\s+)?Scheduled\s+Construction\s+Period", block))
        day = _int(_find(r"Day\s+(\d+)\s+from\s+(?:the\s+)?Appointed", block))
        if day is None:
            day = _int(_find(r"\|\s*Day\s+(\d+)\s*\|", block))
        if day is None:
            day = _int(_find(r"\bDay\s+(\d+)\b", block))
        
        progress = _int(_find(r"(\d+)%\s*physical\s+progress", block))
        if progress is None:
            progress = _int(_find(r"\|\s*(\d+)%\s*\|", block))
        ld_rate = _float(_find(r"(\d+\.?\d*)\s*%\s*of\s+the\s+apportioned\s+milestone\s+value\s+per\s+day", block))
        catch_up = bool(re.search(r"catch.up\s+refund", block, re.IGNORECASE))

        if ld_rate is None:
            ld_rate = _float(_find(r"(\d+\.?\d*)\s*%.*?per\s+day\s+of\s+delay", block))

        milestones.append({
            "id": f"M{i+1}",
            "name": f"Project Milestone {['I','II','III','IV'][i] if i < 4 else i+1}",
            "trigger_pct_of_scp": pct_scp,
            "trigger_day": day,
            "required_physical_progress_pct": progress,
            "ld_rate_pct_per_day": ld_rate,
            "ld_basis": "apportioned_milestone_value" if re.search(r"apportioned", block, re.IGNORECASE) else "total_contract_price",
            "catch_up_refund_eligible": catch_up,
            "source_clause": _find(r"(Article\s+[\d.]+|Clause\s+[\d.]+)", block) or "Article 10.3.1",
        })

    # Scheduled completion (M4) — use scp_days if pattern picks wrong day
    scd_block = re.search(r"Scheduled\s+Completion\s+Date.*?Day\s+(\d+)", text, re.IGNORECASE | re.DOTALL)
    # Find largest trigger_day among existing milestones to validate M4 day
    existing_days = [m["trigger_day"] for m in milestones if m.get("trigger_day")]
    max_existing = max(existing_days) if existing_days else 0

    # Pattern-extracted day for M4
    raw_m4_day = _int(scd_block.group(1)) if scd_block else None

    # If raw day is <= max existing, it grabbed a wrong number — compute from scp pct instead
    if raw_m4_day and raw_m4_day <= max_existing:
        raw_m4_day = None  # will be filled by scp_days at rule store assembly

    milestones.append({
        "id": "M4",
        "name": "Scheduled Completion Date",
        "trigger_pct_of_scp": 100,
        "trigger_day": raw_m4_day,   # None means "use scp_days" — patched at rule store assembly
        "required_physical_progress_pct": 100,
        "ld_rate_pct_per_day": _float(_find(r"(\d+\.?\d*)%\s+of\s+the\s+(?:total\s+)?(?:C|c)ontract\s+(?:P|p)rice\s+per\s+day", text)),
        "ld_basis": "total_contract_price",
        "catch_up_refund_eligible": False,
        "source_clause": "Article 10.3.1 / Clause 2",
    })


    return milestones if milestones else None


def extract_liquidated_damages(text: str) -> dict:
    return {
        "daily_rate_pct": _float(_find(r"(\d+\.?\d*)%\s+of\s+the\s+Contract\s+Price\s+per\s+day", text))
            or _float(_find(r"(\d+\.?\d*)%\s+of\s+the\s+Tendered\s+Value\s+per\s+(?:day|month)", text)),
        "max_cap_pct": _int(_find(r"maximum.*?(\d+)%\s+of\s+the\s+(?:Contract|Tendered)", text)),
        "max_cap_inr": _float(_find(r"(?:Rs\.|INR)\s*([0-9,]+)", text)) or None,
        "catch_up_refund": bool(re.search(r"catch.up\s+refund", text, re.IGNORECASE)),
        "source_clause": _find(r"(Article\s+10\.3\.\d+|Clause\s+2)", text) or "Article 10.3.2 / Clause 2",
    }


def extract_performance_security(text: str) -> dict:
    return {
        "pct_of_contract_value": _float(_find(r"(\d+\.?\d*)%\s+of\s+the\s+(?:Tendered|Contract)\s+(?:Value|Price)", text)),
        "amount_inr": _float(re.sub(r"[^\d.]", "", _find(r"Rs\.\s*([\d,]+)", text) or "")),
        "acceptable_forms": re.findall(
            r"(Bank\s+Guarantee|Fixed\s+Deposit\s+Receipt|FDR|Insurance\s+Surety\s+Bond)", text, re.IGNORECASE
        ),
        "submission_deadline_days": _int(_find(r"within\s+(\d+)\s+days\s+of\s+(?:receipt\s+of\s+)?the\s+Letter\s+of\s+Acceptance", text)),
        "late_fee_pct_per_day": _float(_find(r"(\d+\.?\d*)%\s+per\s+day\s+of\s+delay", text)),
        "max_extension_days": _int(_find(r"maximum\s+extension\s+of\s+(\d+)\s+days", text)),
        "consequence_of_failure": _find(r"(debarred|cancelled|forfeited[^.]+\.)", text),
        "source_clause": "Clause 1",
    }


def extract_force_majeure(text: str) -> dict:
    contents = re.findall(r"\(([a-e])\)\s+([^\n(]+)", text)
    return {
        "notice_deadline_days": _int(_find(r"within\s+(\d+)\s+(?:seven\s+)?\(?seven\)?\s*days\s+of\s+becoming\s+aware|within\s+(\d+)\s+days\s+of\s+becoming", text)),
        "notice_recipient": _find(r"addressed\s+to\s+(?:the\s+)?(.+?)(?:\.|and)", text),
        "required_notice_contents": [c[1].strip() for c in contents] if contents else ["description", "impact", "duration", "mitigation"],
        "ongoing_reporting_frequency": "weekly" if re.search(r"weekly", text, re.IGNORECASE) else None,
        "max_suspension_days_before_termination": _int(_find(r"more\s+than\s+(\d+)\s+continuous\s+days", text)),
        "categories": re.findall(r"(non-political\s+events|indirect\s+political\s+events|political\s+events)", text, re.IGNORECASE),
        "source_clause": "Article 19",
    }


def extract_eot_rules(text: str) -> dict:
    return {
        "application_deadline_days": _int(
            _find(r"within\s+(\d+)(?:\s*\([^)]+\))?\s+days\s+of\s+(?:the\s+)?(?:hindrance|occurrence)", text)
        ),
        "hindrance_register_mandatory": bool(re.search(r"Hindrance\s+Register", text, re.IGNORECASE)),
        "overlap_deduction_required": bool(re.search(r"[Oo]verlapping\s+hindrances|concurrent\s+delays", text, re.IGNORECASE)),
        "source_clause": "Clause 5",
    }


def extract_termination(text: str) -> dict:
    triggers = []
    patterns = [
        (r"[Dd]elay\s+beyond.*?(\d+)\s+days", "delay_beyond_scd", None),
        (r"[Aa]bandonment.*?(\d+)\s+days", "abandonment", None),
        (r"LD\s+cap.*?(\d+)%", "ld_cap_exhausted", None),
    ]
    for pat, name, _ in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            threshold = _int(m.group(1))
            triggers.append({
                "trigger": name,
                "threshold_days": threshold if "days" in pat else None,
                "cure_period_days": _int(_find(r"cure\s+period.*?(\d+)\s+days", text)),
            })

    return {
        "contractor_default_triggers": triggers if triggers else None,
        "source_clause": _find(r"(Article\s+23\.\d+|Clause\s+5)", text) or "Article 23.1.1",
    }


def extract_dispute_resolution(text: str) -> dict:
    tiers = []
    if re.search(r"[Cc]onciliation", text):
        tiers.append({"tier": 1, "mechanism": "Amicable Conciliation", "deadline_days": _int(_find(r"[Cc]onciliation.*?(\d+)\s+days", text))})
    if re.search(r"[Aa]rbitration", text):
        tiers.append({"tier": 2, "mechanism": "Arbitration", "deadline_days": None})
    return {"tiers": tiers if tiers else None, "source_clause": "Article 26"}


def extract_bonus(text: str) -> dict:
    applicable = bool(re.search(r"[Ee]arly\s+[Cc]ompletion\s+[Bb]onus|Clause\s+2A", text, re.IGNORECASE))
    return {
        "applicable": applicable,
        "rate_pct_per_month": _float(_find(r"bonus\s+of\s+(\d+\.?\d*)%.*?per\s+month", text)),
        "max_cap_pct": _float(_find(r"maximum\s+of\s+(\d+)%\s+of\s+the\s+Tendered", text)),
        "source_clause": "Clause 2A",
    }


def extract_payment_workflow(text: str) -> dict:
    deductions = []
    deduction_patterns = [
        (r"Retention\s+Money.*?(\d+\.?\d*)%", "retention_money"),
        (r"TDS.*?Income\s+Tax.*?(\d+\.?\d*)%", "tds_income_tax"),
        (r"GST\s+TDS.*?(\d+\.?\d*)%", "gst_tds"),
        (r"BOCW\s+Cess.*?(\d+\.?\d*)%", "bocw_cess"),
    ]
    for pat, name in deduction_patterns:
        rate = _float(_find(pat, text))
        if rate:
            deductions.append({"type": name, "rate_pct": rate})

    return {
        "ra_bill_submission_day": _int(_find(r"(\d+)(?:st|th|nd|rd)?\s+of\s+each\s+month", text)),
        "verification_deadline_days": _int(_find(r"verify.*?within\s+(\d+)\s+days", text)),
        "payment_release_deadline_days": _int(
            _find(r"(?:payment\s+shall\s+be\s+released|shall\s+release\s+payment|release\s+payment)\s+within\s+(\d+)\s+days", text)
        ),
        "mandatory_deductions": deductions if deductions else None,
        "source_clause": "Clause 7",
    }


def extract_variation_orders(text: str) -> dict:
    return {
        "max_variation_pct": _int(_find(r"(\d+)%\s+of\s+the\s+original\s+contract\s+value", text)),
        "claim_notice_deadline_days": _int(_find(r"within\s+(\d+)\s+days\s+of\s+receiving\s+a\s+variation", text)),
        "source_clause": _find(r"(Article\s+13|Clause\s+12)", text) or "Article 13 / Clause 12",
    }


def extract_quality_assurance(text: str) -> dict:
    tests = re.findall(r"-\s+([^:\n]+):\s+([^\n]+)", text)
    return {
        "field_lab_required": bool(re.search(r"field\s+laboratory", text, re.IGNORECASE)),
        "check_test_pct": _int(_find(r"(\d+)%\s+of\s+samples", text)),
        "ncr_process": bool(re.search(r"NCR|Non-Conformance", text, re.IGNORECASE)),
        "quality_tests": [{"item": t[0].strip(), "frequency": t[1].strip()} for t in tests[:6]] if tests else None,
        "source_clause": "Article 11",
    }


# ── Master extraction dispatcher ───────────────────────────────────────

EXTRACTORS = {
    "milestones":           extract_milestones,
    "liquidated_damages":   extract_liquidated_damages,
    "performance_security": extract_performance_security,
    "force_majeure":        extract_force_majeure,
    "eot_rules":            extract_eot_rules,
    "termination":          extract_termination,
    "dispute_resolution":   extract_dispute_resolution,
    "bonus":                extract_bonus,
    "payment_workflow":     extract_payment_workflow,
    "variation_orders":     extract_variation_orders,
    "quality_assurance":    extract_quality_assurance,
}


def deterministic_extract(full_text: str) -> dict:
    """Run all deterministic extractors on the full contract text."""
    results = {}
    for target, fn in EXTRACTORS.items():
        try:
            results[target] = fn(full_text)
            print(f"  [OK] {target}")
        except Exception as e:
            print(f"  [WARN] {target} extraction error: {e}")
            results[target] = None
    results["conditions_precedent"] = {
        "appointed_date_required": True,
        "row_handover_required": True,
        "source_clause": None,
    }
    return results

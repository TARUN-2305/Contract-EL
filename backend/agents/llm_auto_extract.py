"""
LLM Auto-Extraction Agent
Automatically extracts:
1. Contract fields from uploaded PDF/DOCX (project name, value, SCP, milestones)
2. MPR fields from uploaded MD/PDF (physical %, labour, QA, BoQ items)
3. Enriches with history context for better predictions
"""
import json
import re
from typing import Optional


CONTRACT_AUTO_EXTRACT_PROMPT = """You are a contract data extraction specialist for Indian infrastructure contracts.
Extract ALL fields from the contract text below. Return ONLY valid JSON.

Required fields:
{
  "project_name": "string or null",
  "contract_type": "EPC or ITEM_RATE",
  "contract_value_inr": number or null,
  "scp_days": integer or null,
  "location": "string or null",
  "contractor_name": "string or null",
  "appointed_date": "YYYY-MM-DD or null",
  "scheduled_completion_date": "YYYY-MM-DD or null",
  "ld_rate_pct_per_day": number or null,
  "ld_cap_pct": number or null,
  "performance_security_pct": number or null,
  "milestones": [
    {"name": "M1", "trigger_pct": 28, "progress_pct": 20, "day": 204}
  ],
  "confidence_notes": "explain any uncertain extractions"
}

Contract text:
{text}"""


MPR_AUTO_EXTRACT_PROMPT = """You are an MPR (Monthly Progress Report) data extraction specialist for Indian infrastructure projects.
Extract ALL progress fields from the document below. Return ONLY valid JSON with NO preamble.

Required fields:
{
  "project_name": "string or null",
  "agreement_number": "string or null",
  "contractor_name": "string or null",
  "reporting_period_start": "YYYY-MM-DD or null",
  "reporting_period_end": "YYYY-MM-DD or null",
  "day_number": integer or null,
  "planned_physical_pct": float or null,
  "actual_physical_pct": float or null,
  "previous_actual_physical_pct": float or null,
  "variance_pct": float or null,
  "cumulative_expenditure_inr": float or null,
  "planned_expenditure_inr": float or null,
  "labour_skilled_planned": integer or null,
  "labour_skilled_actual": integer or null,
  "labour_unskilled_planned": integer or null,
  "labour_unskilled_actual": integer or null,
  "ncrs_pending": integer or null,
  "rfis_pending": integer or null,
  "days_lost_rainfall": integer or null,
  "rainfall_mm_monthly": float or null,
  "row_pending_km": float or null,
  "gfc_drawings_pending": integer or null,
  "ra_bill_number": "string or null",
  "ra_bill_amount_inr": float or null,
  "performance_security_submitted": boolean or null,
  "boq_items": [{"item": "name", "unit": "unit", "total_qty": num, "cumulative_qty": num, "pct_complete": num}],
  "qa_failures": integer or null,
  "key_observations": "string summary",
  "confidence_notes": "any uncertain fields"
}

{history_context}

Document text:
{text}"""


class LLMAutoExtractor:
    def __init__(self):
        from utils.llm_client import get_llm_client
        self.llm = get_llm_client()

    def extract_contract_fields(self, text: str) -> dict:
        """Auto-extract contract metadata from contract text."""
        # Truncate to 8000 chars to fit context
        truncated = text[:8000]
        prompt = CONTRACT_AUTO_EXTRACT_PROMPT.replace("{text}", truncated)

        result = self.llm.json_extract(
            system_prompt="You extract structured JSON from Indian infrastructure contract documents. Return ONLY valid JSON.",
            user_content=prompt
        )
        if not result:
            return {"error": "LLM extraction failed", "confidence_notes": "No response from LLM"}

        # Clean JSON fences
        clean = re.sub(r"```json|```", "", result).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            return {"raw_response": result, "parse_error": str(e)}

    def extract_mpr_fields(self, text: str, history: list = None) -> dict:
        """Auto-extract MPR fields with optional history context."""
        truncated = text[:8000]

        # Build history context
        history_context = ""
        if history and len(history) > 0:
            recent = history[-3:]  # last 3 MPRs
            lines = []
            for h in recent:
                lines.append(
                    f"- Period {h.get('reporting_period', '?')}: "
                    f"Actual {h.get('actual_pct', '?')}%, "
                    f"Risk: {h.get('risk_label', '?')}, "
                    f"LD: ₹{h.get('ld_accrued_inr', 0):,.0f}"
                )
            history_context = "Previous MPR history (for context):\n" + "\n".join(lines) + "\n\n"

        prompt = MPR_AUTO_EXTRACT_PROMPT.replace("{text}", truncated).replace("{history_context}", history_context)

        result = self.llm.json_extract(
            system_prompt="You extract structured JSON from Indian infrastructure Monthly Progress Reports. Return ONLY valid JSON.",
            user_content=prompt
        )
        if not result:
            return {"error": "LLM extraction failed"}

        clean = re.sub(r"```json|```", "", result).strip()
        try:
            data = json.loads(clean)
            
            # Context-aware enrichment: If LLM missed previous progress, pull from history
            if data.get("previous_actual_physical_pct") is None and history and len(history) > 0:
                data["previous_actual_physical_pct"] = history[0].get("actual_pct")

            # Compute derived fields
            if data.get("planned_physical_pct") is not None and data.get("actual_physical_pct") is not None:
                data["variance_pct"] = round(data["actual_physical_pct"] - data["planned_physical_pct"], 2)
            return data
        except json.JSONDecodeError as e:
            return {"raw_response": result, "parse_error": str(e)}

    def extract_from_file(self, file_path: str, file_type: str) -> str:
        """Extract raw text from a file for LLM processing."""
        import os
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            try:
                import pdfplumber
                text_parts = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text() or ""
                        text_parts.append(t)
                return "\n\n".join(text_parts)
            except Exception:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(file_path)
                    return "\n".join(p.extract_text() or "" for p in reader.pages)
                except Exception as e:
                    return f"[Error extracting PDF: {e}]"

        elif ext in (".md", ".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif ext in (".docx", ".doc"):
            try:
                from utils.docx_to_md import docx_to_md
                return docx_to_md(file_path)
            except Exception as e:
                return f"[Error extracting DOCX: {e}]"

        return f"[Unsupported file type: {ext}]"

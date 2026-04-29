# Module 01 — Contract Parser
> Hierarchical RAG + LLM Tool-Calling  
> Produces: `rule_store_{contract_id}.json`

---

## Purpose

The Contract Parser is the **source of truth** for the entire system. Every downstream agent — compliance checker, risk predictor, penalty calculator — derives its logic from what this module extracts. It must be accurate, structured, and auditable.

It handles two real-world contract types:
- **EPC contracts** (NITI Aayog Model) — milestone-percentage based, 60-day cure periods
- **Item Rate contracts** (CPWD GCC 2023) — monthly targets, 7-day show cause notices

---

## Input

| Input | Source | Format |
|---|---|---|
| Contract PDF | Uploaded by Contract Manager | `.pdf` |
| Contract Type selector | Contract Manager UI dropdown | `"EPC"` or `"ITEM_RATE"` |
| Project metadata | Contract Manager form | project name, contract value (₹), SCP duration (days), location |

---

## Pipeline: Hierarchical RAG

### Stage 1: PDF Preprocessing
```
PDF → pdfplumber / pypdf → raw text pages
     → detect structure (Article numbers, Clause numbers, Schedule headers)
     → split into semantic chunks (not fixed-size; respect article boundaries)
     → each chunk tagged with: {source_clause, page_number, section_type}
```

### Stage 2: Embedding + Vector Store
```
chunks → sentence-transformers (all-MiniLM-L6-v2) → 384-dim vectors
       → stored in pgvector with metadata: {clause_id, section, contract_id}
```

### Stage 3: Hierarchical Extraction (LLM with Tools)

The LLM does NOT read the whole contract at once. It uses a structured extraction plan:

```python
EXTRACTION_PLAN = [
    {"target": "milestones",          "query": "project milestone schedule completion date"},
    {"target": "liquidated_damages",  "query": "liquidated damages compensation delay penalty rate"},
    {"target": "performance_security","query": "performance security guarantee bank deposit"},
    {"target": "quality_assurance",   "query": "quality assurance testing NCR non-conformance"},
    {"target": "force_majeure",       "query": "force majeure acts of god political event notice"},
    {"target": "eot_rules",           "query": "extension of time hindrance delay application"},
    {"target": "variation_orders",    "query": "change of scope variation order extra items"},
    {"target": "termination",         "query": "termination default notice cure period"},
    {"target": "dispute_resolution",  "query": "dispute arbitration DRB conciliation escalation"},
    {"target": "bonus",               "query": "early completion incentive bonus clause 2A"},
    {"target": "conditions_precedent","query": "conditions precedent appointed date handover"},
    {"target": "payment_workflow",    "query": "running account bill measurement certificate payment"},
]
```

For each target: retrieve top-5 chunks → send to LLM with few-shot prompt → parse JSON → validate → store.

### Stage 4: Rule Store Assembly

All extracted fields are merged into a single structured JSON per contract:

```json
{
  "contract_id": "CONTRACT_001",
  "contract_type": "EPC",
  "contract_value_inr": 250000000,
  "scp_days": 730,
  "appointed_date": "2025-04-01",
  "scheduled_completion_date": "2027-03-31",
  "location": "NH-44, Karnataka",

  "milestones": [
    {
      "id": "M1",
      "name": "Project Milestone-I",
      "trigger_pct_of_scp": 28,
      "trigger_day": 204,
      "required_physical_progress_pct": 20,
      "ld_rate_pct_per_day": 0.05,
      "ld_basis": "apportioned_milestone_value",
      "catch_up_refund_eligible": true,
      "source_clause": "Article 10.3.1"
    },
    {
      "id": "M2",
      "name": "Project Milestone-II",
      "trigger_pct_of_scp": 55,
      "trigger_day": 401,
      "required_physical_progress_pct": 50,
      "ld_rate_pct_per_day": 0.05,
      "ld_basis": "apportioned_milestone_value",
      "catch_up_refund_eligible": true,
      "source_clause": "Article 10.3.1"
    },
    {
      "id": "M3",
      "name": "Project Milestone-III",
      "trigger_pct_of_scp": 75,
      "trigger_day": 547,
      "required_physical_progress_pct": 75,
      "ld_rate_pct_per_day": 0.05,
      "ld_basis": "apportioned_milestone_value",
      "catch_up_refund_eligible": true,
      "source_clause": "Article 10.3.1"
    },
    {
      "id": "M4",
      "name": "Scheduled Completion Date",
      "trigger_pct_of_scp": 100,
      "trigger_day": 730,
      "required_physical_progress_pct": 100,
      "ld_rate_pct_per_day": 0.05,
      "ld_basis": "total_contract_price",
      "catch_up_refund_eligible": false,
      "termination_threshold_days": 90,
      "source_clause": "Article 10.3.2 & 23.1.1"
    }
  ],

  "liquidated_damages": {
    "daily_rate_pct": 0.05,
    "max_cap_pct": 10,
    "max_cap_inr": 25000000,
    "catch_up_refund": true,
    "source_clause": "Article 10.3.2"
  },

  "performance_security": {
    "pct_of_contract_value": 5,
    "amount_inr": 12500000,
    "acceptable_forms": ["Bank Guarantee", "FDR", "Insurance Surety Bond"],
    "submission_deadline_days": 15,
    "late_fee_pct_per_day": 0.1,
    "max_extension_days": 15,
    "consequence_of_failure": "LoA cancellation + EMD forfeiture + debarment",
    "source_clause": "CPWD GCC Clause 1"
  },

  "quality_assurance": {
    "field_lab_required": true,
    "contractor_tests_primary": true,
    "authority_test_check_pct": 50,
    "ncr_rectification_basis": "specified by AE on NCR",
    "tests": [
      {"material": "concrete", "test": "slump", "frequency": "every batch", "standard": "IS:456"},
      {"material": "concrete", "test": "cube_strength_7d_28d", "frequency": "1 sample per 1-5 cum", "standard": "IS:456"},
      {"material": "soil", "test": "field_density_test", "frequency": "1 per 3000 sqm per layer", "standard": "MoRTH Sec 300"},
      {"material": "bitumen", "test": "bitumen_extraction_marshall", "frequency": "1 per 400 tonnes", "standard": "MoRTH Sec 500"}
    ],
    "source_clause": "NITI Aayog Article 11, CPWD Clause 10A"
  },

  "force_majeure": {
    "notice_deadline_days": 7,
    "notice_recipient": "Authority + Authority's Engineer",
    "required_notice_contents": ["event_description", "impact_assessment", "estimated_duration", "mitigation_strategy"],
    "proof_documents": {
      "weather": "IMD certified data",
      "political": "Police FIR / government curfew order",
      "change_in_law": "Official Gazette notification"
    },
    "ongoing_reporting_frequency": "weekly",
    "max_suspension_days_before_termination": 180,
    "categories": ["non_political", "indirect_political", "political"],
    "source_clause": "NITI Aayog Article 19"
  },

  "eot_rules": {
    "application_deadline_days": 14,
    "hindrance_register_mandatory": true,
    "overlap_deduction_required": true,
    "max_contractor_delay_before_termination_days": 90,
    "source_clause": "CPWD GCC Clause 5"
  },

  "variation_orders": {
    "max_total_variation_pct": 10,
    "contractor_consent_required_above_pct": 10,
    "claim_notice_deadline_days": 14,
    "rate_basis": "DSR + tender premium/discount",
    "rate_basis_new_items": "market rate + 15% overhead profit",
    "source_clause": "NITI Aayog Article 13, CPWD Clause 12"
  },

  "termination": {
    "contractor_default_triggers": [
      {"trigger": "delay_beyond_completion", "threshold_days": 90, "cure_period_days": 60},
      {"trigger": "abandonment", "threshold_days": 15, "cure_period_days": 60},
      {"trigger": "ld_cap_exhausted", "threshold_pct": 10, "cure_period_days": 60},
      {"trigger": "performance_security_not_replenished", "threshold_days": 15, "cure_period_days": 15}
    ],
    "authority_default_triggers": [
      {"trigger": "row_not_handed_over", "threshold_days": 180},
      {"trigger": "payment_not_released", "threshold_days": 60},
      {"trigger": "work_suspended_by_authority", "threshold_days": 180}
    ],
    "authority_default_compensation": ["work_done_value", "material_costs", "demobilization", "securities_returned"],
    "source_clause": "NITI Aayog Article 23"
  },

  "dispute_resolution": {
    "contract_type_track": "EPC",
    "tiers": [
      {"tier": 1, "mechanism": "Amicable Conciliation", "deadline_days": 30},
      {"tier": 2, "mechanism": "Arbitration (3-member tribunal)", "governing_law": "Arbitration and Conciliation Act 1996"}
    ],
    "source_clause": "NITI Aayog Article 26"
  },

  "early_completion_bonus": {
    "applicable": true,
    "rate_pct_per_month": 1,
    "max_cap_pct": 5,
    "disbursement": "Final Bill only",
    "source_clause": "CPWD Clause 2A"
  },

  "payment_workflow": {
    "ra_bill_submission_day": 5,
    "verification_deadline_days": 15,
    "payment_release_deadline_days": 30,
    "mandatory_deductions": [
      {"type": "retention_money", "rate_pct": 5},
      {"type": "tds_income_tax", "rate_pct": 2},
      {"type": "gst_tds", "rate_pct": 2},
      {"type": "bocw_cess", "rate_pct": 1},
      {"type": "ld_if_applicable", "rate_pct": "calculated"}
    ],
    "source_clause": "CPWD GCC Clause 7"
  }
}
```

---

## Mock Contract Specification

The mock contract PDF must contain the following sections (based on real NITI Aayog + CPWD + NHAI clause structures) to be parseable by the system:

### Mock Contract: NH-44 Karnataka Road Widening Project

**Contract details to hardcode in the mock PDF:**

```
Project: 4-Laning of NH-44 from Km 220 to Km 260 (40 km)
Contract Type: EPC
Contracting Authority: NHAI / Karnataka PWD
Contract Value: ₹25,00,00,000 (Twenty-Five Crore)
Scheduled Construction Period: 730 days (2 years)
Appointed Date: [To be filled on execution]

ARTICLE 10 — CONSTRUCTION PERIOD AND MILESTONES
10.3.1 The Contractor shall achieve Project Milestone-I, being 20% physical
        progress, by the day falling at 28% of the Scheduled Construction
        Period (i.e., Day 204 from the Appointed Date).
10.3.2 Liquidated Damages for delay shall be levied at the rate of 0.05%
        of the Contract Price per day of delay. The maximum LD shall not
        exceed 10% of the Contract Price (₹2,50,00,000).
10.3.3 If the Contractor misses an interim milestone but achieves the
        Scheduled Completion Date on time, all previously deducted LD
        shall be refunded without interest.

ARTICLE 19 — FORCE MAJEURE
19.1 The Affected Party shall issue written notice within 7 (seven) days
     of becoming aware of the Force Majeure Event. Failure to issue
     notice within 7 days forfeits all relief.

CLAUSE 1 — PERFORMANCE GUARANTEE
The Contractor shall deposit a Performance Guarantee equal to 5% of the
Tendered Value (₹1,25,00,000) within 15 days of the Letter of Acceptance.
Late submission shall attract a fee of 0.1% per day of delay.

CLAUSE 2 — COMPENSATION FOR DELAY
Compensation shall be levied at 1% of the Tendered Value per month (per
day basis), subject to a maximum of 10% of the Tendered Value.

CLAUSE 5 — EXTENSION OF TIME
The Contractor must apply for EoT within 14 days of the hindrance.
The Hindrance Register must be jointly signed by the Contractor and the JE.
```

---

## Extraction Prompt Template (Few-Shot)

```python
MILESTONE_EXTRACTION_PROMPT = """
You are a legal extraction engine for Indian infrastructure contracts.

Extract ALL milestone definitions from the following contract text.
Return ONLY valid JSON. No preamble, no explanation, no markdown.

Required fields per milestone:
- id (M1, M2, etc.)
- name
- trigger_pct_of_scp (% of scheduled construction period, integer)
- trigger_day (absolute day number, integer)
- required_physical_progress_pct (integer)
- ld_rate_pct_per_day (float)
- ld_basis ("apportioned_milestone_value" or "total_contract_price")
- catch_up_refund_eligible (boolean)
- source_clause (string, exact article/clause number)

If a field is not found, use null. Never hallucinate values.

Contract text:
{context}

Example output:
[
  {
    "id": "M1",
    "name": "Project Milestone-I",
    "trigger_pct_of_scp": 28,
    "trigger_day": 204,
    "required_physical_progress_pct": 20,
    "ld_rate_pct_per_day": 0.05,
    "ld_basis": "apportioned_milestone_value",
    "catch_up_refund_eligible": true,
    "source_clause": "Article 10.3.1"
  }
]
"""
```

---

## Validation Rules

After extraction, before writing to rule store:

```python
VALIDATION_RULES = {
    "milestones": {
        "ld_rate_pct_per_day": lambda x: 0 < x <= 1,         # sanity check
        "max_cap_pct": lambda x: x == 10,                      # universal standard
        "trigger_pct_of_scp": lambda x: 0 < x <= 100,
    },
    "performance_security": {
        "pct_of_contract_value": lambda x: 4 <= x <= 10,      # CPWD standard range
        "submission_deadline_days": lambda x: x == 15,
    },
    "force_majeure": {
        "notice_deadline_days": lambda x: x == 7,              # NITI Aayog Article 19
    }
}
```

If any critical field is `null` after extraction, flag it as `⚠️ UNRESOLVED` and require Contract Manager review before activating the rule store.

---

## Output

| File | Location | Contents |
|---|---|---|
| `rule_store_{contract_id}.json` | `data/rule_store/` | Full structured rule store |
| `extraction_audit_{contract_id}.json` | `data/audit/` | Which chunks were used for each field |
| `unresolved_fields_{contract_id}.json` | `data/audit/` | Nulls requiring human review |

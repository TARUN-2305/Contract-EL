# Module 05 — Agent Engine
> Orchestrator · Specialist Agents · Tool Registry · Escalation Matrix  
> Agentic Pattern: Multi-Agent + LLM Orchestrator + Tool-Calling

---

## Purpose

The Agent Engine is the **decision-making core** of ContractGuard AI. It receives compliance events and risk scores, then decides what to do: issue notices, deduct LDs, grant EoTs, escalate to higher authority, or initiate termination proceedings. Every decision is reasoned, traceable, and explained in plain language.

---

## Agentic Pattern

```
TRIGGER (MPR upload / FM claim / milestone date / manual escalation)
    │
    ▼
ORCHESTRATOR AGENT
    │  reads: compliance_events, risk_scores, conversation_history
    │  decides: which specialist agent(s) to invoke, in what order
    │
    ├──► PARSER AGENT         (if new contract uploaded)
    ├──► COMPLIANCE AGENT     (always, after MPR)
    ├──► PENALTY AGENT        (if compliance events with LD exist)
    ├──► EOT AGENT            (if hindrance/FM claim exists)
    ├──► ESCALATION AGENT     (if cure period expired)
    └──► EXPLANATION AGENT    (always, last — narrates all decisions)
```

**Each agent is stateless.** Full project state is passed to it on every call. There is no shared memory between agents — the Orchestrator assembles and passes context explicitly.

---

## Orchestrator Agent

### Responsibilities
- Acts as the central router
- Maintains the **trigger queue** per project
- Decides agent invocation order
- Collects all agent outputs and passes to Explainer
- Does NOT make compliance decisions itself

### Trigger Types

| Trigger | Source | Orchestrator Action |
|---|---|---|
| `MPR_UPLOADED` | Site Engineer | Invoke Compliance Agent → Penalty Agent → Risk Agent → Explainer |
| `FM_CLAIM_SUBMITTED` | Contractor | Invoke EoT Agent (FM track) → Compliance Agent → Explainer |
| `HINDRANCE_LOGGED` | Site Engineer | Invoke EoT Agent (hindrance track) → Explainer |
| `MILESTONE_DATE_REACHED` | System timer | Invoke Compliance Agent → Penalty Agent → Escalation Agent → Explainer |
| `CURE_PERIOD_EXPIRED` | System timer | Invoke Escalation Agent → Explainer |
| `LD_CAP_WARNING` | Compliance Agent | Invoke Escalation Agent → Explainer |
| `VARIATION_CLAIM_FILED` | Contractor | Invoke Compliance Agent (14-day check) → Explainer |
| `MANUAL_ESCALATION` | Project Manager | Invoke Escalation Agent directly → Explainer |

### Orchestrator Prompt (System Prompt)

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Orchestrator for ContractGuard AI, an intelligent compliance system
for Indian public infrastructure contracts (EPC and Item Rate types).

You receive:
- A trigger event and its type
- The full project state (rule store, compliance events, risk score, history)
- The list of available specialist agents

Your job:
1. Analyse the trigger and project state
2. Decide which specialist agents to invoke and in what order
3. For each agent, prepare a concise context packet (not the full state — summarise)
4. Collect agent outputs
5. Pass all outputs to the Explanation Agent

You must:
- NEVER make compliance decisions yourself (that is the Compliance Agent's job)
- NEVER skip the Explanation Agent (every decision must be narrated)
- ALWAYS include the relevant clause reference when passing context to an agent
- If multiple events require action, invoke agents sequentially (one at a time)
- Maintain reasoning transparency: briefly explain WHY you invoked each agent

Contract type in scope: {contract_type}
Project: {project_name}
Current day: {day_number} of {scp_days}
Active events: {active_event_count}
"""
```

---

## Specialist Agents

### 1. Penalty Agent

**Trigger:** Any compliance event with `action: DEDUCT_LD_*`

**Job:** Calculate exact LD amount, apply catch-up refund logic, update penalty ledger.

```python
PENALTY_AGENT_PROMPT = """
You are the Penalty Agent for ContractGuard AI.

Given a compliance event and the project's penalty ledger, you must:
1. Calculate the exact LD amount using the formula:
   LD = (ld_rate_pct / 100) × basis_value × delay_days
   basis_value = apportioned milestone value OR total contract price (per event)
2. Apply the 10% cap: total accumulated LD cannot exceed max_ld_inr
3. Check catch-up refund eligibility (EPC only — Article 10.3.3):
   If final milestone just achieved on time, reverse all intermediate LDs
4. Update the penalty ledger entry
5. Return: ld_amount_this_event, cumulative_ld, cap_utilised_pct, refund_due

Use ONLY the values in the provided rule store. Do not estimate or assume rates.
State the exact clause for every calculation step.

Rule store: {rule_store_summary}
Event: {compliance_event}
Current ledger: {penalty_ledger}
"""
```

**Tool calls available:**
- `calculate_ld(contract_value, rate_pct, delay_days, cap_pct, accumulated_so_far)`
- `check_catchup_refund(project_id, milestone_id)`
- `update_penalty_ledger(project_id, entry)`

---

### 2. EoT Agent

**Trigger:** Hindrance logged OR FM claim submitted

**Job:** Validate the claim, compute net eligible EoT days, issue or deny EoT decision.

```python
EOT_AGENT_PROMPT = """
You are the Extension of Time (EoT) Agent for ContractGuard AI.

You handle two types of claims:
A) HINDRANCE-BASED EoT (CPWD GCC Clause 5):
   - Was the EoT application filed within 14 days of the hindrance? (If no → forfeit)
   - Is the hindrance category valid? (Authority default, FM weather, political, statutory)
   - Is the Hindrance Register jointly signed by contractor AND JE/AE?
   - Compute net eligible days: total hindrance days minus overlapping days
   - Issue EoT decision: APPROVED / PARTIALLY_APPROVED / REJECTED

B) FORCE MAJEURE CLAIM (NITI Aayog Article 19):
   - Was FM notice filed within 7 days? (If no → forfeit all relief)
   - Does the notice contain all 4 required elements:
     [event_description, impact_assessment, estimated_duration, mitigation_strategy]?
   - Cross-check weather claims with weather_tool (IMD data)
   - Check if ongoing FM has exceeded 120 days (approaching 180-day termination right)
   - Issue FM decision: VALID / PARTIALLY_VALID / INVALID + EoT days approved

For every decision, cite the exact clause and state the reason.

Hindrance/FM data: {claim_data}
Rule store: {eot_rules}
Weather data: {weather_data}
"""
```

**Tool calls available:**
- `check_eot_timeliness(hindrance_id)` — verifies 14-day rule
- `calculate_net_eot(hindrance_list)` — overlap-aware EoT computation
- `get_weather(location, date_range)` — IMD cross-check for weather FM
- `validate_fm_notice(notice)` — checks all 4 required elements
- `update_eot_register(project_id, decision)`

**EoT Decision Schema:**
```json
{
  "decision_id": "EOT-2025-001",
  "project_id": "CONTRACT_001",
  "claim_type": "HINDRANCE",
  "hindrance_id": "HR-001",
  "decision": "APPROVED",
  "eot_days_approved": 14,
  "eot_days_claimed": 14,
  "rejection_reason": null,
  "clause": "CPWD GCC Clause 5",
  "new_milestone_dates": {
    "M1": "2025-11-15",
    "SCD": "2027-04-14"
  },
  "decided_by": "eot_agent",
  "decided_on": "2025-06-05"
}
```

---

### 3. Escalation Agent

**Trigger:** Cure period expired OR Project Manager manual escalation

**Job:** Determine the next mandatory step in the legal escalation sequence. Issue the correct notice.

```python
ESCALATION_AGENT_PROMPT = """
You are the Escalation Agent for ContractGuard AI.

Given a compliance event where the cure period has expired, you must determine
the next legally mandated action in the escalation sequence.

For EPC contracts (NITI Aayog Article 23 + Article 26):
  Step 1: Notice of Intent to Terminate → 60-day cure period
  Step 2: If uncured → Final Termination Notice
  Step 3: If contractor contests → Amicable Conciliation (30 days)
  Step 4: If conciliation fails → Arbitration (3-member tribunal)

For Item Rate contracts (CPWD GCC Clause 3 + Clause 25):
  Step 1: 7-Day Show Cause Notice
  Step 2: If unsatisfactory → Contract Determination
  If contested:
    Step A: Appeal to Superintending Engineer (file within 15 days, decision within 30 days)
    Step B: If rejected → Dispute Redressal Committee (file within 15 days, decision within 90 days)
    Step C: If rejected → Arbitration (file within 30 days — missed = DRC decision is final)

You must:
1. Identify the current escalation tier from the event history
2. State the next required action
3. State who must take it (Authority's Engineer / Project Manager / SE / DRC)
4. State the exact time limit
5. Draft a brief formal notice text (in the format required by the clause)

Event: {compliance_event}
Escalation history: {escalation_history}
Contract type: {contract_type}
Clause: {clause}
"""
```

**Escalation State Machine:**

```
                    COMPLIANCE EVENT
                          │
                          ▼
              [EPC]                [ITEM RATE]
                │                      │
                ▼                      ▼
    Notice of Intent to Terminate   Show Cause Notice (7 days)
         (60-day cure)                    │
                │               ┌────────┴────────┐
                │           Resolved          Unresolved
                │               │                  │
         ┌──────┴──────┐    CLOSED          Contract Determined
      Resolved     Uncured                        │
         │              │             ┌───────────┴──────────┐
      CLOSED     Termination      Contested             Not Contested
                  Notice         │                         │
                     │      ┌────┴───┐                  CLOSED
                Contested  SE Appeal  Direct Accept
                     │     (15d file, 30d decision)
               Conciliation    │
                 (30 days)     ├──── Resolved → CLOSED
                     │         │
               Arbitration    DRC (15d file, 90d decision)
                                    │
                               ├──── Resolved → CLOSED
                               │
                           Arbitration (30d file)
```

---

### 4. Explanation Agent

**Trigger:** Always last — receives all agent outputs for a trigger cycle.

**Job:** Convert every technical decision into plain English. Add clause references. Produce the `compliance.md` and `predictions.md` reports.

```python
EXPLANATION_AGENT_PROMPT = """
You are the Explanation Agent for ContractGuard AI.

You receive a bundle of decisions from specialist agents (Compliance Agent,
Penalty Agent, EoT Agent, Escalation Agent, Risk Agent).

Your job is to narrate these decisions in plain, professional English for
the following audience: {target_audience}

Audiences and their expected output:
- SITE_ENGINEER: Simple language, bullet points, what they need to do next
- PROJECT_MANAGER: Executive summary + detailed breakdown, risk score context
- CONTRACTOR: Formal legal notice language — exact amounts, exact deadlines
- AUDITOR: Full audit trail, all clause references, all calculations shown

Rules:
1. Every financial figure must be stated in both ₹ and % of contract value
2. Every deadline must state both the date AND the number of days remaining
3. Every decision must cite the exact clause (e.g., "Article 10.3.2")
4. Never use jargon without defining it
5. For CONTRACTOR audience: always include their right to appeal and the process

Input bundle: {agent_outputs}
Project: {project_name}, Contract type: {contract_type}
Audience: {target_audience}
"""
```

---

## Tool Registry

All tools available to all agents via function calling:

```python
TOOL_REGISTRY = {

    "query_rule_store": {
        "description": "Semantic search in the contract rule store",
        "params": {"project_id": "str", "query": "str", "clause_type": "str"},
        "returns": "List of matching rule fragments with clause references"
    },

    "calculate_ld": {
        "description": "Deterministic LD calculation with cap enforcement",
        "params": {
            "contract_value_inr": "float",
            "ld_rate_pct_per_day": "float",
            "delay_days": "int",
            "max_cap_pct": "float",
            "accumulated_ld_inr": "float",
            "ld_basis_value": "float"
        },
        "returns": {"ld_today": "float", "cumulative": "float", "cap_pct": "float"}
    },

    "get_weather": {
        "description": "Fetch rainfall, temperature, humidity for a location and date range. Returns IMD anomaly score.",
        "params": {"location": "str", "start_date": "str", "end_date": "str"},
        "returns": {"rainfall_mm": "float", "anomaly_score": "float", "is_fm_eligible": "bool"}
    },

    "get_news": {
        "description": "Search recent news for external risk signals",
        "params": {"keywords": "list[str]", "location": "str", "days_back": "int"},
        "returns": {"headlines": "list", "risk_signals": "list[str]"}
    },

    "check_eot_timeliness": {
        "description": "Verifies if EoT application was filed within 14 days of hindrance",
        "params": {"hindrance_date": "str", "application_date": "str"},
        "returns": {"within_deadline": "bool", "days_late": "int"}
    },

    "calculate_net_eot": {
        "description": "Computes net eligible EoT days from hindrance register (overlap-aware)",
        "params": {"hindrance_list": "list[dict]"},
        "returns": {"net_eot_days": "int", "overlap_deducted_days": "int"}
    },

    "get_s_curve_deviation": {
        "description": "Returns S-curve deviation and trend analysis",
        "params": {"project_id": "str"},
        "returns": {"current_deviation_pct": "float", "trend": "str", "forecast_completion_day": "int"}
    },

    "lookup_escalation_next_step": {
        "description": "Given current escalation tier and days elapsed, returns next required action",
        "params": {"contract_type": "str", "current_tier": "str", "days_elapsed": "int"},
        "returns": {"next_action": "str", "responsible_party": "str", "deadline_days": "int"}
    },

    "check_catchup_refund": {
        "description": "Checks if catch-up refund clause is triggered (EPC only)",
        "params": {"project_id": "str"},
        "returns": {"refund_eligible": "bool", "refund_amount_inr": "float"}
    },

    "calculate_early_completion_bonus": {
        "description": "Calculates bonus if contractor finishes early (CPWD Clause 2A)",
        "params": {
            "contract_value_inr": "float",
            "scheduled_completion_day": "int",
            "actual_completion_day": "int",
            "clause_2a_active": "bool"
        },
        "returns": {"bonus_inr": "float", "bonus_pct": "float", "capped_at_5pct": "bool"}
    }
}
```

---

## State Passed to Every Agent

```python
AGENT_CONTEXT = {
    "project_id": "CONTRACT_001",
    "contract_type": "EPC",
    "day_number": 61,
    "scp_days": 730,
    "contract_value_inr": 250000000,
    "rule_store_summary": {
        "milestones": [...],           # abridged
        "ld_rules": {...},
        "eot_rules": {...},
        "termination_triggers": [...]
    },
    "current_execution": {
        "actual_physical_pct": 6.1,
        "s_curve_deviation": -2.1,
        "ld_accumulated_inr": 0,
        "ncrs_pending": 1,
        "row_pending_km": 3.2
    },
    "active_compliance_events": [...],  # from this cycle
    "escalation_history": [...],        # all past notices and decisions
    "conversation_history": [...]       # for multi-turn reasoning
}
```

---

## Agent Output Log (Audit Trail)

Every agent call is logged for full auditability:

```json
{
  "log_id": "AGENT-LOG-2025-06-01-003",
  "trigger": "MPR_UPLOADED",
  "cycle_id": "CYCLE-2025-06-01",
  "project_id": "CONTRACT_001",
  "agents_invoked": [
    {
      "agent": "compliance_agent",
      "invoked_at": "2025-06-01T09:12:04",
      "input_summary": "MPR Month 2 uploaded",
      "output_summary": "3 events generated: C03_M1 HIGH, C07a MEDIUM, C10 LOW",
      "tools_called": [],
      "duration_ms": 1840
    },
    {
      "agent": "penalty_agent",
      "invoked_at": "2025-06-01T09:12:06",
      "input_summary": "Event C03_M1 — delay 22 days",
      "output_summary": "LD ₹5,50,000 deducted. Cap at 2.2%.",
      "tools_called": ["calculate_ld"],
      "duration_ms": 920
    },
    {
      "agent": "explanation_agent",
      "invoked_at": "2025-06-01T09:12:08",
      "output_summary": "compliance.md updated for 3 audiences",
      "duration_ms": 3210
    }
  ],
  "total_duration_ms": 6810
}
```

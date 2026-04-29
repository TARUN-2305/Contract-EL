"""
Orchestrator Agent — routes triggers to specialist agents.
LLM backend: Groq API (llama-3.3-70b-versatile)
Ollama/gemma4:e2b kept in comments for local fallback reference.
"""
import json
from pydantic import BaseModel
from typing import Dict, Any, List

# ── Groq (primary) ──────────────────────────────────────────────────────
from utils.groq_client import groq_chat

# ── Ollama (commented out — local fallback, requires gemma4:e2b + RAM) ──

# from httpx import Timeout
# _ollama_client = ollama.Client(timeout=Timeout(300.0))

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

Trigger routing rules:
- MPR_UPLOADED        → Compliance Agent → Penalty Agent → Risk Agent → Explanation Agent
- FM_CLAIM_SUBMITTED  → EoT Agent (FM track) → Compliance Agent → Explanation Agent
- HINDRANCE_LOGGED    → EoT Agent (hindrance track) → Explanation Agent
- MILESTONE_DATE_REACHED → Compliance Agent → Penalty Agent → Escalation Agent → Explanation Agent
- CURE_PERIOD_EXPIRED → Escalation Agent → Explanation Agent
- LD_CAP_WARNING      → Escalation Agent → Explanation Agent
- VARIATION_CLAIM_FILED → Compliance Agent → Explanation Agent

Return ONLY valid JSON. No preamble, no explanation, no markdown.
Required keys: "agents_to_invoke" (list of strings), "reasoning" (string), "context_packets" (dict).
"""


class OrchestratorResponse(BaseModel):
    agents_to_invoke: List[str]
    reasoning: str
    context_packets: Dict[str, Any]


class OrchestratorAgent:
    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        # model_name kept as param for compatibility; Groq model used by default
        self.model_name = model_name

    def process_trigger(self, trigger_type: str, project_state: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[Orchestrator] Received trigger: {trigger_type} for project {project_state.get('project_id')}")

        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(
            contract_type=project_state.get("contract_type", "EPC"),
            project_name=project_state.get("project_name", "Unknown"),
            day_number=project_state.get("day_number", 0),
            scp_days=project_state.get("scp_days", 730),
            active_event_count=len(project_state.get("active_events", [])),
        )

        user_prompt = f"""
Trigger Type: {trigger_type}

Available Specialist Agents:
- Parser Agent
- Compliance Agent
- Risk Agent
- Penalty Agent
- EoT Agent
- Escalation Agent
- Explanation Agent (Must always be last)

Project State Summary:
{json.dumps(project_state, indent=2, default=str)}

Provide routing decision as JSON with keys:
  "agents_to_invoke": [list of agent names in order],
  "reasoning": "why you chose this sequence",
  "context_packets": {{agent_name: relevant_context_dict}}
"""

        try:
            print(f"[Orchestrator] Calling Groq: {self.model_name}")

            # ── Groq call ──────────────────────────────────────────────
            raw = groq_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                max_tokens=1024,
            )

            # ── Ollama fallback (comment in if Groq unavailable) ────────
            # response = _ollama_client.chat(
            #     model="gemma4:e2b",
            #     messages=[
            #         {"role": "system", "content": system_prompt},
            #         {"role": "user", "content": user_prompt},
            #     ],
            #     format="json",
            # )
            # raw = response["message"]["content"]

            # Parse JSON — strip markdown fences if present
            content = raw.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result_json = json.loads(content)

            print(f"[Orchestrator] Decision: {result_json.get('agents_to_invoke')}")
            return {
                "status": "success",
                "trigger": trigger_type,
                "orchestrator_decision": result_json,
            }

        except Exception as e:
            print(f"[Orchestrator] Error: {e} — using default routing for {trigger_type}")
            # Deterministic fallback routing when LLM fails
            default_routes = {
                "MPR_UPLOADED":           ["Compliance Agent", "Risk Agent", "Explanation Agent"],
                "FM_CLAIM_SUBMITTED":     ["EoT Agent", "Compliance Agent", "Explanation Agent"],
                "HINDRANCE_LOGGED":       ["EoT Agent", "Explanation Agent"],
                "MILESTONE_DATE_REACHED": ["Compliance Agent", "Escalation Agent", "Explanation Agent"],
                "CURE_PERIOD_EXPIRED":    ["Escalation Agent", "Explanation Agent"],
                "LD_CAP_WARNING":         ["Escalation Agent", "Explanation Agent"],
            }
            return {
                "status": "fallback",
                "trigger": trigger_type,
                "orchestrator_decision": {
                    "agents_to_invoke": default_routes.get(trigger_type, ["Compliance Agent", "Explanation Agent"]),
                    "reasoning": f"LLM unavailable ({e}) — using deterministic fallback routing.",
                    "context_packets": {},
                },
            }

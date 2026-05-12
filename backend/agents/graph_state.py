from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator

class ContractGuardState(TypedDict):
    # Inputs
    trigger_type: str
    project_id: str
    event_data: Dict[str, Any]
    project_state: Dict[str, Any]
    rule_store: Dict[str, Any]
    
    # Orchestrator routing
    agents_to_invoke: List[str]
    current_agent_index: int
    context_packets: Dict[str, Any]
    
    # Agent Outputs
    compliance_report: Optional[Dict[str, Any]]
    risk_prediction: Optional[Dict[str, Any]]
    escalation_records: Optional[List[Dict[str, Any]]]
    eot_decision: Optional[Dict[str, Any]]
    
    # Final Output
    explainer_outputs: Optional[Dict[str, Any]]
    status: str
    messages: Annotated[List[str], operator.add]

from langgraph.graph import StateGraph, END
from agents.graph_state import ContractGuardState
from agents.compliance_agent import ComplianceAgent
from agents.risk_predictor import RiskPredictor
from agents.explainer_agent import ExplainerAgent

compliance_agent = ComplianceAgent()
risk_predictor = RiskPredictor()
explainer_agent = ExplainerAgent()

def run_compliance(state: ContractGuardState):
    report = compliance_agent.run(state["event_data"])
    return {"compliance_report": report}

def run_risk(state: ContractGuardState):
    prediction = risk_predictor.predict(state["event_data"], state["rule_store"])
    import dataclasses
    return {"risk_prediction": dataclasses.asdict(prediction)}

def run_explainer(state: ContractGuardState):
    outputs = explainer_agent.explain(
        compliance_report=state["compliance_report"],
        risk_prediction=state["risk_prediction"],
        rule_store=state["rule_store"],
        exec_data=state["event_data"],
        audience=state.get("project_state", {}).get("audience", "Project Manager")
    )
    return {"explainer_outputs": outputs, "status": "completed"}

workflow = StateGraph(ContractGuardState)

workflow.add_node("compliance", run_compliance)
workflow.add_node("risk", run_risk)
workflow.add_node("explainer", run_explainer)

workflow.set_entry_point("compliance")
workflow.add_edge("compliance", "risk")
workflow.add_edge("risk", "explainer")
workflow.add_edge("explainer", END)

pipeline_app = workflow.compile()

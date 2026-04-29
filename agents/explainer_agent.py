"""
Explainer Agent — Rule-based narrative generation for compliance events and risk scores.
Generates compliance.md and risk summary in a structured, citation-rich format.
LLM narrative: available if Ollama has memory; falls back to template-based generation.
"""
import json
import os
from datetime import date, datetime
from utils.groq_client import groq_narrate
from tools.weather_tool import WeatherTool
from tools.news_tool import NewsTool

SEVERITY_EMOJI = {
    "CRITICAL": "[CRITICAL]",
    "HIGH": "[HIGH]",
    "MEDIUM": "[MEDIUM]",
    "LOW": "[LOW]",
    "INFO": "[INFO]",
}

RISK_EMOJI = {
    "CRITICAL": "CRITICAL RISK",
    "HIGH": "HIGH RISK",
    "MEDIUM": "MEDIUM RISK",
    "LOW": "LOW RISK",
}


def _inr(amount: float) -> str:
    """Format Indian currency."""
    if amount >= 1e7:
        return f"Rs. {amount/1e7:.2f} Cr"
    elif amount >= 1e5:
        return f"Rs. {amount/1e5:.2f} L"
    else:
        return f"Rs. {amount:,.0f}"


def generate_event_narrative(event: dict, rule_store: dict) -> str:
    """Generate a structured markdown narrative for a single compliance event."""
    check_id = event.get("check_id", "")
    severity = event.get("severity", "")
    title = event.get("title", "")
    clause = event.get("clause", "")
    description = event.get("description", "")
    action = event.get("action", "")
    ld = event.get("ld_accrued_inr", 0)
    financial = event.get("financial_impact_inr", 0)
    catch_up = event.get("catch_up_refund_eligible", False)

    lines = [
        f"### {SEVERITY_EMOJI.get(severity, '')} [{check_id}] {title}",
        f"**Clause:** {clause}",
        f"**Severity:** {severity}",
        f"",
        f"**What happened:**",
        f"{description}",
        "",
    ]

    if ld > 0:
        cv = rule_store.get("contract_value_inr", 0)
        ld_info = rule_store.get("liquidated_damages") or {}
        max_ld = ld_info.get("max_cap_inr") or (cv * (ld_info.get("max_cap_pct") or 10) / 100)
        cap_used = (ld / max_ld * 100) if max_ld > 0 else 0
        daily_rate = event.get("ld_daily_rate_inr", 0)
        lines.append(f"**Financial Consequence:**")
        lines.append(f"LD accrued: **{_inr(ld)}** ({cap_used:.1f}% of cap). Daily rate: {_inr(daily_rate)}/day.")
        if catch_up:
            lines.append(f"*Note: Catch-up refund eligible if final SCD is achieved on time (Article 10.3.3).*")
        lines.append("")

    if financial and financial != 0 and financial != ld:
        label = "Refund due" if financial < 0 else "Financial impact"
        lines.append(f"**{label}:** {_inr(abs(financial))}")
        lines.append("")

    lines.append(f"**Required Action:** {action.replace('_', ' ').title()}")
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def generate_compliance_report_md(
    compliance_report: dict,
    risk_prediction: dict,
    rule_store: dict,
    exec_data: dict = None,
    audience: str = "Project Manager"
) -> str:
    """Generate the full compliance.md report with Groq summary and external tools."""
    exec_data = exec_data or {}
    project_name = rule_store.get("project_name", "Unknown Project")
    contract_id = rule_store.get("contract_id", "")
    contract_type = rule_store.get("contract_type", "EPC")
    contractor_name = rule_store.get("contractor_name", "Contractor")
    cv = rule_store.get("contract_value_inr", 0)
    scp_days = rule_store.get("scp_days", 730)
    period = compliance_report.get("reporting_period", "")
    day_number = compliance_report.get("day_number", 0)
    total_ld = compliance_report.get("total_ld_accrued_inr", 0)
    ld_info = rule_store.get("liquidated_damages") or {}
    max_ld = ld_info.get("max_cap_inr") or (cv * (ld_info.get("max_cap_pct") or 10) / 100)
    ld_cap_pct = (total_ld / max_ld * 100) if max_ld > 0 else 0
    n_events = compliance_report.get("total_events", 0)
    n_critical = compliance_report.get("critical_count", 0)
    n_high = compliance_report.get("high_count", 0)
    risk_score = risk_prediction.get("risk_score", 0)
    risk_label = risk_prediction.get("risk_label", "UNKNOWN")
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M IST")

    # Call External Tools
    news_tool = NewsTool()
    weather_tool = WeatherTool()
    
    news_data = news_tool.get_entity_news(contractor_name)
    fm_events = exec_data.get("force_majeure_events", [])
    weather_data = None
    if fm_events:
        # Validate the first FM event
        weather_data = weather_tool.verify_force_majeure(fm_events[0])

    # Groq Audience-Aware Summary
    prompt = f"""
    Write a 3-sentence executive summary of this project status tailored for a {audience}.
    Project: {project_name} (Day {day_number}/{scp_days})
    Risk Score: {risk_score:.2f} ({risk_label})
    Violations: {n_critical} Critical, {n_high} High
    LD Cap Used: {ld_cap_pct:.1f}%
    News Risk Signals: {news_data.get('adverse_signals_found', 0)}
    Focus on what this specific role ({audience}) needs to know and act on immediately.
    """
    ai_summary = groq_narrate("You are an expert infrastructure project analyst.", prompt) or "AI Summary unavailable."

    lines = [
        f"# Compliance & Risk Report",
        f"**Project:** {project_name}",
        f"**Contract ID:** {contract_id}",
        f"**Contract Type:** {contract_type}",
        f"**Contract Value:** {_inr(cv)}",
        f"**Contractor:** {contractor_name}",
        f"**Reporting Period:** {period} (Day {day_number} of {scp_days})",
        f"**Target Audience:** {audience}",
        f"**Report Generated:** {report_date}",
        f"**Generated By:** ContractGuard AI",
        "",
        "---",
        "",
        "## AI Executive Summary",
        f"> {ai_summary}",
        "",
        "## Metric Overview",
        "",
        "| Item | Value | Status |",
        "|---|---|---|",
        f"| Day Number | {day_number} of {scp_days} | {'On Track' if day_number <= scp_days else 'OVERRUN'} |",
        f"| LD Accumulated | {_inr(total_ld)} ({ld_cap_pct:.1f}% of cap) | {'CRITICAL' if ld_cap_pct >= 80 else 'Clear' if ld_cap_pct < 20 else 'Warning'} |",
        f"| Active Violations | {n_events} ({n_critical} CRITICAL, {n_high} HIGH) | {'Action Required' if n_events > 0 else 'Clean'} |",
        f"| Risk Score | {risk_score:.4f} ({risk_label}) | {RISK_EMOJI.get(risk_label, risk_label)} |",
        "",
        "---",
        "",
        "## External Intelligence",
        "",
        f"### Entity Risk Signals (NewsAPI)",
        f"**Contractor:** {contractor_name}",
        f"- Articles Analyzed: {news_data.get('total_articles_analyzed', 0)}",
        f"- Adverse Signals Found: {news_data.get('adverse_signals_found', 0)}",
    ]
    
    if news_data.get("signals"):
        lines.append("- **Top Signals:**")
        for sig in news_data["signals"][:2]:
            lines.append(f"  - [{sig.get('title')}]({sig.get('url')}) (Keywords: {', '.join(sig.get('matched_keywords', []))})")
            
    lines.append("")
    
    if weather_data:
        lines.append("### Force Majeure Weather Verification")
        lines.append(f"- **Valid Weather Anomaly:** {'YES' if weather_data.get('valid') else 'NO'}")
        lines.append(f"- **Reasoning:** {weather_data.get('reason')}")
        if weather_data.get('weather_data', {}).get('extreme_rainfall_days'):
            lines.append(f"- **Extreme Rain Days:** {weather_data['weather_data']['extreme_rainfall_days']}")
        lines.append("")

    lines.append("---")
    lines.append("## Active Compliance Events")
    lines.append("")

    events = compliance_report.get("events", [])
    if not events:
        lines.append("*No compliance violations detected this period.*")
        lines.append("")
    else:
        for event in events:
            lines.append(generate_event_narrative(event, rule_store))

    # Risk section
    top_factors = risk_prediction.get("top_risk_factors", [])
    ttd = risk_prediction.get("time_to_default_estimate_days")
    lines += [
        "## Risk Assessment",
        "",
        f"**Risk Score:** {risk_score:.4f} — **{risk_label}**",
        f"**Model:** {risk_prediction.get('model_type', 'unknown')}",
    ]
    if ttd:
        lines.append(f"**Estimated Days to Trigger Default:** {ttd} days")
    if top_factors:
        lines.append("")
        lines.append("**Top Risk Drivers (SHAP):**")
        for f in top_factors[:5]:
            direction = f.get("direction", "")
            shap_val = f.get("shap_value", f.get("contribution", f.get("importance", 0)))
            lines.append(f"- `{f['feature']}`: {shap_val:+.4f} ({direction})")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated automatically by ContractGuard AI. For official use, verify all figures against source MPR.*")

    return "\n".join(lines)


class ExplainerAgent:
    def __init__(self):
        pass

    def explain(
        self,
        compliance_report: dict,
        risk_prediction: dict,
        rule_store: dict,
        exec_data: dict = None,
        audience: str = "Project Manager"
    ) -> dict:
        """Generate all outputs: compliance.md, risk summary."""
        contract_id = rule_store.get("contract_id") or compliance_report.get("contract_id")
        period = compliance_report.get("reporting_period", "unknown")
        print(f"[ExplainerAgent] Generating outputs for {contract_id} / {period} (Audience: {audience})")

        # Generate compliance.md
        compliance_md = generate_compliance_report_md(
            compliance_report, 
            risk_prediction, 
            rule_store, 
            exec_data=exec_data,
            audience=audience
        )

        os.makedirs("data/reports", exist_ok=True)
        md_path = f"data/reports/compliance_{contract_id}_{period}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(compliance_md)
        print(f"[ExplainerAgent] compliance.md written: {md_path}")

        from agents.pdf_exporter import PDFExporter
        pdf_exporter = PDFExporter()
        pdf_path = f"data/reports/compliance_{contract_id}_{period}.pdf"
        try:
            pdf_exporter.export_compliance_report(md_path, output_dir="data/reports")
            print(f"[ExplainerAgent] compliance.pdf written: {pdf_path}")
        except Exception as e:
            print(f"[ExplainerAgent] PDF export failed: {e}")
            pdf_path = ""

        # Generate risk summary
        risk_summary = {
            "contract_id": contract_id,
            "period": period,
            "audience": audience,
            "risk_score": risk_prediction.get("risk_score"),
            "risk_label": risk_prediction.get("risk_label"),
            "top_factors": risk_prediction.get("top_risk_factors", [])[:3],
            "compliance_events": compliance_report.get("total_events"),
            "critical_count": compliance_report.get("critical_count"),
            "total_ld_inr": compliance_report.get("total_ld_accrued_inr"),
        }

        summary_path = f"data/reports/risk_summary_{contract_id}_{period}.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(risk_summary, f, indent=2)

        print(f"[ExplainerAgent] Outputs complete for {contract_id}")
        return {
            "compliance_md_path": md_path,
            "compliance_pdf_path": pdf_path,
            "risk_summary_path": summary_path,
            "compliance_md": compliance_md,
            "risk_summary": risk_summary,
        }


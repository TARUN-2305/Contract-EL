"""
ContractGuard AI — Streamlit Dashboard
Role-gated views: Contract Manager, Project Manager, Site Engineer, Auditor, Contractor Rep
"""
import json
import os
import streamlit as st
import httpx
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime

API_BASE = "http://127.0.0.1:8000"

# ── Page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ContractGuard AI",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1a1a2e; margin-bottom: 0; }
    .sub-header  { font-size: 1rem; color: #555; margin-top: -8px; }
    .metric-card { background: #f8f9fa; border-radius: 10px; padding: 16px; text-align: center; border: 1px solid #e0e0e0; }
    .metric-val  { font-size: 2rem; font-weight: 700; }
    .metric-lbl  { font-size: 0.8rem; color: #666; }
    .critical    { color: #d32f2f; }
    .high        { color: #f57c00; }
    .medium      { color: #f9a825; }
    .low         { color: #388e3c; }
    .info        { color: #1976d2; }
    .event-block { background: #fff3f3; border-left: 4px solid #d32f2f; padding: 10px 14px; border-radius: 6px; margin: 8px 0; }
    .event-high  { border-color: #f57c00; background: #fff8f0; }
    .event-med   { border-color: #f9a825; background: #fffde7; }
    .event-info  { border-color: #1976d2; background: #e3f2fd; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/color/96/000000/building.png", width=60)
st.sidebar.markdown("## ContractGuard AI")
st.sidebar.markdown("---")

ROLES = ["Contract Manager", "Project Manager", "Site Engineer", "Auditor", "Contractor Rep"]
role = st.sidebar.selectbox("Select Role", ROLES)
contract_id = st.sidebar.text_input("Contract ID", value="")
st.sidebar.markdown("---")

# ── Header ─────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🏗️ ContractGuard AI</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">EPC Contract Compliance & Risk Intelligence · Role: <b>{role}</b></div>', unsafe_allow_html=True)
st.markdown("---")

# ── Load rule store ────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_rule_store(cid):
    if not cid: return None
    path = f"data/rule_store/rule_store_{cid}.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

rule_store = load_rule_store(contract_id)

# ── Contract Upload (Contract Manager only) ────────────────────────────
if role == "Contract Manager":
    with st.expander("📄 Upload Contract (PDF/DOCX)", expanded=not rule_store):
        uploaded = st.file_uploader("Upload EPC Contract File", type=["pdf", "docx"])
        col1, col2 = st.columns(2)
        with col1:
            proj_name = st.text_input("Project Name", "")
            cv = st.number_input("Contract Value (INR)", value=0, step=1_000_000)
        with col2:
            scp = st.number_input("SCP Days", value=0, step=30)
            loc = st.text_input("Location", "")
        if st.button("🚀 Parse Contract"):
            if not contract_id:
                st.warning("⚠️ Please enter a Contract ID in the sidebar before uploading.")
            elif not uploaded:
                st.warning("⚠️ Please select a contract file to upload.")
            else:
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" \
                    if uploaded.name.lower().endswith(".docx") else "application/pdf"
                with st.spinner(f"Parsing contract ({uploaded.name})..."):
                    r = httpx.post(
                        f"{API_BASE}/upload-contract",
                        files={"file": (uploaded.name, uploaded.read(), mime)},
                        data={"contract_id": contract_id, "contract_type": "EPC",
                              "contract_value_inr": str(cv), "scp_days": str(scp),
                              "project_name": proj_name, "location": loc},
                        timeout=300,
                    )
                if r.status_code == 200:
                    st.success(f"✅ Contract parsed! Keys: {r.json().get('rule_store_keys')}")
                    st.cache_data.clear()
                else:
                    st.error(f"Error {r.status_code}: {r.text[:500]}")

# ── Rule Store Overview ────────────────────────────────────────────────
if rule_store:
    with st.expander("📋 Contract Rule Store", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Project:** {rule_store.get('project_name', '—')}")
            st.markdown(f"**Contract ID:** {rule_store.get('contract_id', '—')}")
            st.markdown(f"**Type:** {rule_store.get('contract_type', '—')}")
        with col2:
            cv = rule_store.get("contract_value_inr", 0)
            st.markdown(f"**Contract Value:** ₹{cv/1e7:.2f} Cr")
            st.markdown(f"**SCP Days:** {rule_store.get('scp_days', '—')}")
            ld = rule_store.get("liquidated_damages") or {}
            st.markdown(f"**LD Rate:** {ld.get('daily_rate_pct', '—')}%/day")
        with col3:
            milestones = rule_store.get("milestones") or []
            st.markdown(f"**Milestones:** {len(milestones)}")
            ps = rule_store.get("performance_security") or {}
            st.markdown(f"**Perf. Security:** {ps.get('pct_of_contract_value', '—')}%")
            st.markdown(f"**LD Cap:** {ld.get('max_cap_pct', '—')}%")

        if milestones:
            st.markdown("**Milestone Schedule:**")
            m_df = pd.DataFrame([
                {"ID": m["id"], "Name": m["name"],
                 "Day": m.get("trigger_day", "—"),
                 "Progress Required": f"{m.get('required_physical_progress_pct', '—')}%",
                 "LD Rate": f"{m.get('ld_rate_pct_per_day', '—')}%/day",
                 "Catch-Up": "Yes" if m.get("catch_up_refund_eligible") else "No"}
                for m in milestones
            ])
            st.dataframe(m_df, use_container_width=True, hide_index=True)

# ── MPR Analysis Panel ──────────────────────────────────────────────────
st.markdown("## 📊 MPR Compliance Analysis")

mpr_file = st.file_uploader("Upload Monthly Progress Report (.md or .docx)", type=["md", "docx"])
with st.form("mpr_upload_form"):
    prev_pct = st.number_input("Previous Month Actual Progress (%)", value=0.0, min_value=0.0, max_value=100.0, step=0.5)
    run_btn = st.form_submit_button("🔍 Run Full Analysis")

if run_btn and mpr_file is not None:
    with st.spinner("Parsing MPR and running compliance + risk analysis..."):
        try:
            files_payload = {"file": (mpr_file.name, mpr_file.getvalue(), "application/octet-stream")}
            form_data = {
                "contract_id": contract_id,
                "prev_actual_pct": str(prev_pct),
                "audience": role,
            }
            r = httpx.post(f"{API_BASE}/upload-mpr", files=files_payload, data=form_data, timeout=120)
            if r.status_code == 200:
                result = r.json()
                comp = result.get("compliance", {})
                risk = result.get("risk", {})
                parsed = result.get("parsed_mpr", {})

                # Store in session state for role-specific panels
                st.session_state["last_compliance_result"] = comp
                st.session_state["last_risk_result"] = risk
                st.session_state["last_parsed_mpr"] = parsed

                # Key metrics from parsed MPR
                day_number_res = parsed.get("day_number", 730)
                actual_pct_res = parsed.get("actual_physical_pct", 0.0)

                # ── Summary metrics ──────────────────────────────────────────
                st.markdown("### 📈 Analysis Results")
                st.caption(f"📄 **{parsed.get('project_name', 'N/A')}** · Day **{day_number_res}** · Contractor: {parsed.get('contractor_name', 'N/A')}")
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Risk Score", f"{risk.get('score', 0):.4f}", delta=risk.get("label"))
                with m2:
                    st.metric("Compliance Events", comp.get("total_events", 0),
                              delta=f"{comp.get('critical_count', 0)} CRITICAL")
                with m3:
                    ld_total = comp.get("total_ld_accrued_inr", 0)
                    st.metric("LD Accrued", f"₹{ld_total/1e5:.1f}L" if ld_total >= 1e5 else f"₹{ld_total:,.0f}")
                with m4:
                    ttd = risk.get("ttd_days")
                    st.metric("Time to Default", f"{ttd} days" if ttd else "N/A")

                # ── Download Buttons ──────────────────────────────────────────
                reports = result.get("reports", {})
                col_l, col_r, col_p = st.columns(3)
                with col_l:
                    md_path = reports.get("compliance_md", "")
                    if md_path and os.path.exists(md_path):
                        with open(md_path, encoding="utf-8") as f:
                            md_content = f.read()
                        st.download_button("📥 Markdown", md_content,
                                           file_name=os.path.basename(md_path), mime="text/markdown", use_container_width=True)
                with col_r:
                    risk_path = reports.get("risk_summary", "")
                    if risk_path and os.path.exists(risk_path):
                        with open(risk_path, encoding="utf-8") as f:
                            rs_content = f.read()
                        st.download_button("📥 JSON Summary", rs_content,
                                           file_name=os.path.basename(risk_path), mime="application/json", use_container_width=True)
                with col_p:
                    pdf_path = reports.get("compliance_pdf", "")
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            pdf_content = f.read()
                        st.download_button("📥 PDF Report", pdf_content,
                                           file_name=os.path.basename(pdf_path), mime="application/pdf", use_container_width=True)

                st.markdown("---")

                # ── S-Curve and SHAP Charts ───────────────────────────────────
                st.markdown("### 📊 Project Trajectory & Risk Drivers")
                c1, c2 = st.columns([1.2, 1])

                with c1:
                    scp_days = rule_store.get("scp_days", 730) or 730
                    days_list = list(range(0, scp_days + 30, 30))
                    if day_number_res not in days_list:
                        days_list.append(day_number_res)
                    days_list = sorted(days_list)

                    planned_curve = [min(100.0, (d / scp_days) * 100) for d in days_list]
                    actual_curve = [
                        min(actual_pct_res, (d / max(day_number_res, 1)) * actual_pct_res)
                        if d <= day_number_res else None
                        for d in days_list
                    ]

                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=days_list, y=planned_curve, mode="lines",
                                               name="Planned (%)", line=dict(color="#2196F3", dash="dash")))
                    fig_s.add_trace(go.Scatter(x=days_list, y=actual_curve, mode="lines+markers",
                                               name="Actual (%)", line=dict(color="#FF9800", width=3)))
                    fig_s.add_vline(x=day_number_res, line_dash="dot", line_color="gray", annotation_text="Today")
                    fig_s.add_vline(x=scp_days, line_dash="dot", line_color="red", annotation_text="SCD")
                    fig_s.update_layout(title="Project S-Curve", xaxis_title="Days from Appointed Date",
                                        yaxis_title="Progress (%)", height=350,
                                        margin=dict(l=20, r=20, t=40, b=20),
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig_s, use_container_width=True)

                with c2:
                    top_factors = risk.get("top_factors", [])
                    if top_factors:
                        df_shap = pd.DataFrame(top_factors).iloc[::-1].reset_index(drop=True)
                        val_col = next((c for c in ["shap_value", "importance", "contribution"] if c in df_shap.columns), None)
                        if val_col:
                            df_shap["val"] = df_shap[val_col]
                            df_shap["color"] = df_shap["direction"].apply(
                                lambda x: "#ef5350" if x == "Increases risk" else "#66bb6a")
                            fig_shap = px.bar(df_shap, x="val", y="feature", orientation="h",
                                              title="Top Risk Drivers (SHAP)",
                                              color="color",
                                              color_discrete_map="identity")
                            fig_shap.update_layout(showlegend=False, height=350,
                                                   margin=dict(l=20, r=20, t=40, b=20),
                                                   xaxis_title="Impact on Risk Score")
                            st.plotly_chart(fig_shap, use_container_width=True)
                        else:
                            st.info("SHAP data format unrecognised.")
                    else:
                        st.info("No SHAP factors available for this scenario.")

                st.markdown("---")

                # ── Compliance Report Preview ──────────────────────────────────
                with st.expander("📄 Compliance Report Preview", expanded=True):
                    preview = result.get("compliance_md_preview", "")
                    st.markdown(preview.replace("...", ""))

            else:
                st.error(f"API Error ({r.status_code}): {r.text[:500]}")
        except Exception as e:
            st.error(f"Connection error: {e}")
elif run_btn and mpr_file is None:
    st.warning("⚠️ Please upload an MPR file before running the analysis.")

# ── Role-Specific Panels ────────────────────────────────────────────────
st.markdown("---")

if role == "Auditor":
    st.markdown("### 🔍 Audit Trail")
    compliance_dir = "data/compliance"
    if os.path.exists(compliance_dir):
        files = sorted(os.listdir(compliance_dir), reverse=True)
        if files:
            selected = st.selectbox("Select report", files)
            with open(os.path.join(compliance_dir, selected), encoding="utf-8") as f:
                report = json.load(f)
            st.json(report)
        else:
            st.info("No compliance reports yet.")
    else:
        st.info("No audit trail available.")

elif role == "Site Engineer":
    st.markdown("### 🔧 Field Action Items")
    if "last_compliance_result" in st.session_state:
        field_events = [
            e for e in st.session_state["last_compliance_result"].get("events", [])
            if e["severity"] in ("HIGH", "MEDIUM")
        ]
        if field_events:
            for ev in field_events:
                st.markdown(f"**[{ev['severity']}] {ev['title']}**")
                st.markdown(f"_{ev['description']}_")
                st.markdown(f"➡️ **Action:** {ev['action'].replace('_', ' ').title()}")
                st.markdown("---")
        else:
            st.success("✅ No field actions required — project on track.")
    elif os.path.exists("data/compliance") and sorted(os.listdir("data/compliance")):
        files = sorted(os.listdir("data/compliance"), reverse=True)
        with open(os.path.join("data/compliance", files[0]), encoding="utf-8") as f:
            latest = json.load(f)
        field_events = [e for e in latest.get("events", []) if e["severity"] in ("HIGH", "MEDIUM")]
        if field_events:
            for ev in field_events:
                st.markdown(f"**[{ev['severity']}] {ev['title']}**")
                st.markdown(f"_{ev['description']}_")
                st.markdown(f"➡️ **Action:** {ev['action'].replace('_', ' ').title()}")
                st.markdown("---")
        else:
            st.success("✅ No field actions required — project on track.")
    else:
        st.info("Upload and analyse an MPR to see field action items.")

elif role == "Contractor Rep":
    st.markdown("### 📋 Contractor View")
    st.info("View your current compliance status and pending actions. LD deductions and payment status visible here.")
    if "last_compliance_result" in st.session_state:
        latest = st.session_state["last_compliance_result"]
        st.markdown(f"**Latest Period:** {latest.get('reporting_period', '—')}")
        st.markdown(f"**Total Events:** {latest.get('total_events', 0)}")
        ld = latest.get('total_ld_accrued_inr', 0)
        st.markdown(f"**LD Accrued:** ₹{ld:,.0f}")
    elif os.path.exists("data/compliance") and sorted(os.listdir("data/compliance")):
        files = sorted(os.listdir("data/compliance"), reverse=True)
        with open(os.path.join("data/compliance", files[0]), encoding="utf-8") as f:
            latest = json.load(f)
        st.markdown(f"**Latest Period:** {latest.get('reporting_period', '—')}")
        st.markdown(f"**Total Events:** {latest.get('total_events', 0)}")
        ld = latest.get('total_ld_accrued_inr', 0)
        st.markdown(f"**LD Accrued:** ₹{ld:,.0f}")
    else:
        st.info("Upload and analyse an MPR to see contractor view.")

# Footer
st.markdown("---")
st.markdown("*ContractGuard AI · Powered by XGBoost + Deterministic Rule Engine · EL Spec v1.0*")

import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

const PERSONAS = [
  {
    id: 'contract_manager',
    title: 'Contract Manager',
    subtitle: 'Engineer-in-Charge (EiC) / Divisional Engineer',
    side: 'Government / NHAI Authority Side',
    color: '#3b82f6',
    icon: '🏛️',
    tasks: [
      'Upload the signed contract PDF/DOCX to the system',
      'Review the LLM-extracted rule store (milestones, LD rates, FM clauses)',
      'Approve or reject each extracted rule (flag ⚠️ UNRESOLVED fields)',
      'Set the project baseline: appointed date, contract value, SCP days',
      'Monitor violation summaries and approve LD deductions',
    ],
    data_produces: [
      'Approved rule_store_{contract_id}.json — the legal source of truth',
      'extraction_audit_{contract_id}.json — evidence trail of which PDF clauses were used',
      'Project metadata in PostgreSQL (contract value, SCP, location)',
    ],
    data_consumes: [
      'LLM-extracted clause summaries (review before approving)',
      'Violation summaries per MPR cycle',
      'Escalation notices that require authority signature',
    ],
    panel_view: 'Sees ALL data — the only role with approve/reject access to the rule store.',
    format_note: 'Upload format: PDF or DOCX of signed NITI Aayog EPC / CPWD GCC contract.',
    evidence_chain: [
      'PDF → pdfplumber extraction → semantic chunks (respect Article boundaries)',
      'Chunks → sentence-transformers (all-MiniLM-L6-v2) → 384-dim vectors → Qdrant',
      'Query: top-5 semantically similar chunks per field → regex extraction → LLM fallback',
      'Validation: LD rate 0–1%/day, cap=10%, PS=4–10%, FM notice=7 days',
    ],
    what_they_dont_see: 'No contractor financial data beyond what is relevant to the authority.',
    legal_basis: 'NITI Aayog EPC Agreement Art. 10–23; CPWD GCC 2023 Clauses 1–12',
  },
  {
    id: 'site_engineer',
    title: 'Site Engineer',
    subtitle: 'Junior Engineer (JE) / Assistant Engineer (AE)',
    side: 'On the Ground — Field Level',
    color: '#10b981',
    icon: '🔧',
    tasks: [
      'Fill in the Monthly Progress Report (MPR) Markdown template',
      'Upload MPR by the 5th of each following month',
      'Log hindrance register entries on occurrence of any disruption',
      'Submit Quality Assurance test results (concrete, soil, bitumen)',
      'Flag pending GFC drawings and utility clearances',
    ],
    data_produces: [
      'MPR .md file with all 11 sections filled (Section 1–11)',
      'Hindrance Register entries (joint sign with Contractor JE)',
      'QA test results (cube strength, FDT, Marshall tests)',
      'RA Bill trigger data (bill number, amount, submission date)',
    ],
    data_consumes: [
      'NCR (Non-Conformance Reports) issued against their work',
      'Compliance flags specific to field actions they can fix',
      'EoT application status for hindrances they logged',
    ],
    panel_view: 'Sees only field-actionable items: NCRs, hindrance status, QA failures. No risk scores or financial LD data.',
    format_note: 'Upload format: .md file following the exact MPR template (Sections 1–11). LLM can auto-fill from uploaded PDF.',
    evidence_chain: [
      'MPR .md → regex parser extracts all 11 sections (field-by-field)',
      'Validation: 5 rules (monotonic progress, date sanity, labour > 0, etc.)',
      'Falls back to LLM extraction for malformed or PDF-converted fields',
      'Parsed data feeds Compliance Engine → all 15 checks trigger automatically',
    ],
    what_they_dont_see: 'No financial LD totals, no risk score, no escalation matrix. Only their specific action items.',
    legal_basis: 'CPWD GCC 2023 Clause 5 (MPR obligation); IS:456, MoRTH Sec 300/500 (QA frequencies)',
  },
  {
    id: 'project_manager',
    title: 'Project Manager',
    subtitle: 'Superintending Engineer (SE) / Project Director',
    side: 'Government / Authority Oversight',
    color: '#8b5cf6',
    icon: '📊',
    tasks: [
      'Monitor all active projects on the risk dashboard',
      'Review S-curve deviations (planned vs actual progress over time)',
      'Approve or reject Extension of Time (EoT) and Variation Orders',
      'Act on HIGH/CRITICAL risk alerts before they become defaults',
      'Review SHAP-explained risk factors and top drivers',
    ],
    data_produces: [
      'EoT approval / rejection decisions (stored in eot_decisions_{project_id}.json)',
      'Variation order approvals (scope changes beyond 10% require consent)',
      'Escalation authorizations (trigger DRC or termination notice)',
    ],
    data_consumes: [
      'Risk score (0–1) + risk label (LOW/MEDIUM/HIGH/CRITICAL) from XGBoost',
      'S-curve data (all historical MPRs: planned vs actual %)',
      'SHAP top-risk-factors (which specific indicators are driving the score)',
      'Time-to-default estimate in days',
    ],
    panel_view: 'Dashboard with S-curve chart, risk score trend, active compliance events, pending EoT decisions.',
    format_note: 'No file upload required. Consumes analysis outputs.',
    evidence_chain: [
      'XGBoost model trained on 26 features derived from MPR execution data',
      'SHAP explainability: each risk factor shows its signed contribution to score',
      'S-curve: pulled from mpr_history table (all periods for project)',
      'Time-to-default: linear extrapolation from current trajectory + LD cap distance',
    ],
    what_they_dont_see: 'Raw contractor financial claims, specific QA test records (not their domain).',
    legal_basis: 'NITI Aayog EPC Art. 13 (Variation Orders); CPWD GCC Clause 5 (EoT authority)',
  },
  {
    id: 'contractor',
    title: 'Contractor Representative',
    subtitle: 'Site Contractor / Concessionaire',
    side: 'Construction Company — Opposite Side',
    color: '#f59e0b',
    icon: '🏗️',
    tasks: [
      'View LD calculations accrued against their contract',
      'Submit Force Majeure (FM) claims with supporting evidence',
      'Submit Extension of Time (EoT) applications via Hindrance Register',
      'View their own compliance violations — not other contractors',
      'Submit Quality Test results and NCR closure reports',
    ],
    data_produces: [
      'FM claims with event description, IMD proof, impact assessment',
      'EoT applications citing specific Hindrance Register entries',
      'Quality test certificates (cube strength, FDT, Marshall)',
    ],
    data_consumes: [
      'Their own LD calculation trail (daily rate × delay days, capped at 10%)',
      'Violation notices with specific clause references',
      'EoT decision outcomes (granted days)',
      'FM claim validation results (weather API cross-check)',
    ],
    panel_view: 'Intentionally limited: sees ONLY their own project data. No risk scores, no authority internal assessments.',
    format_note: 'FM claims via form with supporting documents. EoT via Hindrance Register form.',
    evidence_chain: [
      'LD calculation: (ld_rate_pct/100) × basis_value × delay_days, capped at max_cap_inr',
      'FM validation: weather API (Open-Meteo free historical data) cross-checks claimed dates',
      'EoT: overlap calculator removes duplicate hindrance days, applies 14-day application rule',
      'Catch-up refund: if M4 achieved on time, all prior milestone LDs are refunded (Art. 10.3.3)',
    ],
    what_they_dont_see: 'Other contractors, authority internal risk assessments, SHAP factors, PM decision rationale.',
    legal_basis: 'NITI Aayog EPC Art. 10.3.3 (catch-up), Art. 19 (FM); CPWD GCC Clause 5 (EoT)',
  },
  {
    id: 'auditor',
    title: 'Auditor',
    subtitle: 'CAG / Internal Audit / Authority\'s Engineer',
    side: 'Third-Party / Government Audit Body',
    color: '#6b7280',
    icon: '📋',
    tasks: [
      'Read-only access to ALL project data across ALL contracts',
      'Download compliance PDF reports with timestamped evidence',
      'Review the full penalty ledger with calculation methodology',
      'Verify FM claim approvals against weather API data',
      'Access the complete agent decision audit trail',
    ],
    data_produces: 'Nothing — read-only role. All data is consumed, not produced.',
    data_consumes: [
      'Full compliance_events table with check IDs, clauses, calculations',
      'penalty_ledger with LD calculation trail (each deduction auditable)',
      'eot_decisions with FM validation evidence (weather data cross-reference)',
      'All agent decisions with reasoning + clause references',
      'Downloadable PDF reports (fpdf2 generated)',
    ],
    panel_view: 'Full audit trail with timestamps. Can download PDF compliance reports. Can see ALL projects.',
    format_note: 'No upload capability. Downloads PDF/JSON reports for offline review.',
    evidence_chain: [
      'Every compliance event stored with: check_id, severity, clause, description, financial_impact, timestamp',
      'Every LLM decision stored with: system_prompt context, extracted JSON, model used, fallback chain used',
      'Weather API responses cached and stored (evidence for FM validation)',
      'All database writes are append-only (no overwrites) — full history preserved',
    ],
    what_they_dont_see: 'Nothing — sees everything. This is the maximum-access role.',
    legal_basis: 'CAG of India audit rights; CPWD GCC Clause 16 (inspection rights); RTI Act 2005',
  },
];

function EvidenceList({ items }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {(Array.isArray(items) ? items : [items]).map((item, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12, color: 'var(--text-muted)' }}>
          <span style={{ color: 'var(--primary)', marginTop: 2 }}>→</span>
          <span style={{ lineHeight: 1.6 }}>{item}</span>
        </div>
      ))}
    </div>
  );
}

export default function PersonasPage() {
  const [expanded, setExpanded] = useState('contract_manager');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">User Roles & Responsibilities</h1>
          <p className="page-subtitle">Detailed breakdown of all 5 personas — what they do, what they see, and the evidence chain behind each action</p>
        </div>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', marginBottom: 20, fontSize: 13, color: 'var(--text-muted)' }}>
        <strong style={{ color: 'var(--text-main)' }}>Architecture Note:</strong> ContractGuard AI is built for Indian public infrastructure contracts under NITI Aayog EPC and CPWD GCC 2023 frameworks.
        The 5-persona model maps directly to real government project roles — every piece of information displayed is access-controlled by role.
        No persona sees data outside their legal and operational mandate.
      </div>

      {PERSONAS.map(p => (
        <div key={p.id} style={{ marginBottom: 12, border: `1px solid ${p.color}30`, borderRadius: 10, overflow: 'hidden' }}>
          {/* Header */}
          <div
            onClick={() => setExpanded(expanded === p.id ? null : p.id)}
            style={{ padding: '16px 20px', cursor: 'pointer', background: expanded === p.id ? `${p.color}10` : 'var(--bg-card)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <span style={{ fontSize: 28 }}>{p.icon}</span>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16, fontWeight: 700 }}>{p.title}</span>
                  <span style={{ background: `${p.color}20`, color: p.color, fontSize: 11, padding: '2px 10px', borderRadius: 20, fontWeight: 600 }}>{p.side}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{p.subtitle}</div>
              </div>
            </div>
            {expanded === p.id ? <ChevronUp size={18} color={p.color} /> : <ChevronDown size={18} />}
          </div>

          {/* Expanded content */}
          {expanded === p.id && (
            <div style={{ padding: '20px', background: 'var(--bg-elevated)', borderTop: `1px solid ${p.color}20` }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {/* Left column */}
                <div>
                  <Section title="What They Do (Tasks)" color={p.color}>
                    <EvidenceList items={p.tasks} />
                  </Section>

                  <Section title="Data They Produce" color={p.color}>
                    <EvidenceList items={p.data_produces} />
                  </Section>

                  <Section title="Data They Consume" color={p.color}>
                    <EvidenceList items={p.data_consumes} />
                  </Section>
                </div>

                {/* Right column */}
                <div>
                  <Section title="Dashboard View (What They Actually See)" color={p.color}>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>{p.panel_view}</p>
                  </Section>

                  <Section title="Upload / Input Format" color={p.color}>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>{p.format_note}</p>
                  </Section>

                  <Section title="Evidence Chain (Technical Audit Trail)" color={p.color}>
                    <EvidenceList items={p.evidence_chain} />
                  </Section>

                  <Section title="Access Restrictions" color="#ef4444">
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>{p.what_they_dont_see}</p>
                  </Section>

                  <Section title="Legal Basis" color="#f59e0b">
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>{p.legal_basis}</p>
                  </Section>
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Section({ title, color, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: color, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 3, height: 12, background: color, borderRadius: 2 }} />
        {title}
      </div>
      {children}
    </div>
  );
}

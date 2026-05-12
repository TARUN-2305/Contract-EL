import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, Cpu, Loader, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Activity, FileText } from 'lucide-react';
import { useApp } from '../context/AppContext';

const SEVERITY_CONFIG = {
  CRITICAL: { bg: '#ef444415', border: '#ef4444', color: '#ef4444', icon: '🚨' },
  HIGH:     { bg: '#f59e0b15', border: '#f59e0b', color: '#f59e0b', icon: '⚠️' },
  MEDIUM:   { bg: '#3b82f615', border: '#3b82f6', color: '#3b82f6', icon: '📋' },
  LOW:      { bg: '#10b98115', border: '#10b981', color: '#10b981', icon: 'ℹ️' },
};

const RISK_CONFIG = {
  CRITICAL: { color: '#ef4444', bg: '#ef444420' },
  HIGH:     { color: '#f59e0b', bg: '#f59e0b20' },
  MEDIUM:   { color: '#3b82f6', bg: '#3b82f620' },
  LOW:      { color: '#10b981', bg: '#10b98120' },
};

function ComplianceEventCard({ event, index }) {
  const [open, setOpen] = useState(index < 2);
  const cfg = SEVERITY_CONFIG[event.severity] || SEVERITY_CONFIG.LOW;
  return (
    <div style={{ border: `1px solid ${cfg.border}40`, borderRadius: 8, marginBottom: 10, overflow: 'hidden' }}>
      <div onClick={() => setOpen(o => !o)} style={{ padding: '10px 14px', background: cfg.bg, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16 }}>{cfg.icon}</span>
          <div>
            <span style={{ color: cfg.color, fontWeight: 700, fontSize: 12, marginRight: 8 }}>[{event.severity}]</span>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{event.title}</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {event.ld_accrued_inr > 0 && (
            <span style={{ color: '#ef4444', fontSize: 12, fontWeight: 600 }}>LD: ₹{event.ld_accrued_inr?.toLocaleString()}</span>
          )}
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>
      {open && (
        <div style={{ padding: '12px 14px' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
            <strong>Clause:</strong> <span style={{ color: '#f59e0b' }}>{event.clause}</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.6 }}>{event.description}</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {event.action && (
              <div style={{ background: 'var(--bg-dark)', borderRadius: 6, padding: '6px 12px', fontSize: 11 }}>
                <span style={{ color: 'var(--text-subtle)' }}>Action: </span>
                <span style={{ color: cfg.color, fontWeight: 600 }}>{event.action}</span>
              </div>
            )}
            {event.catch_up_refund_eligible && (
              <div style={{ background: '#10b98115', borderRadius: 6, padding: '6px 12px', fontSize: 11, color: '#10b981' }}>
                ✓ Catch-up refund eligible (Art. 10.3.3)
              </div>
            )}
            {event.financial_impact_inr > 0 && (
              <div style={{ background: '#ef444415', borderRadius: 6, padding: '6px 12px', fontSize: 11, color: '#ef4444' }}>
                Financial Impact: ₹{event.financial_impact_inr?.toLocaleString()}
              </div>
            )}
          </div>
          {/* Evidence explanation */}
          <div style={{ marginTop: 10, background: 'var(--bg-dark)', borderRadius: 6, padding: '8px 12px', fontSize: 11, color: 'var(--text-subtle)' }}>
            <strong style={{ color: 'var(--text-muted)' }}>How this was detected: </strong>
            Check {event.check_id} — deterministic rule evaluation against the contract rule store. No LLM involved in this detection — pure contractual math.
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalysisPage() {
  const { contractId, role } = useApp();
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({
    prev_actual_pct: '0', audience: 'project_manager',
    day_number: '', actual_physical_pct: '', planned_physical_pct: '',
    ncrs_pending: '', days_lost_rainfall: '',
  });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [llmLoading, setLlmLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [llmExtracted, setLlmExtracted] = useState(null);
  const fileRef = useRef();

  const PERSONA_AUDIENCES = [
    { value: 'contract_manager', label: 'Contract Manager (EiC) — Full violations, clause refs' },
    { value: 'site_engineer', label: 'Site Engineer (JE/AE) — Actionable field items, NCRs' },
    { value: 'project_manager', label: 'Project Manager (SE) — Risk dashboard, S-curve, escalation' },
    { value: 'contractor', label: 'Contractor Rep — LD calculations, FM claims, EoT status' },
    { value: 'auditor', label: 'Auditor (CAG) — Full audit trail, compliance history, penalties' },
  ];

  const handleLLMExtract = async () => {
    if (!file) return;
    setLlmLoading(true);
    setStatus({ type: 'info', msg: '🤖 LLM reading your MPR... (using project history for context)' });
    const fd = new FormData();
    fd.append('file', file);
    fd.append('project_id', contractId);
    try {
      const res = await axios.post('/api/llm-extract-mpr', fd, { timeout: 300000 });
      const ext = res.data.extracted;
      setLlmExtracted(ext);
      if (ext.day_number) setForm(f => ({ ...f, day_number: String(ext.day_number) }));
      if (ext.actual_physical_pct != null) setForm(f => ({ ...f, actual_physical_pct: String(ext.actual_physical_pct) }));
      if (ext.previous_actual_physical_pct != null) setForm(f => ({ ...f, prev_actual_pct: String(ext.previous_actual_physical_pct) }));
      if (ext.planned_physical_pct != null) setForm(f => ({ ...f, planned_physical_pct: String(ext.planned_physical_pct) }));
      if (ext.ncrs_pending != null) setForm(f => ({ ...f, ncrs_pending: String(ext.ncrs_pending) }));
      if (ext.days_lost_rainfall != null) setForm(f => ({ ...f, days_lost_rainfall: String(ext.days_lost_rainfall) }));
      setStatus({ type: 'success', msg: `✅ LLM extracted fields (used ${res.data.history_used} previous MPRs for context). Review values below.` });
    } catch (err) {
      setStatus({ type: 'error', msg: `LLM MPR extraction failed: ${err.response?.data?.detail || err.message}` });
    } finally { setLlmLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file && !form.actual_physical_pct) return;
    setLoading(true);
    setResult(null);
    setStatus({ type: 'info', msg: '⚙️ Running 15 compliance checks + XGBoost risk prediction + LLM explanation...' });
    const fd = new FormData();
    if (file) fd.append('file', file);
    fd.append('contract_id', contractId);
    fd.append('prev_actual_pct', form.prev_actual_pct);
    fd.append('audience', form.audience);
    try {
      const res = await axios.post('/api/upload-mpr', fd, { timeout: 600000 });
      setResult(res.data);
      setStatus({ type: 'success', msg: `✅ Analysis complete — ${res.data.compliance?.total_events} events, Risk: ${res.data.risk?.label}` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setStatus({ type: 'error', msg: typeof detail === 'object' ? JSON.stringify(detail) : (detail || err.message) });
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">MPR Analysis</h1>
          <p className="page-subtitle">Upload Monthly Progress Report → 15 compliance checks + XGBoost risk + LLM explanation</p>
        </div>
      </div>

      {/* Persona grid for MPR roles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 20 }}>
        {[
          { role: 'Site Engineer', color: '#10b981', task: 'Uploads MPR (.md)', format: '.md file per template', evidence: 'Parsed exec_data.csv' },
          { role: 'Contract Manager', color: '#3b82f6', task: 'Reviews violations', format: 'Compliance events JSON', evidence: 'Clause-referenced events' },
          { role: 'Project Manager', color: '#8b5cf6', task: 'Monitors S-curve & risk', format: 'Risk score + factors', evidence: 'XGBoost SHAP values' },
          { role: 'Contractor Rep', color: '#f59e0b', task: 'Views LD + FM claims', format: 'Penalty ledger', evidence: 'LD calculation trail' },
          { role: 'Auditor', color: '#6b7280', task: 'Full audit trail', format: 'PDF report download', evidence: 'Timestamped decisions' },
        ].map(p => (
          <div key={p.role} style={{ background: 'var(--bg-card)', border: `1px solid ${p.color}30`, borderRadius: 8, padding: '10px 12px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: p.color, marginBottom: 6, textTransform: 'uppercase' }}>{p.role}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}><strong>Does:</strong> {p.task}</div>
            <div style={{ fontSize: 10, color: 'var(--text-subtle)' }}>Evidence: {p.evidence}</div>
          </div>
        ))}
      </div>

      {status && (
        <div className={`alert ${status.type === 'success' ? 'alert-success' : status.type === 'info' ? 'alert-info' : 'alert-danger'}`}>
          {status.msg}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: result ? '420px 1fr' : '1fr', gap: 20 }}>
        {/* Upload form */}
        <div className="card">
          <h3 style={{ marginBottom: 16, fontSize: 16 }}>Upload MPR</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">MPR File (.md or .docx)</label>
              <div className={`upload-zone ${file ? 'dragover' : ''}`} onClick={() => fileRef.current.click()}>
                <div className="upload-zone-icon"><Upload size={28} /></div>
                <p style={{ fontSize: 13 }}>Monthly Progress Report file</p>
                {file && <p className="file-selected"><FileText size={12} style={{ display: 'inline' }} /> {file.name}</p>}
              </div>
              <input ref={fileRef} type="file" accept=".md,.docx" style={{ display: 'none' }} onChange={e => setFile(e.target.files[0])} />
            </div>

            {file && (
              <button type="button" onClick={handleLLMExtract} disabled={llmLoading}
                style={{ width: '100%', marginBottom: 14, background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', border: 'none', borderRadius: 8, padding: '9px 16px', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                {llmLoading ? <Loader size={12} className="spin" /> : <Cpu size={12} />}
                🤖 Auto-Extract Fields (LLM reads the MPR + history)
              </button>
            )}

            {/* LLM extracted preview */}
            {llmExtracted && (
              <div style={{ background: '#7c3aed15', border: '1px solid #7c3aed30', borderRadius: 8, padding: '10px 12px', marginBottom: 14, fontSize: 11 }}>
                <div style={{ color: '#7c3aed', fontWeight: 700, marginBottom: 6 }}>LLM Extracted (review before submitting):</div>
                <div style={{ color: 'var(--text-muted)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
                  {llmExtracted.actual_physical_pct != null && <div>Actual %: <strong>{llmExtracted.actual_physical_pct}</strong></div>}
                  {llmExtracted.planned_physical_pct != null && <div>Planned %: <strong>{llmExtracted.planned_physical_pct}</strong></div>}
                  {llmExtracted.day_number != null && <div>Day No: <strong>{llmExtracted.day_number}</strong></div>}
                  {llmExtracted.ncrs_pending != null && <div>NCRs Pending: <strong>{llmExtracted.ncrs_pending}</strong></div>}
                  {llmExtracted.days_lost_rainfall != null && <div>Rainfall Days Lost: <strong>{llmExtracted.days_lost_rainfall}</strong></div>}
                </div>
                {llmExtracted.confidence_notes && <div style={{ color: '#f59e0b', marginTop: 6 }}>Note: {llmExtracted.confidence_notes}</div>}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Audience (report tailored for)</label>
              <select className="form-control" value={form.audience} onChange={e => setForm({ ...form, audience: e.target.value })}>
                {PERSONA_AUDIENCES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Previous Month Actual % (for S-curve)</label>
              <input className="form-control" type="number" step="0.1" value={form.prev_actual_pct}
                onChange={e => setForm({ ...form, prev_actual_pct: e.target.value })} />
            </div>

            <button className="btn" type="submit" disabled={loading || !file || !contractId}>
              {loading ? <><Loader size={14} className="spin" /> Running analysis...</> : '▶ Run Full Compliance Analysis'}
            </button>
          </form>
        </div>

        {/* Results */}
        {result && (
          <div>
            {/* Risk banner */}
            {result.risk && (
              <div style={{ background: RISK_CONFIG[result.risk.label]?.bg || '#33333330', border: `1px solid ${RISK_CONFIG[result.risk.label]?.color || '#333'}40`, borderRadius: 10, padding: '16px 20px', marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Risk Assessment</div>
                    <div style={{ fontSize: 28, fontWeight: 800, color: RISK_CONFIG[result.risk.label]?.color }}>{result.risk.label}</div>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Score: {result.risk.score?.toFixed(3)} | {result.risk.ttd_days ? `Est. ${result.risk.ttd_days} days to default` : 'No default risk detected'}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 11, color: 'var(--text-subtle)', marginBottom: 4 }}>LD Accrued</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#ef4444' }}>₹{result.compliance?.total_ld_accrued_inr?.toLocaleString() || 0}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {result.risk.top_factors?.map((f, i) => (
                    <div key={i} style={{ background: 'var(--bg-dark)', borderRadius: 6, padding: '4px 10px', fontSize: 11, color: 'var(--text-muted)' }}>
                      {typeof f === 'object' ? `${f.feature}: ${f.shap_value?.toFixed(3)}` : f}
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-subtle)' }}>
                  Model: XGBoost + SHAP explainability | Training: synthetic MPR scenarios | Features: 26 indicators from compliance engine
                </div>
              </div>
            )}

            {/* Event summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
              {[
                { label: 'Critical Events', value: result.compliance?.critical_count, color: '#ef4444' },
                { label: 'High Events', value: result.compliance?.high_count, color: '#f59e0b' },
                { label: 'Total Events', value: result.compliance?.total_events, color: '#3b82f6' },
                { label: 'LD Today (₹)', value: (result.compliance?.total_ld_accrued_inr || 0).toLocaleString(), color: '#ef4444' },
              ].map(s => (
                <div key={s.label} style={{ background: 'var(--bg-card)', borderRadius: 8, padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value ?? 0}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{s.label}</div>
                </div>
              ))}
            </div>

            {/* Compliance events */}
            <div className="card">
              <h3 style={{ fontSize: 15, marginBottom: 14 }}>Compliance Events (All 15 Checks)</h3>
              <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--text-subtle)' }}>
                Each check is deterministic — same contract + same data = same result. No LLM in the detection logic.
              </div>
              {result.compliance?.events?.length > 0 ? (
                result.compliance.events.map((e, i) => <ComplianceEventCard key={i} event={e} index={i} />)
              ) : (
                <div style={{ textAlign: 'center', color: '#10b981', padding: '20px', fontSize: 14 }}>
                  ✅ No violations detected. All 15 checks passed.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { BarChart, Bar, Cell } from 'recharts';
import { Upload, FileText, Download, ChevronDown, ChevronUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { useApp } from '../context/AppContext';

// ── Helpers ─────────────────────────────────────────────────────────────
function getRiskBadge(label) {
  if (!label) return <span className="badge badge-gray">Unknown</span>;
  const l = label.toUpperCase();
  if (l === 'CRITICAL') return <span className="badge badge-danger">Critical</span>;
  if (l === 'HIGH' || l === 'AT_RISK') return <span className="badge badge-warning">High Risk</span>;
  if (l === 'MEDIUM') return <span className="badge badge-warning">Medium</span>;
  return <span className="badge badge-success">Low</span>;
}

function getSeverityClass(s) {
  const m = { CRITICAL: 'critical', HIGH: 'high', MEDIUM: 'medium', LOW: 'low', INFO: 'info' };
  return m[s?.toUpperCase()] || 'info';
}

// ── S-Curve Chart ─────────────────────────────────────────────────────────
function SCurveChart({ history, dayNumber, actualPct, scpDays = 730 }) {
  const points = [];
  for (let d = 0; d <= scpDays + 30; d += 30) points.push(d);
  if (!points.includes(dayNumber)) points.push(dayNumber);
  if (history) {
    history.forEach(h => {
      if (!points.includes(h.day_number)) points.push(h.day_number);
    });
  }
  points.sort((a, b) => a - b);

  const data = points.map(d => {
    let act = null;
    if (d === dayNumber) act = parseFloat(actualPct);
    else if (history) {
      const h = history.find(h => h.day_number === d);
      if (h) act = parseFloat(h.actual_pct);
    }
    return {
      day: d,
      planned: parseFloat(Math.min(100, (d / scpDays) * 100).toFixed(1)),
      actual: act,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="day" stroke="var(--text-muted)" label={{ value: 'Days from Appointed Date', position: 'insideBottom', offset: -4, fill: 'var(--text-muted)', fontSize: 11 }} />
        <YAxis stroke="var(--text-muted)" unit="%" domain={[0, 100]} />
        <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0.5rem' }}
          formatter={(v, n) => [v != null ? `${v}%` : '—', n === 'planned' ? 'Planned' : 'Actual']} />
        <ReferenceLine x={dayNumber} stroke="var(--text-muted)" strokeDasharray="4 4" label={{ value: 'Today', fill: 'var(--text-muted)', fontSize: 11 }} />
        <ReferenceLine x={scpDays} stroke="var(--danger)" strokeDasharray="4 4" label={{ value: 'SCD', fill: 'var(--danger)', fontSize: 11 }} />
        <Line type="monotone" dataKey="planned" stroke="var(--info)" strokeWidth={2} strokeDasharray="6 3" dot={false} name="planned" />
        <Line type="monotone" dataKey="actual" stroke="var(--warning)" strokeWidth={3} dot={{ r: 8, fill: 'var(--warning)' }} name="actual" connectNulls={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── SHAP Bar Chart ───────────────────────────────────────────────────────
function ShapChart({ factors }) {
  if (!factors || factors.length === 0)
    return <p className="text-muted text-sm">No risk factor data available.</p>;

  const valCol = ['shap_value', 'importance', 'contribution'].find(c => c in factors[0]);
  if (!valCol) return <p className="text-muted text-sm">Unrecognised SHAP format.</p>;

  const data = [...factors].reverse().map(f => ({
    feature: f.feature,
    value: Math.abs(parseFloat(f[valCol]) || 0),
    direction: f.direction,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 120, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis type="number" stroke="var(--text-muted)" label={{ value: 'Risk Impact', position: 'insideBottom', offset: -4, fill: 'var(--text-muted)', fontSize: 11 }} />
        <YAxis type="category" dataKey="feature" stroke="var(--text-muted)" width={115} tick={{ fontSize: 11 }} />
        <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0.5rem' }} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.direction === 'increases_risk' ? 'var(--danger)' : 'var(--primary)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Compliance Events ─────────────────────────────────────────────────────
function ComplianceEvents({ events }) {
  if (!events || events.length === 0)
    return <div className="alert alert-success"><CheckCircle size={16} /> No compliance events — project is on track.</div>;
  return (
    <div>
      {events.map((ev, i) => (
        <div key={i} className={`event-card ${getSeverityClass(ev.severity)}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.3rem' }}>
            <span className="event-title">{ev.title}</span>
            <span className={`badge badge-${getSeverityClass(ev.severity) === 'critical' ? 'danger' : getSeverityClass(ev.severity) === 'high' ? 'warning' : 'info'}`}>{ev.severity}</span>
          </div>
          <p className="event-desc">{ev.description}</p>
          {ev.action && <p className="event-action">➡ Action: {ev.action.replace(/_/g, ' ')}</p>}
          {ev.ld_amount_inr > 0 && <p className="event-action text-warning">LD: ₹{ev.ld_amount_inr?.toLocaleString('en-IN')}</p>}
        </div>
      ))}
    </div>
  );
}

// ── Role panels ──────────────────────────────────────────────────────────
function AuditorPanel({ contractId }) {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [data, setData] = useState(null);

  useEffect(() => {
    axios.get('/api/projects').then(res => {
      const ids = (res.data.projects || []).map(p => p.id);
      setReports(ids);
    });
  }, []);

  const load = async (id) => {
    setSelected(id);
    try {
      const res = await axios.get(`/api/projects/${id}/mpr-history`);
      setData(res.data.history);
    } catch { setData(null); }
  };

  return (
    <div>
      <h3 className="section-title">Audit Trail</h3>
      <div className="form-group" style={{ maxWidth: 320 }}>
        <label className="form-label">Select Project</label>
        <select className="form-control" onChange={e => load(e.target.value)}>
          <option value="">— choose —</option>
          {reports.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>
      {data && (
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Day</th>
                <th>Progress</th>
                <th>Risk Score</th>
                <th>Risk Label</th>
                <th>Critical Events</th>
                <th>LD Accrued (₹)</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r, i) => (
                <tr key={i}>
                  <td>{r.reporting_period}</td>
                  <td>{r.day_number}</td>
                  <td>{r.actual_pct}%</td>
                  <td>{r.risk_score?.toFixed(4)}</td>
                  <td>{getRiskBadge(r.risk_label)}</td>
                  <td>{r.critical_events}</td>
                  <td>{r.ld_accrued_inr?.toLocaleString('en-IN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SiteEngineerPanel({ events }) {
  const fieldEvents = (events || []).filter(e => ['HIGH', 'MEDIUM'].includes(e.severity?.toUpperCase()));
  if (fieldEvents.length === 0)
    return <div className="alert alert-success"><CheckCircle size={16} /> No field actions required — project on track.</div>;
  return (
    <div>
      <h3 className="section-title">Field Action Items</h3>
      {fieldEvents.map((ev, i) => (
        <div key={i} className={`event-card ${getSeverityClass(ev.severity)}`}>
          <div className="event-title">[{ev.severity}] {ev.title}</div>
          <p className="event-desc">{ev.description}</p>
          <p className="event-action">➡ {ev.action?.replace(/_/g, ' ')}</p>
        </div>
      ))}
    </div>
  );
}

function ContractorRepPanel({ compliance, parsedMpr, contractId }) {
  const [fmForm, setFmForm] = useState({ event_id: '', event_date: '', category: 'FORCE_MAJEURE_WEATHER', event_description: '', impact_assessment: '', estimated_duration: '', mitigation_strategy: '', notice_submitted_date: '' });
  const [fmResult, setFmResult] = useState(null);
  const [fmLoading, setFmLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const submitFm = async (e) => {
    e.preventDefault();
    if (!contractId) return;
    setFmLoading(true); setFmResult(null);
    try {
      const fd = new FormData();
      fd.append('project_id', contractId);
      fd.append('contract_id', contractId);
      fd.append('fm_claim', JSON.stringify(fmForm));
      const res = await axios.post('/api/process-fm-eot', fd);
      setFmResult(res.data.decision);
    } catch (err) {
      setFmResult({ decision: 'ERROR', rejection_reason: err.response?.data?.detail || err.message });
    } finally { setFmLoading(false); }
  };

  return (
    <div>
      <h3 className="section-title">Contractor View</h3>
      {compliance && (
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: '1.5rem' }}>
          <div className="card glass-panel">
            <div className="stat-label">Reporting Period</div>
            <div className="stat-value" style={{ fontSize: '1.25rem' }}>{parsedMpr?.reporting_period || '—'}</div>
          </div>
          <div className="card glass-panel">
            <div className="stat-label">Total Events</div>
            <div className="stat-value">{compliance.total_events || 0}</div>
          </div>
          <div className="card glass-panel" style={{ borderLeft: '4px solid var(--warning)' }}>
            <div className="stat-label">LD Accrued</div>
            <div className="stat-value" style={{ fontSize: '1.25rem' }}>₹{((compliance.total_ld_accrued_inr || 0) / 1e5).toFixed(1)}L</div>
          </div>
        </div>
      )}

      <div className="accordion">
        <div className="accordion-header" onClick={() => setShowForm(!showForm)}>
          <span>Submit Force Majeure Claim</span>
          {showForm ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        {showForm && (
          <div className="accordion-body">
            {fmResult && (
              <div className={`alert ${fmResult.decision === 'APPROVED' ? 'alert-success' : fmResult.decision === 'REJECTED' ? 'alert-danger' : 'alert-warning'}`}>
                {fmResult.decision === 'APPROVED' && `FM Claim APPROVED — ${fmResult.eot_days_approved} days EoT granted.`}
                {fmResult.decision === 'REJECTED' && `FM Claim REJECTED — ${fmResult.rejection_reason}`}
                {fmResult.decision === 'PARTIALLY_APPROVED' && `Partially Approved — ${fmResult.eot_days_approved} days EoT.`}
                {fmResult.decision === 'ERROR' && `Error: ${fmResult.rejection_reason}`}
              </div>
            )}
            <form onSubmit={submitFm}>
              <div className="form-grid-2">
                <div className="form-group">
                  <label className="form-label">Event ID</label>
                  <input className="form-control" placeholder="FM-001" value={fmForm.event_id} onChange={e => setFmForm({ ...fmForm, event_id: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select className="form-control" value={fmForm.category} onChange={e => setFmForm({ ...fmForm, category: e.target.value })}>
                    <option>FORCE_MAJEURE_WEATHER</option>
                    <option>FORCE_MAJEURE_POLITICAL</option>
                    <option>INDIRECT_POLITICAL</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Date of FM Event</label>
                  <input className="form-control" type="date" value={fmForm.event_date} onChange={e => setFmForm({ ...fmForm, event_date: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Notice Submitted Date</label>
                  <input className="form-control" type="date" value={fmForm.notice_submitted_date} onChange={e => setFmForm({ ...fmForm, notice_submitted_date: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Estimated Duration (days)</label>
                  <input className="form-control" type="number" value={fmForm.estimated_duration} onChange={e => setFmForm({ ...fmForm, estimated_duration: e.target.value })} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Event Description</label>
                <textarea className="form-control" rows={3} value={fmForm.event_description} onChange={e => setFmForm({ ...fmForm, event_description: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Impact Assessment</label>
                <textarea className="form-control" rows={2} value={fmForm.impact_assessment} onChange={e => setFmForm({ ...fmForm, impact_assessment: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Mitigation Strategy</label>
                <textarea className="form-control" rows={2} value={fmForm.mitigation_strategy} onChange={e => setFmForm({ ...fmForm, mitigation_strategy: e.target.value })} />
              </div>
              <button className="btn" type="submit" disabled={fmLoading || !contractId}>
                {fmLoading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Submitting...</> : 'Submit FM Claim'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main AnalysisPage ────────────────────────────────────────────────────
export default function AnalysisPage() {
  const { role, contractId } = useApp();
  const [file, setFile] = useState(null);
  const [prevPct, setPrevPct] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [showEvents, setShowEvents] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [ruleStore, setRuleStore] = useState(null);
  const [history, setHistory] = useState([]);

  // Load rule store and history when contractId changes
  useEffect(() => {
    if (!contractId) return;
    axios.get(`/api/projects/${contractId}/rule-store`)
      .then(r => setRuleStore(r.data))
      .catch(() => setRuleStore(null));

    axios.get(`/api/projects/${contractId}/mpr-history`)
      .then(r => setHistory(r.data.history || []))
      .catch(() => setHistory([]));
  }, [contractId, result]);

  const runAnalysis = async (e) => {
    e.preventDefault();
    if (!file || !contractId) return;
    setLoading(true); setResult(null); setError(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('contract_id', contractId);
    fd.append('prev_actual_pct', prevPct);
    fd.append('audience', role);
    try {
      const res = await axios.post('/api/upload-mpr', fd, { timeout: 180000 });
      setResult(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'object' ? JSON.stringify(detail, null, 2) : (detail || err.message));
    } finally { setLoading(false); }
  };

  const parsed = result?.parsed_mpr || {};
  const compliance = result?.compliance || {};
  const risk = result?.risk || {};
  const events = result?.compliance_events_full || [];
  const scpDays = ruleStore?.scp_days || 730;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">MPR Analysis</h1>
          <p className="page-subtitle">Upload a Monthly Progress Report to run compliance + risk analysis</p>
        </div>
        {role && <span className={`role-badge ${role.toLowerCase().replace(' ', '-')}`}>{role}</span>}
      </div>

      {/* ── Rule Store Summary ── */}
      {ruleStore && (
        <div className="accordion mb-2">
          <div className="accordion-header" onClick={() => setShowEvents(prev => !prev)}>
            <span>Contract Rule Store — {ruleStore.project_name || contractId}</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{ruleStore.milestones?.length || 0} milestones · SCP {scpDays} days</span>
          </div>
        </div>
      )}

      {/* ── Upload Form ── */}
      <div className="card mb-3">
        <form onSubmit={runAnalysis}>
          <div className="form-group">
            <label className="form-label">Monthly Progress Report (.md or .docx)</label>
            <div className={`upload-zone ${file ? 'dragover' : ''}`}
              onClick={() => document.getElementById('mpr-file').click()}>
              <div className="upload-zone-icon"><FileText size={32} /></div>
              <p>Click to select MPR file</p>
              {file ? <p className="file-selected">{file.name}</p> : <p style={{ fontSize: '0.8rem' }}>.md or .docx</p>}
            </div>
            <input id="mpr-file" type="file" accept=".md,.docx" style={{ display: 'none' }}
              onChange={e => setFile(e.target.files[0])} />
          </div>
          <div className="form-group" style={{ maxWidth: 280 }}>
            <label className="form-label">Previous Month Actual Progress (%)</label>
            <input className="form-control" type="number" min={0} max={100} step={0.1}
              value={prevPct} onChange={e => setPrevPct(e.target.value)} />
          </div>
          <button className="btn" type="submit" disabled={loading || !file || !contractId}>
            {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Analysing...</> : 'Run Full Analysis'}
          </button>
          {!contractId && <p className="text-muted text-sm mt-1" style={{ marginLeft: '0.5rem', display: 'inline' }}>Set Contract ID in sidebar first</p>}
        </form>
      </div>

      {error && <div className="alert alert-danger" style={{ whiteSpace: 'pre-wrap' }}><AlertTriangle size={16} /> {error}</div>}

      {/* ── Results ── */}
      {result && (
        <>
          {/* Summary cards */}
          <p className="text-muted text-sm mb-2">{parsed.project_name} · Day {parsed.day_number} · {parsed.contractor_name}</p>
          <div className="stats-grid mb-3">
            <div className="card glass-panel">
              <div className="stat-label">Risk Score</div>
              <div className="stat-value">{risk.score?.toFixed(4)}</div>
              {getRiskBadge(risk.label)}
            </div>
            <div className="card glass-panel">
              <div className="stat-label">Compliance Events</div>
              <div className="stat-value">{compliance.total_events}</div>
              <span className="badge badge-danger">{compliance.critical_count} Critical</span>
            </div>
            <div className="card glass-panel" style={{ borderLeft: '4px solid var(--warning)' }}>
              <div className="stat-label">LD Accrued</div>
              <div className="stat-value" style={{ fontSize: '1.5rem' }}>
                ₹{compliance.total_ld_accrued_inr >= 1e5
                  ? `${(compliance.total_ld_accrued_inr / 1e5).toFixed(1)}L`
                  : compliance.total_ld_accrued_inr?.toLocaleString('en-IN')}
              </div>
            </div>
            <div className="card glass-panel">
              <div className="stat-label">Time to Default</div>
              <div className="stat-value">{risk.ttd_days ? `${risk.ttd_days}d` : '—'}</div>
            </div>
          </div>

          {/* Downloads */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            {result.reports?.compliance_md && (
              <a href={`/api/reports/${result.reports.compliance_md.split('/').pop()}`}
                className="btn btn-outline btn-sm" target="_blank" rel="noreferrer">
                <Download size={14} /> Markdown Report
              </a>
            )}
            {result.reports?.compliance_pdf && (
              <a href={`/api/reports/${result.reports.compliance_pdf.split('/').pop()}`}
                className="btn btn-outline btn-sm" target="_blank" rel="noreferrer">
                <Download size={14} /> PDF Report
              </a>
            )}
            {result.reports?.risk_summary && (
              <a href={`/api/reports/${result.reports.risk_summary.split('/').pop()}`}
                className="btn btn-outline btn-sm" target="_blank" rel="noreferrer">
                <Download size={14} /> Risk JSON
              </a>
            )}
          </div>

          {/* S-Curve + SHAP */}
          <div className="two-col mb-3">
            <div className="card">
              <h3 className="section-title">Project S-Curve</h3>
              <SCurveChart history={history} dayNumber={parsed.day_number} actualPct={parsed.actual_physical_pct} scpDays={scpDays} />
              <p className="text-muted text-xs mt-1" style={{ textAlign: 'center' }}>
                Planned: {Math.min(100, ((parsed.day_number / scpDays) * 100)).toFixed(1)}% &nbsp;|&nbsp;
                Actual: {parsed.actual_physical_pct?.toFixed(1)}% &nbsp;|&nbsp;
                <span className={parsed.actual_physical_pct >= (parsed.day_number / scpDays * 100) ? 'text-success' : 'text-danger'}>
                  {(parsed.actual_physical_pct - (parsed.day_number / scpDays * 100)).toFixed(1)}% vs plan
                </span>
              </p>
            </div>
            <div className="card">
              <h3 className="section-title">Top Risk Drivers (SHAP)</h3>
              <ShapChart factors={risk.top_factors} />
            </div>
          </div>

          {/* Compliance Events */}
          <div className="accordion mb-3">
            <div className="accordion-header" onClick={() => setShowEvents(v => !v)}>
              <span>Compliance Events ({events.length})</span>
              {showEvents ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </div>
            {showEvents && (
              <div className="accordion-body">
                <ComplianceEvents events={events} />
              </div>
            )}
          </div>

          {/* Compliance MD Preview */}
          {result.compliance_md_preview && (
            <div className="accordion mb-3">
              <div className="accordion-header" onClick={() => setShowPreview(v => !v)}>
                <span>Compliance Report Preview</span>
                {showPreview ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </div>
              {showPreview && (
                <div className="accordion-body">
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {result.compliance_md_preview}
                  </pre>
                </div>
              )}
            </div>
          )}

          <div className="divider" />

          {/* Role-specific panels */}
          {role === 'Auditor' && <AuditorPanel contractId={contractId} />}
          {role === 'Site Engineer' && <SiteEngineerPanel events={events} />}
          {role === 'Contractor Rep' && <ContractorRepPanel compliance={compliance} parsedMpr={parsed} contractId={contractId} />}
        </>
      )}

      {/* Role panels even before analysis */}
      {!result && role === 'Auditor' && <AuditorPanel contractId={contractId} />}
      {!result && role === 'Contractor Rep' && <ContractorRepPanel compliance={null} parsedMpr={null} contractId={contractId} />}
    </div>
  );
}

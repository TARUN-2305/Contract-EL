import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useApp } from '../context/AppContext';
import { Activity } from 'lucide-react';

function getRiskBadge(label) {
  if (!label) return <span className="badge badge-gray">—</span>;
  const l = label.toUpperCase();
  if (l === 'CRITICAL') return <span className="badge badge-danger">Critical</span>;
  if (l === 'HIGH' || l === 'AT_RISK') return <span className="badge badge-warning">High Risk</span>;
  return <span className="badge badge-success">Low</span>;
}

export default function MprHistoryPage() {
  const { contractId } = useApp();
  const [localId, setLocalId] = useState(contractId || '');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState([]);

  useEffect(() => {
    axios.get('/api/projects').then(r => setProjects(r.data.projects || []));
  }, []);

  useEffect(() => { if (contractId) setLocalId(contractId); }, [contractId]);

  const load = async (id) => {
    if (!id) return;
    setLoading(true);
    try {
      const r = await axios.get(`/api/projects/${id}/mpr-history`);
      setHistory(r.data.history || []);
    } catch { setHistory([]); }
    setLoading(false);
  };

  const chartData = history.map(h => ({
    period: h.reporting_period,
    actual: h.actual_pct,
    planned: h.planned_pct,
    risk: parseFloat((h.risk_score * 100).toFixed(1)),
    ld: parseFloat((h.ld_accrued_inr / 1e5).toFixed(2)),
  }));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">MPR History</h1>
          <p className="page-subtitle">Time-series view of monthly progress reports for a project</p>
        </div>
      </div>

      {/* Project selector */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', alignItems: 'flex-end' }}>
        <div className="form-group" style={{ margin: 0, flex: 1, maxWidth: 360 }}>
          <label className="form-label">Select Project</label>
          <select className="form-control" value={localId} onChange={e => setLocalId(e.target.value)}>
            <option value="">— choose a project —</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
          </select>
        </div>
        <button className="btn" onClick={() => load(localId)} disabled={!localId || loading}>
          {loading ? <span className="spinner" style={{ width: 16, height: 16 }} /> : <Activity size={16} />}
          Load History
        </button>
      </div>

      {history.length === 0 && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <Activity size={48} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
          <p className="text-muted">Select a project and load its MPR history.</p>
        </div>
      )}

      {history.length > 0 && (
        <>
          {/* Charts */}
          <div className="two-col mb-3">
            <div className="card">
              <h3 className="section-title">Progress Trend</h3>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="period" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                  <YAxis stroke="var(--text-muted)" unit="%" />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0.5rem' }} />
                  <Legend />
                  <Line type="monotone" dataKey="planned" stroke="var(--info)" strokeDasharray="6 3" strokeWidth={2} name="Planned %" dot={false} />
                  <Line type="monotone" dataKey="actual" stroke="var(--primary)" strokeWidth={2} name="Actual %" dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <h3 className="section-title">Risk Score over Time (%)</h3>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="period" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                  <YAxis stroke="var(--text-muted)" domain={[0, 100]} unit="%" />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0.5rem' }} />
                  <Line type="monotone" dataKey="risk" stroke="var(--danger)" strokeWidth={2} dot={{ r: 4 }} name="Risk %" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* History table */}
          <div className="card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Day</th>
                  <th>Actual %</th>
                  <th>Planned %</th>
                  <th>Variance</th>
                  <th>Risk Score</th>
                  <th>Risk Label</th>
                  <th>Critical Events</th>
                  <th>LD (L)</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const variance = ((h.actual_pct || 0) - (h.planned_pct || 0)).toFixed(1);
                  return (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{h.reporting_period}</td>
                      <td>{h.day_number}</td>
                      <td>{h.actual_pct?.toFixed(1)}%</td>
                      <td>{h.planned_pct?.toFixed(1)}%</td>
                      <td className={variance >= 0 ? 'text-success' : 'text-danger'}>
                        {variance >= 0 ? '+' : ''}{variance}%
                      </td>
                      <td>{h.risk_score?.toFixed(4)}</td>
                      <td>{getRiskBadge(h.risk_label)}</td>
                      <td>{h.critical_events ?? '—'}</td>
                      <td className={h.ld_accrued_inr > 0 ? 'text-warning' : ''}>
                        {h.ld_accrued_inr != null ? `₹${(h.ld_accrued_inr / 1e5).toFixed(1)}L` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { TrendingUp, AlertTriangle, IndianRupee, Activity, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';

function getRiskBadge(label) {
  if (!label) return <span className="badge badge-gray">—</span>;
  const l = label.toUpperCase();
  if (l === 'CRITICAL') return <span className="badge badge-danger">Critical</span>;
  if (l === 'HIGH' || l === 'AT_RISK') return <span className="badge badge-warning">High Risk</span>;
  if (l === 'MEDIUM') return <span className="badge badge-warning">Medium</span>;
  return <span className="badge badge-success">Low</span>;
}

export default function Dashboard() {
  const { setContractId } = useApp();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trendData, setTrendData] = useState([]);

  useEffect(() => {
    axios.get('/api/projects')
      .then(async res => {
        const projs = res.data.projects || [];
        setProjects(projs);

        // Load history of the first project for the risk trend chart
        if (projs.length > 0) {
          try {
            const hist = await axios.get(`/api/projects/${projs[0].id}/mpr-history`);
            const h = hist.data.history || [];
            setTrendData(h.map(r => ({
              period: r.reporting_period,
              risk: parseFloat((r.risk_score * 100).toFixed(1)),
              actual: r.actual_pct,
            })));
          } catch { /* no history yet */ }
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="pulse" style={{ padding: '2rem' }}>Loading Dashboard...</div>;

  const atRisk = projects.filter(p => ['CRITICAL', 'HIGH', 'AT_RISK'].includes(p.last_risk_label?.toUpperCase())).length;
  const totalLd = projects.reduce((acc, p) => acc + (p.last_ld_accrued_inr || 0), 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Executive Overview</h1>
          <p className="page-subtitle">Real-time contract risk and compliance tracking</p>
        </div>
        <Link to="/analysis" className="btn">
          <Activity size={18} /> Run Analysis
        </Link>
      </div>

      {/* Stat cards */}
      <div className="stats-grid">
        <div className="card glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="stat-label">Total Projects</div>
            <TrendingUp size={20} color="var(--primary)" />
          </div>
          <div className="stat-value">{projects.length}</div>
          <p className="text-muted text-sm">Active on platform</p>
        </div>

        <div className="card glass-panel" style={{ borderLeft: '4px solid var(--danger)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="stat-label">Projects at Risk</div>
            <AlertTriangle size={20} color="var(--danger)" />
          </div>
          <div className="stat-value">{atRisk}</div>
          <p className="text-muted text-sm">Require immediate attention</p>
        </div>

        <div className="card glass-panel" style={{ borderLeft: '4px solid var(--warning)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="stat-label">Total LD Accrued</div>
            <IndianRupee size={20} color="var(--warning)" />
          </div>
          <div className="stat-value">₹ {(totalLd / 100000).toFixed(2)}L</div>
          <p className="text-muted text-sm">Potential penalties across portfolio</p>
        </div>
      </div>

      <div className="two-col">
        {/* Risk Trend */}
        <div className="card">
          <h3 className="section-title">Risk Trend Analysis</h3>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="period" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                <YAxis stroke="var(--text-muted)" unit="%" domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0.5rem' }} />
                <Legend />
                <Line type="monotone" dataKey="risk" stroke="var(--danger)" strokeWidth={3} dot={{ r: 5 }} name="Risk Score %" />
                <Line type="monotone" dataKey="actual" stroke="var(--primary)" strokeWidth={2} dot={{ r: 4 }} name="Progress %" strokeDasharray="6 3" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <p className="text-muted text-sm">No MPR history yet. Upload MPRs to see risk trends.</p>
            </div>
          )}
        </div>

        {/* Project Status table */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0 }}>Project Status</h3>
            <Link to="/projects" style={{ fontSize: '0.8rem', color: 'var(--primary)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              View all <ArrowRight size={14} />
            </Link>
          </div>
          <table>
            <thead>
              <tr>
                <th>Project</th>
                <th>Risk</th>
                <th>Progress</th>
              </tr>
            </thead>
            <tbody>
              {projects.slice(0, 6).map(p => (
                <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => setContractId(p.id)}>
                  <td style={{ fontWeight: 500, fontSize: '0.875rem' }}>{p.name || p.id}</td>
                  <td>{getRiskBadge(p.last_risk_label)}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div className="progress-bar-wrap" style={{ flex: 1 }}>
                        <div className={`progress-bar-fill ${['CRITICAL','HIGH','AT_RISK'].includes(p.last_risk_label?.toUpperCase()) ? 'danger' : ''}`}
                          style={{ width: `${p.last_actual_pct || 0}%` }} />
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', minWidth: 36 }}>
                        {p.last_actual_pct?.toFixed(1) || '0.0'}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
              {projects.length === 0 && (
                <tr><td colSpan="3" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                  No projects found. <Link to="/upload-contract" style={{ color: 'var(--primary)' }}>Upload a contract</Link> to get started.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

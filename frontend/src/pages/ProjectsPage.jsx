import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FolderKanban, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

function getRiskBadge(label) {
  if (!label) return <span className="badge badge-gray">—</span>;
  const l = label.toUpperCase();
  if (l === 'CRITICAL') return <span className="badge badge-danger">Critical</span>;
  if (l === 'HIGH' || l === 'AT_RISK') return <span className="badge badge-warning">High Risk</span>;
  if (l === 'MEDIUM') return <span className="badge badge-warning">Medium</span>;
  return <span className="badge badge-success">Low</span>;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const { setContractId } = useApp();
  const navigate = useNavigate();

  useEffect(() => {
    axios.get('/api/projects')
      .then(r => setProjects(r.data.projects || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const openHistory = (id) => {
    setContractId(id);
    navigate('/history');
  };

  if (loading) return <div className="pulse" style={{ padding: '2rem' }}>Loading projects...</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-subtitle">{projects.length} active project(s) on the platform</p>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <FolderKanban size={48} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
          <p className="text-muted">No projects yet. Upload a contract to get started.</p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Project</th>
                <th>Contractor</th>
                <th>Contract Value</th>
                <th>Progress</th>
                <th>Risk</th>
                <th>LD Accrued</th>
                <th>Last Period</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {projects.map(p => (
                <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => openHistory(p.id)}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{p.name || p.id}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{p.id} · {p.contract_type}</div>
                  </td>
                  <td>{p.contractor_name || '—'}</td>
                  <td>₹{p.contract_value_inr ? `${(p.contract_value_inr / 1e7).toFixed(1)} Cr` : '—'}</td>
                  <td>
                    {p.last_actual_pct != null ? (
                      <>
                        <div style={{ marginBottom: 4 }}>{p.last_actual_pct?.toFixed(1)}%</div>
                        <div className="progress-bar-wrap" style={{ width: 80 }}>
                          <div className="progress-bar-fill" style={{ width: `${p.last_actual_pct}%` }} />
                        </div>
                      </>
                    ) : '—'}
                  </td>
                  <td>{getRiskBadge(p.last_risk_label)}</td>
                  <td className={p.last_ld_accrued_inr > 0 ? 'text-warning' : ''}>
                    {p.last_ld_accrued_inr != null ? `₹${(p.last_ld_accrued_inr / 1e5).toFixed(1)}L` : '—'}
                  </td>
                  <td>{p.last_reporting_period || '—'}</td>
                  <td><ChevronRight size={18} color="var(--text-muted)" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

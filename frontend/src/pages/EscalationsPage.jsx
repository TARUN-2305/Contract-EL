import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertOctagon, ArrowRight, Clock, ShieldAlert } from 'lucide-react';

function getTierBadge(tier) {
  if (tier === 'Tier 3 (Termination/Legal)') return <span className="badge badge-danger">{tier}</span>;
  if (tier === 'Tier 2 (Notice of Default)') return <span className="badge badge-warning">{tier}</span>;
  return <span className="badge badge-info">{tier}</span>;
}

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('/api/escalations')
      .then(res => setEscalations(res.data.escalations || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="pulse" style={{ padding: '2rem' }}>Loading Escalations...</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title"><AlertOctagon size={24} style={{ display: 'inline', verticalAlign: 'text-bottom', color: 'var(--danger)' }} /> Escalations Tracker</h1>
          <p className="page-subtitle">Multi-tier escalation and legal notice tracking</p>
        </div>
      </div>

      <div className="card">
        {escalations.length === 0 ? (
          <div className="alert alert-success"><ShieldAlert size={16} /> No active escalations.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Project ID</th>
                <th>Current Tier</th>
                <th>Tier Entered</th>
                <th>Deadline</th>
                <th>Next Action</th>
                <th>Responsible</th>
              </tr>
            </thead>
            <tbody>
              {escalations.map(e => (
                <tr key={e.id} style={e.is_final ? { opacity: 0.6 } : {}}>
                  <td style={{ fontWeight: 500 }}>{e.event_id}</td>
                  <td>{e.project_id}</td>
                  <td>{getTierBadge(e.current_tier)}</td>
                  <td>{e.tier_entered_date}</td>
                  <td>{e.tier_deadline ? <span style={{ color: 'var(--danger)' }}><Clock size={12} style={{ display: 'inline', marginRight: 4 }}/>{e.tier_deadline}</span> : '—'}</td>
                  <td>{e.next_action} {e.is_final && '(Resolved/Terminated)'}</td>
                  <td>{e.responsible_party}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ShieldAlert, LayoutDashboard, FolderKanban, Activity, Upload, Search, History, FileText, Settings, Users, Server } from 'lucide-react';
import { useApp, ROLES } from '../context/AppContext';

const ROLE_COLORS = {
  'Contract Manager': '#3b82f6',
  'Project Manager': '#8b5cf6',
  'Site Engineer': '#10b981',
  'Auditor': '#6b7280',
  'Contractor Rep': '#f59e0b',
};

export default function Sidebar() {
  const { role, setRole, contractId, setContractId } = useApp();
  const location = useLocation();
  const isActive = (path) => path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
  const roleColor = ROLE_COLORS[role] || '#10b981';

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <ShieldAlert size={28} color="var(--primary)" />
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 800 }}>ContractGuard AI</h2>
          <div style={{ fontSize: 10, color: 'var(--text-subtle)', letterSpacing: 1 }}>PRODUCTION v2.0</div>
        </div>
      </div>

      <div className="sidebar-control">
        <span className="sidebar-label">Active Role</span>
        <select className="sidebar-select" value={role} onChange={e => setRole(e.target.value)}>
          {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: roleColor }} />
          <span style={{ fontSize: 11, color: roleColor, fontWeight: 600 }}>{role}</span>
        </div>
      </div>

      <div className="sidebar-control">
        <span className="sidebar-label">Contract / Project ID</span>
        <input className="sidebar-input" type="text" placeholder="e.g. EPC_NH44_KA03"
          value={contractId} onChange={e => setContractId(e.target.value.replace(/[/\\]/g, '_'))} />
      </div>

      <div className="sidebar-divider" />
      <span className="sidebar-section-label">Overview</span>
      <nav style={{ display: 'flex', flexDirection: 'column' }}>
        <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}><LayoutDashboard size={16} /> Dashboard</Link>
        <Link to="/projects" className={`nav-link ${isActive('/projects') ? 'active' : ''}`}><FolderKanban size={16} /> Projects</Link>
        <Link to="/history" className={`nav-link ${isActive('/history') ? 'active' : ''}`}><History size={16} /> MPR History</Link>
        <Link to="/personas" className={`nav-link ${isActive('/personas') ? 'active' : ''}`}><Users size={16} /> Persona Guide</Link>

        <div className="sidebar-divider" />
        <span className="sidebar-section-label">Workflows</span>

        <Link to="/upload-contract" className={`nav-link ${isActive('/upload-contract') ? 'active' : ''}`}><Upload size={16} /> Upload Contract</Link>
        <Link to="/analysis" className={`nav-link ${isActive('/analysis') ? 'active' : ''}`}><Search size={16} /> MPR Analysis</Link>

        <div className="sidebar-divider" />
        <span className="sidebar-section-label">Oversight</span>

        <Link to="/escalations" className={`nav-link ${isActive('/escalations') ? 'active' : ''}`}><ShieldAlert size={16} /> Escalations</Link>
        <Link to="/reports" className={`nav-link ${isActive('/reports') ? 'active' : ''}`}><FileText size={16} /> Reports</Link>
        <Link to="/admin" className={`nav-link ${isActive('/admin') ? 'active' : ''}`}><Settings size={16} /> Admin Overrides</Link>
        <Link to="/system" className={`nav-link ${isActive('/system') ? 'active' : ''}`}><Server size={16} /> System Status</Link>
      </nav>

      <div style={{ marginTop: 'auto', paddingTop: 16 }}>
        <div style={{ fontSize: 10, color: 'var(--text-subtle)', textAlign: 'center' }}>
          Stack: FastAPI · Redis · Qdrant · Celery<br />
          LLM: Groq → Ollama fallback
        </div>
      </div>
    </aside>
  );
}

import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ShieldAlert, LayoutDashboard, FolderKanban,
  Activity, Upload, Search, ChevronDown
} from 'lucide-react';
import { useApp, ROLES } from '../context/AppContext';

const ROLE_CLASS = {
  'Contract Manager': 'contract-manager',
  'Project Manager': 'project-manager',
  'Site Engineer': 'site-engineer',
  'Auditor': 'auditor',
  'Contractor Rep': 'contractor-rep',
};

export default function Sidebar() {
  const { role, setRole, contractId, setContractId } = useApp();
  const location = useLocation();

  const isActive = (path) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <ShieldAlert size={28} color="var(--primary)" />
        <h2>ContractGuard AI</h2>
      </div>

      {/* Role selector */}
      <div className="sidebar-control">
        <span className="sidebar-label">Active Role</span>
        <select
          className="sidebar-select"
          value={role}
          onChange={e => setRole(e.target.value)}
        >
          {ROLES.map(r => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <span className={`role-badge ${ROLE_CLASS[role] || ''}`}>{role}</span>
      </div>

      {/* Contract ID */}
      <div className="sidebar-control">
        <span className="sidebar-label">Contract ID</span>
        <input
          className="sidebar-input"
          type="text"
          placeholder="e.g. EPC_NH44_KA03"
          value={contractId}
          onChange={e => setContractId(e.target.value.replace(/[/\\]/g, '_'))}
        />
      </div>

      <div className="sidebar-divider" />

      {/* Navigation */}
      <span className="sidebar-section-label">Navigation</span>
      <nav style={{ display: 'flex', flexDirection: 'column' }}>
        <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}>
          <LayoutDashboard size={18} /> Dashboard
        </Link>
        <Link to="/projects" className={`nav-link ${isActive('/projects') ? 'active' : ''}`}>
          <FolderKanban size={18} /> Projects
        </Link>
        <Link to="/history" className={`nav-link ${isActive('/history') ? 'active' : ''}`}>
          <Activity size={18} /> MPR History
        </Link>

        <div className="sidebar-divider" />
        <span className="sidebar-section-label">Workflows</span>

        <Link to="/upload-contract" className={`nav-link ${isActive('/upload-contract') ? 'active' : ''}`}>
          <Upload size={18} /> Upload Contract
        </Link>
        <Link to="/analysis" className={`nav-link ${isActive('/analysis') ? 'active' : ''}`}>
          <Search size={18} /> MPR Analysis
        </Link>
      </nav>
    </aside>
  );
}

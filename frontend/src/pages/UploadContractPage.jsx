import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function UploadContractPage() {
  const { contractId, setContractId } = useApp();
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({ project_name: '', contract_value_inr: '', scp_days: '', location: '', contractor_name: '' });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !contractId) return;
    setLoading(true); setStatus(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('contract_id', contractId);
    fd.append('contract_type', 'EPC');
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    try {
      const res = await axios.post('/api/upload-contract', fd, { timeout: 300000 });
      setStatus({ type: 'success', msg: `Contract parsed! Keys: ${res.data.rule_store_keys?.join(', ')}` });
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.detail || err.message });
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Upload Contract</h1>
          <p className="page-subtitle">Parse an EPC/ITEM RATE contract to extract rule store</p>
        </div>
      </div>

      {status && (
        <div className={`alert ${status.type === 'success' ? 'alert-success' : 'alert-danger'}`}>
          {status.msg}
        </div>
      )}

      <div className="card" style={{ maxWidth: 720 }}>
        <form onSubmit={handleSubmit}>
          {/* File upload zone */}
          <div className="form-group">
            <label className="form-label">Contract File (PDF / DOCX)</label>
            <div
              className={`upload-zone ${file ? 'dragover' : ''}`}
              onClick={() => document.getElementById('contract-file-input').click()}
            >
              <div className="upload-zone-icon"><Upload size={36} /></div>
              <p>Click to select or drag & drop your contract file</p>
              {file ? (
                <p className="file-selected"><FileText size={14} style={{ display: 'inline', marginRight: 4 }} />{file.name}</p>
              ) : (
                <p style={{ fontSize: '0.8rem' }}>Supported: .pdf, .docx</p>
              )}
            </div>
            <input id="contract-file-input" type="file" accept=".pdf,.docx" style={{ display: 'none' }}
              onChange={e => setFile(e.target.files[0])} />
          </div>

          <div className="form-group">
            <label className="form-label">Contract ID</label>
            <input className="form-control" placeholder="e.g. EPC_NH44_KA03" value={contractId}
              onChange={e => setContractId(e.target.value.replace(/[/\\]/g, '_'))} required />
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Project Name</label>
              <input className="form-control" placeholder="NH44 Expansion KA-03"
                value={form.project_name} onChange={e => setForm({ ...form, project_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">Contractor Name</label>
              <input className="form-control" placeholder="XYZ Constructions Pvt Ltd"
                value={form.contractor_name} onChange={e => setForm({ ...form, contractor_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">Contract Value (INR)</label>
              <input className="form-control" type="number" placeholder="150000000"
                value={form.contract_value_inr} onChange={e => setForm({ ...form, contract_value_inr: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">SCP Days</label>
              <input className="form-control" type="number" placeholder="730"
                value={form.scp_days} onChange={e => setForm({ ...form, scp_days: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">Location</label>
              <input className="form-control" placeholder="Karnataka, India"
                value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
            </div>
          </div>

          <button className="btn" type="submit" disabled={loading || !file || !contractId}>
            {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Parsing...</> : <><Upload size={16} /> Parse Contract</>}
          </button>
        </form>
      </div>
    </div>
  );
}

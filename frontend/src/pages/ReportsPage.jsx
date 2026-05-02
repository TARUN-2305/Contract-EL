import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FileText, Download, FileJson, FileType2 } from 'lucide-react';

export default function ReportsPage() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('/api/reports/list')
      .then(res => setReports(res.data.reports || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="pulse" style={{ padding: '2rem' }}>Loading Reports...</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title"><FileText size={24} style={{ display: 'inline', verticalAlign: 'text-bottom' }} /> Document Center</h1>
          <p className="page-subtitle">Download AI-generated risk, compliance, and legal reports</p>
        </div>
      </div>

      <div className="card">
        {reports.length === 0 ? (
          <p className="text-muted text-sm" style={{ padding: '1rem' }}>No reports generated yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>File Name</th>
                <th>Category</th>
                <th>Size (KB)</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {r.filename.endsWith('.pdf') ? <FileType2 size={16} color="var(--danger)" /> : r.filename.endsWith('.json') ? <FileJson size={16} color="var(--warning)" /> : <FileText size={16} color="var(--primary)" />}
                    {r.filename}
                  </td>
                  <td><span className="badge badge-info">{r.type}</span></td>
                  <td>{(r.size / 1024).toFixed(1)}</td>
                  <td>
                    <a href={`/api/reports/${r.filename}`} className="btn btn-outline btn-sm" target="_blank" rel="noreferrer" download>
                      <Download size={14} /> Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

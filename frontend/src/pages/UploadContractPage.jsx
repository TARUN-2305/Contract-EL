import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, Cpu, CheckCircle, AlertTriangle, Info, Loader, ChevronDown, ChevronUp } from 'lucide-react';
import { useApp } from '../context/AppContext';

const PERSONA_INFO = {
  'Contract Manager': {
    role: 'Engineer-in-Charge (EiC) / Divisional Engineer',
    tasks: ['Upload the contract PDF/DOCX', 'Review LLM-extracted rules', 'Approve the rule store', 'Set project baseline'],
    format: 'PDF or DOCX of the signed EPC/Item Rate contract',
    evidence: 'Rule store JSON with exact clause references (Article 10.3, Clause 1, etc.)',
    color: '#3b82f6'
  }
};

function EvidenceBox({ title, children, severity = 'info' }) {
  const [open, setOpen] = useState(false);
  const colors = { info: '#3b82f6', success: '#10b981', warning: '#f59e0b', error: '#ef4444' };
  return (
    <div style={{ border: `1px solid ${colors[severity]}30`, borderRadius: 8, marginBottom: 12, overflow: 'hidden' }}>
      <div onClick={() => setOpen(o => !o)} style={{ padding: '10px 14px', cursor: 'pointer', background: `${colors[severity]}10`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: colors[severity], fontWeight: 600, fontSize: 13 }}>{title}</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </div>
      {open && <div style={{ padding: '12px 14px', fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.7 }}>{children}</div>}
    </div>
  );
}

export default function UploadContractPage() {
  const { contractId, setContractId, role } = useApp();
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({ project_name: '', contract_value_inr: '', scp_days: '730', location: '', contractor_name: '', contract_type: 'EPC' });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [llmLoading, setLlmLoading] = useState(false);
  const [extracted, setExtracted] = useState(null);
  const [ruleStore, setRuleStore] = useState(null);
  const [step, setStep] = useState('upload'); // upload | reviewing | done
  const fileRef = useRef();

  const handleLLMExtract = async () => {
    if (!file) return;
    setLlmLoading(true);
    setStatus({ type: 'info', msg: '🤖 LLM is reading your contract... (Groq→Ollama fallback chain active)' });
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post('/api/llm-extract-contract', fd, { timeout: 300000 });
      const ext = res.data.extracted;
      setExtracted(ext);
      // Pre-fill form
      if (ext.project_name) setForm(f => ({ ...f, project_name: ext.project_name }));
      if (ext.contract_value_inr) setForm(f => ({ ...f, contract_value_inr: String(ext.contract_value_inr) }));
      if (ext.scp_days) setForm(f => ({ ...f, scp_days: String(ext.scp_days) }));
      if (ext.location) setForm(f => ({ ...f, location: ext.location }));
      if (ext.contractor_name) setForm(f => ({ ...f, contractor_name: ext.contractor_name }));
      if (ext.contract_type) setForm(f => ({ ...f, contract_type: ext.contract_type }));
      setStatus({ type: 'success', msg: `✅ LLM extracted ${Object.keys(ext).filter(k => ext[k]).length} fields. Review and confirm below.` });
    } catch (err) {
      setStatus({ type: 'error', msg: `LLM extraction failed: ${err.response?.data?.detail || err.message}` });
    } finally {
      setLlmLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !contractId) return;
    setLoading(true); setStatus({ type: 'info', msg: '⚙️ Parsing contract... extracting milestones, LD rates, QA rules...' });
    const fd = new FormData();
    fd.append('file', file);
    fd.append('contract_id', contractId);
    fd.append('contract_type', form.contract_type);
    Object.entries(form).forEach(([k, v]) => { if (k !== 'contract_type') fd.append(k, v); });
    try {
      const res = await axios.post('/api/upload-contract', fd, { timeout: 600000 });
      setStatus({ type: 'success', msg: `✅ Contract parsed! Extracted: ${res.data.rule_store_keys?.join(', ')}` });
      // Load rule store for display
      const rs = await axios.get(`/api/projects/${contractId}/rule-store`);
      setRuleStore(rs.data);
      setStep('done');
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.detail || err.message });
    } finally { setLoading(false); }
  };

  const persona = PERSONA_INFO['Contract Manager'];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Upload Contract</h1>
          <p className="page-subtitle">Parse EPC/Item Rate contracts — extract milestones, LD rates, QA rules, FM clauses</p>
        </div>
      </div>

      {/* Persona Role Card */}
      <div className="card" style={{ borderLeft: `4px solid ${persona.color}`, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ background: `${persona.color}20`, color: persona.color, padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 700 }}>
                CONTRACT MANAGER
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{persona.role}</span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
              <strong>Your job:</strong> Upload the signed contract document. The system will extract all compliance rules automatically using the Hierarchical RAG pipeline (regex extraction → LLM fallback → vector store).
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ background: 'var(--bg-dark)', borderRadius: 8, padding: '10px 14px' }}>
                <div style={{ fontSize: 11, color: 'var(--text-subtle)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>What you do</div>
                {persona.tasks.map(t => <div key={t} style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>• {t}</div>)}
              </div>
              <div style={{ background: 'var(--bg-dark)', borderRadius: 8, padding: '10px 14px' }}>
                <div style={{ fontSize: 11, color: 'var(--text-subtle)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>Evidence produced</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  <div style={{ marginBottom: 4 }}>📄 rule_store_{'{contract_id}'}.json</div>
                  <div style={{ marginBottom: 4 }}>📊 extraction_audit_{'{contract_id}'}.json</div>
                  <div>⚠️ unresolved_fields_{'{contract_id}'}.json</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* How it works explanation */}
      <EvidenceBox title="📐 How the Extraction Pipeline Works (Technical Evidence)" severity="info">
        <p style={{ marginBottom: 8 }}><strong>Stage 1 — PDF Preprocessing:</strong> pdfplumber extracts text page by page. DOCX is converted to Markdown preserving table structure. Each chunk is tagged with clause ID and page number.</p>
        <p style={{ marginBottom: 8 }}><strong>Stage 2 — Semantic Chunking:</strong> Text is split at Article/Clause boundaries (regex pattern: <code>ARTICLE|Clause|SECTION + digit</code>). Each chunk respects article boundaries — no mid-article splits.</p>
        <p style={{ marginBottom: 8 }}><strong>Stage 3 — Embedding + Qdrant:</strong> sentence-transformers (all-MiniLM-L6-v2) embeds all chunks into 384-dim vectors stored in Qdrant. This enables semantic search: "what are the delay penalties?" finds Article 10.3.2 even without keyword match.</p>
        <p style={{ marginBottom: 8 }}><strong>Stage 4a — Regex Extraction:</strong> Deterministic patterns extract milestone days, LD rates, cap percentages. Regex is fast, predictable, and auditable.</p>
        <p><strong>Stage 4b — LLM Fallback (Groq → Ollama):</strong> For any field regex cannot find, the system sends the top-5 semantically relevant chunks to the LLM with a structured extraction prompt. Falls back from Groq → gemma3:1b → phi3:mini.</p>
      </EvidenceBox>

      {status && (
        <div className={`alert ${status.type === 'success' ? 'alert-success' : status.type === 'info' ? 'alert-info' : 'alert-danger'}`}>
          {status.msg}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: step === 'done' ? '1fr 1fr' : '1fr', gap: 20 }}>
        <div className="card">
          <form onSubmit={handleSubmit}>
            <h3 style={{ marginBottom: 16, fontSize: 16 }}>Step 1: Upload Contract Document</h3>

            {/* File upload */}
            <div className="form-group">
              <label className="form-label">Contract File (PDF / DOCX)</label>
              <div className={`upload-zone ${file ? 'dragover' : ''}`}
                onClick={() => fileRef.current.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); setFile(e.dataTransfer.files[0]); }}>
                <div className="upload-zone-icon"><Upload size={36} /></div>
                <p>Click to select or drag & drop your contract</p>
                {file ? (
                  <p className="file-selected"><FileText size={14} style={{ display: 'inline', marginRight: 4 }} />{file.name}</p>
                ) : (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>Supported: .pdf, .docx</p>
                )}
              </div>
              <input ref={fileRef} type="file" accept=".pdf,.docx" style={{ display: 'none' }} onChange={e => setFile(e.target.files[0])} />
            </div>

            {/* LLM auto-fill button */}
            {file && (
              <div style={{ marginBottom: 16 }}>
                <button type="button" onClick={handleLLMExtract} disabled={llmLoading}
                  style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  {llmLoading ? <Loader size={14} className="spin" /> : <Cpu size={14} />}
                  🤖 Auto-Fill with LLM (reads the contract for you)
                </button>
                <p style={{ fontSize: 11, color: 'var(--text-subtle)', marginTop: 6 }}>
                  Uses Groq → Ollama fallback. Review all extracted values before submitting.
                </p>
              </div>
            )}

            {/* Confidence notes from LLM */}
            {extracted?.confidence_notes && (
              <div style={{ background: '#f59e0b15', border: '1px solid #f59e0b30', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 12, color: '#f59e0b' }}>
                <strong>⚠️ LLM Notes:</strong> {extracted.confidence_notes}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Contract ID</label>
              <input className="form-control" placeholder="e.g. EPC_NH44_KA03" value={contractId}
                onChange={e => setContractId(e.target.value.replace(/[/\\]/g, '_'))} required />
              <small style={{ color: 'var(--text-subtle)', fontSize: 11 }}>Used as the unique key for this project across all modules</small>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Contract Type</label>
                <select className="form-control" value={form.contract_type} onChange={e => setForm({ ...form, contract_type: e.target.value })}>
                  <option value="EPC">EPC (NITI Aayog Model) — Milestone %, catch-up refund, 60-day cure</option>
                  <option value="ITEM_RATE">Item Rate (CPWD GCC 2023) — Monthly targets, 7-day SCN</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Project Name</label>
                <input className="form-control" placeholder="NH44 Expansion KA-03"
                  value={form.project_name} onChange={e => setForm({ ...form, project_name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Contract Value (₹)</label>
                <input className="form-control" type="number" placeholder="25000000"
                  value={form.contract_value_inr} onChange={e => setForm({ ...form, contract_value_inr: e.target.value })} />
                <small style={{ color: 'var(--text-subtle)', fontSize: 11 }}>Used for LD cap calculation (10% of this)</small>
              </div>
              <div className="form-group">
                <label className="form-label">SCP Days (Scheduled Construction Period)</label>
                <input className="form-control" type="number" placeholder="730"
                  value={form.scp_days} onChange={e => setForm({ ...form, scp_days: e.target.value })} />
                <small style={{ color: 'var(--text-subtle)', fontSize: 11 }}>Milestone M1=28%, M2=55%, M3=75%, M4=100% of this</small>
              </div>
              <div className="form-group">
                <label className="form-label">Location</label>
                <input className="form-control" placeholder="NH-44 Karnataka, India"
                  value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Contractor Name</label>
                <input className="form-control" placeholder="XYZ Constructions Pvt Ltd"
                  value={form.contractor_name} onChange={e => setForm({ ...form, contractor_name: e.target.value })} />
              </div>
            </div>

            <button className="btn" type="submit" disabled={loading || !file || !contractId}>
              {loading ? <><Loader size={14} className="spin" /> Parsing contract (regex + LLM + embeddings)...</> : '⚙️ Parse Contract & Build Rule Store'}
            </button>
          </form>
        </div>

        {/* Rule Store display */}
        {step === 'done' && ruleStore && (
          <div className="card">
            <h3 style={{ marginBottom: 16, fontSize: 16 }}>✅ Extracted Rule Store</h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              These rules are now the source of truth for all 15 compliance checks, risk prediction, and agent decisions.
            </p>

            {/* Milestones */}
            {ruleStore.milestones && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--primary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>Milestones</div>
                {ruleStore.milestones.map(m => (
                  <div key={m.id} style={{ background: 'var(--bg-dark)', borderRadius: 8, padding: '8px 12px', marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{m.name || m.id}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{m.source_clause}</span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                      Day {m.trigger_day} | {m.required_physical_progress_pct}% progress required | LD: {m.ld_rate_pct_per_day}%/day
                      {m.catch_up_refund_eligible && <span style={{ marginLeft: 8, color: '#10b981' }}>✓ Catch-up refund eligible</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* LD Summary */}
            {ruleStore.liquidated_damages && (
              <div style={{ background: '#ef444415', border: '1px solid #ef444430', borderRadius: 8, padding: '10px 14px', marginBottom: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#ef4444', marginBottom: 6 }}>Liquidated Damages</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Rate: {ruleStore.liquidated_damages.daily_rate_pct}%/day |
                  Cap: {ruleStore.liquidated_damages.max_cap_pct}% (₹{(ruleStore.liquidated_damages.max_cap_inr || 0).toLocaleString()}) |
                  <span style={{ color: '#f59e0b' }}> Clause: {ruleStore.liquidated_damages.source_clause}</span>
                </div>
              </div>
            )}

            {/* Performance Security */}
            {ruleStore.performance_security && (
              <div style={{ background: '#f59e0b15', border: '1px solid #f59e0b30', borderRadius: 8, padding: '10px 14px', marginBottom: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b', marginBottom: 6 }}>Performance Security</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {ruleStore.performance_security.pct_of_contract_value}% of contract value (₹{(ruleStore.performance_security.amount_inr || 0).toLocaleString()})
                  | Submit within {ruleStore.performance_security.submission_deadline_days} days of LoA
                  | Late fee: {ruleStore.performance_security.late_fee_pct_per_day}%/day
                </div>
              </div>
            )}

            <EvidenceBox title="Validation Rules Applied" severity="success">
              <p>• LD rate must be 0–1%/day (sanity check) ✓</p>
              <p>• Max cap must equal 10% (universal Indian standard) ✓</p>
              <p>• Performance Security must be 4–10% of contract value ✓</p>
              <p>• FM notice period must be 7 days (NITI Aayog Art. 19) ✓</p>
              <p style={{ marginTop: 8, color: '#10b981' }}>All fields marked ⚠️ UNRESOLVED require your manual review before the rule store is activated for compliance checks.</p>
            </EvidenceBox>
          </div>
        )}
      </div>
    </div>
  );
}

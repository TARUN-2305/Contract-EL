import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw, CheckCircle, XCircle, AlertCircle, Loader } from 'lucide-react';

function StatusBadge({ ok, label }) {
  if (ok === null) return <span style={{ color: '#6b7280', fontSize: 12 }}>Checking...</span>;
  return ok
    ? <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}><CheckCircle size={13} /> {label || 'Online'}</span>
    : <span style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}><XCircle size={13} /> Offline</span>;
}

export default function SystemStatusPage() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/healthz', { timeout: 10000 });
      setHealth(res.data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err) {
      setHealth({ error: err.message, services: {} });
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchStatus(); }, []);

  const services = health?.services || {};
  const llm = services.llm || {};

  const STACK_DOCS = [
    {
      name: 'PostgreSQL 15',
      role: 'Primary relational store',
      stores: ['Projects, Users, MPR records', 'Compliance events, Escalation events', 'Rule stores (fallback if Qdrant down)'],
      why: 'ACID guarantees needed for financial penalty ledger. Append-only writes preserve full audit history.',
      port: '5432',
    },
    {
      name: 'Redis 7',
      role: 'Message broker + result cache',
      stores: ['Celery job queue (broker)', 'Celery task results (backend)', 'Job status polling (key: job:{id}, TTL 1hr)'],
      why: 'Async job processing lets large contract parsing (30–60s) run without HTTP timeout. Non-blocking API.',
      port: '6379',
    },
    {
      name: 'Qdrant',
      role: 'Vector similarity search',
      stores: ['Contract clause embeddings (384-dim)', 'Indexed by contract_id for filtered search', 'Falls back to in-memory numpy cosine if unavailable'],
      why: 'Semantic search finds relevant clauses even when phrased differently. "delay penalty" finds "liquidated damages" without exact match.',
      port: '6333',
    },
    {
      name: 'Celery Worker',
      role: 'Background task processor',
      stores: ['parse_contract task: PDF→chunks→embed→extract→rule_store', 'process_mpr task: parse→compliance→risk→explain→save', 'run_daily_checks: escalation timer evaluation'],
      why: 'Contract parsing takes 30–120s (embedding + LLM calls). Running sync would timeout HTTP. One worker handles sequential queue.',
      port: 'N/A (connects to Redis)',
    },
    {
      name: 'Ollama (optional)',
      role: 'Local CPU LLM fallback',
      stores: ['gemma3:1b — primary local model (~4GB RAM)', 'phi3:mini — smaller fallback (~2GB RAM)', 'Timeout: 300s (CPU inference is slow)'],
      why: 'When Groq API keys are exhausted or rate-limited, Ollama provides local inference. No data leaves the server.',
      port: '11434',
    },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">System Status</h1>
          <p className="page-subtitle">Live health check of all production services + architecture documentation</p>
        </div>
        <button onClick={fetchStatus} disabled={loading} className="btn" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {loading ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />}
          Refresh
        </button>
      </div>

      {lastChecked && <div style={{ fontSize: 12, color: 'var(--text-subtle)', marginBottom: 16 }}>Last checked: {lastChecked}</div>}

      {/* Live service tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        {[
          { name: 'PostgreSQL', ok: services.postgresql ?? null, detail: 'Relational DB' },
          { name: 'Redis', ok: services.redis ?? null, detail: 'Job Queue / Cache' },
          { name: 'Qdrant', ok: services.qdrant ?? null, detail: 'Vector Search' },
          { name: 'API Server', ok: health && !health.error ? true : null, detail: 'FastAPI' },
        ].map(s => (
          <div key={s.name} style={{ background: 'var(--bg-card)', border: `1px solid ${s.ok ? '#10b98130' : s.ok === false ? '#ef444430' : 'var(--border)'}`, borderRadius: 10, padding: '16px' }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{s.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-subtle)', marginBottom: 8 }}>{s.detail}</div>
            <StatusBadge ok={s.ok} label="Online" />
          </div>
        ))}
      </div>

      {/* LLM fallback chain */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16, fontSize: 15 }}>🤖 LLM Fallback Chain</h3>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
          The system tries each LLM provider in order. If Groq is rate-limited or unavailable, it falls back to local Ollama.
          All models run with large timeouts (300s) to support CPU-based Ollama inference.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {[
            { name: 'Groq API', model: llm.groq_keys_loaded > 0 ? `${llm.groq_keys_loaded} key(s) loaded` : 'No keys', available: llm.groq_available, color: '#10b981' },
            { name: '→', model: '', available: null, color: 'var(--text-subtle)', arrow: true },
            { name: 'Ollama Primary', model: llm.ollama_primary || 'gemma3:1b', available: null, color: '#8b5cf6' },
            { name: '→', model: '', available: null, color: 'var(--text-subtle)', arrow: true },
            { name: 'Ollama Fallback', model: llm.ollama_fallback || 'phi3:mini', available: null, color: '#f59e0b' },
          ].map((item, i) => item.arrow ? (
            <div key={i} style={{ color: 'var(--text-subtle)', fontSize: 20 }}>→</div>
          ) : (
            <div key={i} style={{ background: 'var(--bg-dark)', border: `1px solid ${item.color}30`, borderRadius: 8, padding: '10px 14px', minWidth: 140 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: item.color }}>{item.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{item.model}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-subtle)' }}>
          Extraction model: {llm.extraction_model || 'llama-3.3-70b-versatile'} | Narration model: {llm.narration_model || 'llama-3.1-8b-instant'}
        </div>
      </div>

      {/* Stack docs */}
      <h3 style={{ marginBottom: 14, fontSize: 15 }}>Infrastructure Documentation</h3>
      {STACK_DOCS.map(s => (
        <div key={s.name} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <div>
              <span style={{ fontSize: 15, fontWeight: 700 }}>{s.name}</span>
              <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--primary)', background: 'var(--primary-glow)', padding: '2px 8px', borderRadius: 6 }}>{s.role}</span>
            </div>
            {s.port !== 'N/A (connects to Redis)' && (
              <span style={{ fontSize: 11, color: 'var(--text-subtle)', background: 'var(--bg-dark)', padding: '2px 8px', borderRadius: 6 }}>:{s.port}</span>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>What it stores / does</div>
              {s.stores.map((item, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'flex', gap: 6 }}>
                  <span style={{ color: 'var(--primary)' }}>•</span>{item}
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>Why this technology</div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>{s.why}</p>
            </div>
          </div>
        </div>
      ))}

      {/* Data flow diagram */}
      <div className="card" style={{ marginTop: 20 }}>
        <h3 style={{ marginBottom: 16, fontSize: 15 }}>Data Flow (Contract → Rule Store → Compliance → Risk → Explanation)</h3>
        <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)', lineHeight: 2, background: 'var(--bg-dark)', padding: '16px', borderRadius: 8 }}>
          <div style={{ color: '#3b82f6' }}>CONTRACT PDF (uploaded by Contract Manager)</div>
          <div>        ↓</div>
          <div style={{ color: '#8b5cf6' }}>PARSER AGENT → regex extraction → LLM fallback → Qdrant (384-dim vectors)</div>
          <div>        ↓ rule_store_{'{contract_id}'}.json</div>
          <div style={{ color: '#10b981' }}>MPR UPLOAD (by Site Engineer) → parse_mpr() → exec_data{'{}'}</div>
          <div>        ↓</div>
          <div style={{ color: '#f59e0b' }}>COMPLIANCE ENGINE → 15 deterministic checks → compliance_events[]</div>
          <div>        ↓</div>
          <div style={{ color: '#ef4444' }}>RISK PREDICTOR → XGBoost(26 features) → risk_score + SHAP factors</div>
          <div>        ↓</div>
          <div style={{ color: '#10b981' }}>EXPLAINER AGENT → LLM narration (role-aware) → compliance.md + PDF</div>
          <div>        ↓</div>
          <div style={{ color: '#6b7280' }}>ESCALATION AGENT → daily timer check → cure period tracking → DRC notice</div>
        </div>
      </div>
    </div>
  );
}

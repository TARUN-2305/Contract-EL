import React, { useState } from 'react';
import axios from 'axios';
import { Settings, Cloud, Newspaper, Loader } from 'lucide-react';

export default function AdminPage() {
  const [weatherSource, setWeatherSource] = useState('open_meteo');
  const [weatherData, setWeatherData] = useState('');
  const [newsArticles, setNewsArticles] = useState('');
  const [status, setStatus] = useState({});
  const [loading, setLoading] = useState({});

  const setLoad = (key, val) => setLoading(l => ({ ...l, [key]: val }));
  const setMsg = (key, msg, type = 'success') => setStatus(s => ({ ...s, [key]: { msg, type } }));

  const applyWeather = async () => {
    setLoad('weather', true);
    try {
      const payload = { source: weatherSource };
      if (weatherSource === 'manual' && weatherData) payload.manual_data = JSON.parse(weatherData);
      await axios.post('/api/admin/weather-override', payload);
      setMsg('weather', `✅ Weather source set to: ${weatherSource}`);
    } catch (e) {
      setMsg('weather', `Error: ${e.response?.data?.detail || e.message}`, 'error');
    } finally { setLoad('weather', false); }
  };

  const applyNews = async () => {
    setLoad('news', true);
    try {
      const payload = newsArticles ? { manual_articles: JSON.parse(newsArticles) } : {};
      await axios.post('/api/admin/news-override', payload);
      setMsg('news', '✅ News override applied');
    } catch (e) {
      setMsg('news', `Error: ${e.response?.data?.detail || e.message}`, 'error');
    } finally { setLoad('news', false); }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin Overrides</h1>
          <p className="page-subtitle">Runtime control of weather, news data sources — no restart required</p>
        </div>
      </div>

      <div style={{ background: '#f59e0b15', border: '1px solid #f59e0b30', borderRadius: 8, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#f59e0b' }}>
        ⚠️ These overrides affect live compliance checks. The weather source controls FM (Force Majeure) validation — real IMD data vs synthetic fallback.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Weather override */}
        <div className="card">
          <h3 style={{ marginBottom: 4, fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}><Cloud size={16} color="#3b82f6" /> Weather Source</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            Used for FM (Force Majeure) claim validation. <strong>open_meteo</strong> = free, no key, real historical data.
          </p>

          <div className="form-group">
            <label className="form-label">Source</label>
            <select className="form-control" value={weatherSource} onChange={e => setWeatherSource(e.target.value)}>
              <option value="open_meteo">Open-Meteo (free, real historical data, no API key)</option>
              <option value="manual">Manual JSON (inject test data)</option>
              <option value="synthetic">Synthetic (random fallback, for testing only)</option>
            </select>
          </div>

          {weatherSource === 'manual' && (
            <div className="form-group">
              <label className="form-label">Manual Weather JSON</label>
              <textarea className="form-control" rows={5} value={weatherData} onChange={e => setWeatherData(e.target.value)}
                placeholder='{"total_mm": 92, "avg_temp": 28.5, "extreme_days": 4}' style={{ fontFamily: 'monospace', fontSize: 12 }} />
            </div>
          )}

          {status.weather && (
            <div className={`alert ${status.weather.type === 'error' ? 'alert-danger' : 'alert-success'}`} style={{ marginBottom: 12 }}>
              {status.weather.msg}
            </div>
          )}

          <button className="btn" onClick={applyWeather} disabled={loading.weather}>
            {loading.weather ? <Loader size={14} className="spin" /> : <Settings size={14} />} Apply Weather Override
          </button>

          <div style={{ marginTop: 14, padding: '10px', background: 'var(--bg-dark)', borderRadius: 8, fontSize: 11, color: 'var(--text-subtle)' }}>
            <strong>Open-Meteo:</strong> archive-api.open-meteo.com — provides free daily precipitation, temperature data going back decades.
            Used to cross-check contractor FM claims (was there actually a weather event on those dates?).
          </div>
        </div>

        {/* News override */}
        <div className="card">
          <h3 style={{ marginBottom: 4, fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}><Newspaper size={16} color="#8b5cf6" /> News / Risk Signals</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            Used by the Risk Agent to detect adverse events near the project site (labour strikes, floods, political unrest). Uses GNews API or manual injection.
          </p>

          <div className="form-group">
            <label className="form-label">Manual News Articles (JSON array)</label>
            <textarea className="form-control" rows={8} value={newsArticles} onChange={e => setNewsArticles(e.target.value)}
              placeholder={`[\n  {\n    "title": "NH-44 labour strike reported",\n    "date": "2025-05-15",\n    "sentiment": "negative",\n    "risk_signal": true\n  }\n]`}
              style={{ fontFamily: 'monospace', fontSize: 12 }} />
            <small style={{ color: 'var(--text-subtle)', fontSize: 11 }}>Leave empty to reset to GNews API or synthetic fallback</small>
          </div>

          {status.news && (
            <div className={`alert ${status.news.type === 'error' ? 'alert-danger' : 'alert-success'}`} style={{ marginBottom: 12 }}>
              {status.news.msg}
            </div>
          )}

          <button className="btn" onClick={applyNews} disabled={loading.news}>
            {loading.news ? <Loader size={14} className="spin" /> : <Settings size={14} />} Apply News Override
          </button>
        </div>
      </div>
    </div>
  );
}

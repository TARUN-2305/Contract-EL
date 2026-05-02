import React, { useState } from 'react';
import axios from 'axios';
import { Settings, CloudRain, Newspaper, CheckCircle, AlertTriangle } from 'lucide-react';

export default function AdminPage() {
  const [weatherSource, setWeatherSource] = useState('synthetic');
  const [weatherJson, setWeatherJson] = useState('{\n  "total_rainfall_mm": 150,\n  "extreme_rainfall_days": 3,\n  "historical_average_mm": 50,\n  "period_days": 30\n}');
  const [newsJson, setNewsJson] = useState('[\n  {\n    "title": "Severe Flooding in Karnataka",\n    "description": "Flash floods have halted all construction work in the region.",\n    "publishedAt": "2025-05-15T10:00:00Z"\n  }\n]');
  
  const [msg, setMsg] = useState(null);

  const applyWeather = async () => {
    try {
      const payload = { source: weatherSource };
      if (weatherSource === 'manual') {
        payload.manual_data = JSON.parse(weatherJson);
      }
      await axios.post('/api/admin/weather-override', payload);
      setMsg({ type: 'success', text: 'Weather override applied successfully.' });
    } catch (err) {
      setMsg({ type: 'error', text: 'Failed to apply weather override: ' + err.message });
    }
  };

  const applyNews = async () => {
    try {
      const payload = { manual_articles: JSON.parse(newsJson) };
      await axios.post('/api/admin/news-override', payload);
      setMsg({ type: 'success', text: 'News override applied successfully.' });
    } catch (err) {
      setMsg({ type: 'error', text: 'Failed to apply news override: ' + err.message });
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title"><Settings size={24} style={{ display: 'inline', verticalAlign: 'text-bottom' }} /> Admin Controls</h1>
          <p className="page-subtitle">Configure runtime overrides for external integrations</p>
        </div>
      </div>

      {msg && (
        <div className={`alert alert-${msg.type === 'success' ? 'success' : 'danger'} mb-3`}>
          {msg.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {msg.text}
        </div>
      )}

      <div className="two-col">
        <div className="card">
          <h3 className="section-title"><CloudRain size={18} /> Weather Override</h3>
          <div className="form-group">
            <label className="form-label">Weather Data Source</label>
            <select className="form-control" value={weatherSource} onChange={e => setWeatherSource(e.target.value)}>
              <option value="synthetic">Synthetic (Deterministic Fallback)</option>
              <option value="open_meteo">Open-Meteo Archive API</option>
              <option value="manual">Manual JSON Override</option>
            </select>
          </div>
          {weatherSource === 'manual' && (
            <div className="form-group">
              <label className="form-label">Manual Weather Data (JSON)</label>
              <textarea className="form-control" rows={6} value={weatherJson} onChange={e => setWeatherJson(e.target.value)} style={{ fontFamily: 'monospace', fontSize: '0.85rem' }} />
            </div>
          )}
          <button className="btn" onClick={applyWeather}>Apply Weather Settings</button>
        </div>

        <div className="card">
          <h3 className="section-title"><Newspaper size={18} /> News Override</h3>
          <p className="text-muted text-sm mb-2">Override GNews results with manual articles to force Force Majeure political/riot validations.</p>
          <div className="form-group">
            <label className="form-label">Manual News Articles (JSON Array)</label>
            <textarea className="form-control" rows={8} value={newsJson} onChange={e => setNewsJson(e.target.value)} style={{ fontFamily: 'monospace', fontSize: '0.85rem' }} />
          </div>
          <button className="btn" onClick={applyNews}>Apply News Override</button>
        </div>
      </div>
    </div>
  );
}

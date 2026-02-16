import React, { useState } from 'react';
import { Zap, Key, Plus, Trash2, Check, X, ChevronDown, ChevronUp, Wifi, WifiOff, AlertCircle } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const PROVIDER_COLORS = {
  groq: { bg: 'linear-gradient(135deg, #f97316, #ef4444)', color: '#fff' },
  openai: { bg: 'linear-gradient(135deg, #10a37f, #0d8f6e)', color: '#fff' },
  anthropic: { bg: 'linear-gradient(135deg, #d4a574, #b8956a)', color: '#1a1a1a' },
  google: { bg: 'linear-gradient(135deg, #4285f4, #00c896)', color: '#fff' },
  openrouter: { bg: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' },
};

function Toggle({ on, onClick }) {
  return (
    <div className={`toggle ${on ? 'on' : ''}`} onClick={onClick} data-testid="toggle">
      <div className="toggle-knob" />
    </div>
  );
}

function ProviderCard({ provider, isActive, onSetActive, onRefresh, initData }) {
  const [expanded, setExpanded] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [selectedModel, setSelectedModel] = useState(provider.selected_model || '');

  const colors = PROVIDER_COLORS[provider.name] || { bg: 'var(--bg-elevated)', color: 'var(--text-primary)' };
  const hasModels = provider.models && provider.models.length > 0;
  const hasKeys = provider.keys_count > 0;

  const headers = { 'Content-Type': 'application/json' };
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await fetch(`${API}/api/ai/test-connection`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ provider: provider.name })
      });
      const data = await r.json();
      setTestResult(data);
      if (data.ok) {
        onRefresh();
      }
    } catch (e) {
      setTestResult({ ok: false, error: 'Network error' });
    } finally {
      setTesting(false);
    }
  };

  const addKey = async () => {
    if (!newKey.trim()) return;
    await fetch(`${API}/api/settings/providers/${provider.name}/keys`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ key: newKey.trim() })
    });
    setNewKey('');
    onRefresh();
  };

  const removeKey = async (index) => {
    await fetch(`${API}/api/settings/providers/${provider.name}/keys/${index}`, { method: 'DELETE', headers });
    onRefresh();
  };

  const toggleEnabled = async () => {
    await fetch(`${API}/api/settings/providers/${provider.name}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({ enabled: !provider.enabled })
    });
    onRefresh();
  };

  const changeModel = async (model) => {
    setSelectedModel(model);
    await fetch(`${API}/api/ai/set-model`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ provider: provider.name, model })
    });
    onRefresh();
  };

  const setAsActive = async () => {
    await fetch(`${API}/api/ai/set-active-provider`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ provider: provider.name })
    });
    onSetActive();
  };

  return (
    <div className={`provider-card ${isActive ? 'active-provider' : ''}`} data-testid={`provider-${provider.name}`}>
      <div className="provider-header">
        <div className="provider-name">
          <div className="provider-icon" style={{ background: colors.bg, color: colors.color }}>
            {provider.display_name[0]}
          </div>
          <span>{provider.display_name}</span>
          {isActive && <span className="badge badge-accent">Active</span>}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Toggle on={provider.enabled} onClick={toggleEnabled} />
          <button className="btn btn-icon btn-secondary" onClick={() => setExpanded(!expanded)} data-testid={`expand-${provider.name}`}>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      <div className="provider-meta">
        <span className="badge badge-muted"><Key size={10} /> {provider.keys_count || 0} ключей</span>
        {hasModels ? (
          <span className="badge badge-info">{provider.selected_model || 'выберите модель'}</span>
        ) : (
          <span className="badge badge-muted">нет моделей</span>
        )}
        {provider.enabled && hasKeys && hasModels ? (
          <span className="badge badge-success"><Wifi size={10} /> Готов</span>
        ) : !hasKeys ? (
          <span className="badge badge-warning"><AlertCircle size={10} /> Нужен ключ</span>
        ) : !hasModels ? (
          <span className="badge badge-warning"><WifiOff size={10} /> Проверьте соединение</span>
        ) : (
          <span className="badge badge-muted"><WifiOff size={10} /> Выключен</span>
        )}
      </div>

      {!isActive && provider.enabled && hasKeys && hasModels && (
        <button className="btn btn-primary btn-sm" onClick={setAsActive} style={{ marginBottom: 8 }} data-testid={`activate-${provider.name}`}>
          <Zap size={13} /> Сделать активным
        </button>
      )}

      {expanded && (
        <div className="animate-fade" style={{ marginTop: 8 }}>
          {/* Keys section */}
          <div style={{ marginBottom: 12 }}>
            <span className="card-title" style={{ display: 'block', marginBottom: 6 }}>API Ключи</span>
            {(provider.api_keys_masked || []).map((k, i) => (
              <div className={`key-item ${i === provider.active_key_index ? 'key-active' : ''}`} key={i}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {k} {i === provider.active_key_index && <Check size={11} style={{ color: 'var(--accent)' }} />}
                </span>
                <button className="btn btn-icon btn-danger" style={{ width: 26, height: 26 }} onClick={() => removeKey(i)} data-testid={`remove-key-${provider.name}-${i}`}>
                  <Trash2 size={11} />
                </button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
              <input
                className="input"
                placeholder="Вставьте API ключ..."
                value={newKey}
                onChange={e => setNewKey(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addKey()}
                style={{ flex: 1, fontSize: '0.82rem' }}
                data-testid={`add-key-input-${provider.name}`}
              />
              <button className="btn btn-primary btn-sm" onClick={addKey} data-testid={`add-key-btn-${provider.name}`}>
                <Plus size={13} />
              </button>
            </div>
          </div>

          {/* Model select — only if models loaded */}
          {hasModels ? (
            <div style={{ marginBottom: 12 }}>
              <span className="card-title" style={{ display: 'block', marginBottom: 6 }}>Модель ({provider.models.length} доступно)</span>
              <select
                className="select"
                value={selectedModel}
                onChange={e => changeModel(e.target.value)}
                data-testid={`model-select-${provider.name}`}
              >
                <option value="">Выберите модель...</option>
                {provider.models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          ) : (
            <div style={{ marginBottom: 12, padding: '10px 12px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                Добавьте API ключ и нажмите «Проверить соединение» для загрузки доступных моделей
              </span>
            </div>
          )}

          {/* Test connection */}
          <button
            className={`btn ${hasKeys ? 'btn-primary' : 'btn-secondary'}`}
            onClick={testConnection}
            disabled={testing || !hasKeys}
            style={{ width: '100%' }}
            data-testid={`test-conn-${provider.name}`}
          >
            {testing ? (
              <><span className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Проверка...</>
            ) : (
              <><Wifi size={14} /> Проверить соединение</>
            )}
          </button>

          {testResult && (
            <div className={`test-result ${testResult.ok ? 'success' : 'error'}`} data-testid={`test-result-${provider.name}`}>
              {testResult.ok ? (
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 3, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Check size={14} /> Соединение установлено
                  </div>
                  <div style={{ fontSize: '0.82rem' }}>Доступно моделей: {testResult.count || testResult.models?.length || 0}</div>
                </div>
              ) : (
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 3, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <X size={14} /> Ошибка соединения
                  </div>
                  <div style={{ fontSize: '0.78rem', opacity: 0.85 }}>{testResult.error}</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProvidersPage({ providers, settings, onRefresh, initData }) {
  const activeProvider = settings?.active_provider || '';
  const enabledCount = providers.filter(p => p.enabled).length;
  const readyCount = providers.filter(p => p.enabled && p.keys_count > 0 && p.models?.length > 0).length;

  return (
    <div data-testid="providers-page">
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-header">
          <span className="card-title">AI Провайдеры</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <span className="badge badge-info">{enabledCount} вкл</span>
            <span className="badge badge-success">{readyCount} готовых</span>
          </div>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', lineHeight: 1.55 }}>
          Добавьте API ключи и проверьте соединение для загрузки моделей.
          При исчерпании лимитов ключа система автоматически переключается на следующий.
          Если все ключи провайдера недоступны — используется другой активный провайдер.
        </p>
      </div>

      {providers.map(p => (
        <ProviderCard
          key={p.name}
          provider={p}
          isActive={p.name === activeProvider}
          onSetActive={onRefresh}
          onRefresh={onRefresh}
          initData={initData}
        />
      ))}
    </div>
  );
}

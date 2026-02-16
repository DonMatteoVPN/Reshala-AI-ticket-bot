import React, { useState, useEffect } from 'react';
import { Save, RefreshCw, Eye, EyeOff, Sparkles, Info } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function InputWithEye({ label, placeholder, value, onChange, testId, hint }) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="input-group">
      <label className="input-label">{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          className="input"
          type={visible ? 'text' : 'password'}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          style={{ paddingRight: 42 }}
          data-testid={testId}
        />
        <button
          type="button"
          className="btn-eye"
          onClick={() => setVisible(!visible)}
          data-testid={`${testId}-toggle`}
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
      {hint && <p className="input-hint">{hint}</p>}
    </div>
  );
}

export default function SettingsPage({ settings, onUpdate, initData }) {
  const [form, setForm] = useState({
    service_name: settings?.service_name || '',
    main_bot_username: settings?.main_bot_username || '',
    bot_token: settings?.bot_token || '',
    remnawave_api_url: settings?.remnawave_api_url || '',
    remnawave_api_token: settings?.remnawave_api_token || '',
    allowed_manager_ids: (settings?.allowed_manager_ids || []).join(', '),
    support_group_id: settings?.support_group_id || '',
    mini_app_domain: settings?.mini_app_domain || '',
    bedolaga_webhook_url: settings?.bedolaga_webhook_url || settings?.bedolaga_api_url || '',
    bedolaga_web_api_token: settings?.bedolaga_web_api_token || settings?.bedolaga_api_token || '',
    system_prompt_override: settings?.system_prompt_override || '',
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [stockPrompt, setStockPrompt] = useState(null);

  const handleChange = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const headers = { 'Content-Type': 'application/json' };
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  const handleSave = async () => {
    setSaving(true);
    setMsg('');
    try {
      const payload = {
        ...form,
        allowed_manager_ids: form.allowed_manager_ids.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n)),
        support_group_id: form.support_group_id ? parseInt(form.support_group_id) : null,
      };
      const r = await fetch(`${API}/api/settings`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      if (data.ok) {
        setMsg('Настройки сохранены');
        onUpdate();
      } else {
        setMsg('Ошибка: ' + (data.error || 'unknown'));
      }
    } catch (e) {
      setMsg('Ошибка сети');
    } finally {
      setSaving(false);
    }
  };

  const loadStockPrompt = async () => {
    try {
      const r = await fetch(`${API}/api/ai/stock-prompt`, { headers });
      const data = await r.json();
      if (data.prompt) {
        handleChange('system_prompt_override', data.prompt);
        setStockPrompt(data);
        setMsg('Стоковый промпт загружен. Не забудьте сохранить!');
      }
    } catch (e) {
      setMsg('Ошибка загрузки промпта');
    }
  };

  const textFields = [
    { key: 'service_name', label: 'Название сервиса', placeholder: 'Решала Support', hint: 'Используется в промпте AI как {service_name}' },
    { key: 'main_bot_username', label: 'Username основного бота', placeholder: 'YourVPNBot', hint: 'Бот для покупки подписки. Используется как {main_bot}' },
    { key: 'allowed_manager_ids', label: 'ID менеджеров (через запятую)', placeholder: '123456789, 987654321' },
    { key: 'support_group_id', label: 'ID группы поддержки', placeholder: '-1001234567890' },
    { key: 'mini_app_domain', label: 'Домен Mini App', placeholder: 'app.example.com' },
  ];

  const secretFields = [
    { key: 'bot_token', label: 'Bot Token', placeholder: 'xxxxx:yyyyy' },
    { key: 'remnawave_api_url', label: 'Remnawave API URL', placeholder: 'https://api.example.com' },
    { key: 'remnawave_api_token', label: 'Remnawave API Token', placeholder: 'Bearer token' },
    { key: 'bedolaga_webhook_url', label: 'Bedolaga WEBHOOK_URL', placeholder: 'https://bedolaga.example.com' },
    { key: 'bedolaga_web_api_token', label: 'Bedolaga WEB_API_DEFAULT_TOKEN', placeholder: 'API key' },
  ];

  return (
    <div data-testid="settings-page">
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <span className="card-title">Основные настройки</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 4 }}>
          Конфигурация бота и API. Все изменения сохраняются в базу данных.
        </p>
      </div>

      {msg && (
        <div className={`alert ${msg.includes('Ошибка') ? 'alert-error' : 'alert-success'}`} data-testid="settings-msg">
          {msg}
        </div>
      )}

      <div className="card">
        {textFields.map(f => (
          <div className="input-group" key={f.key}>
            <label className="input-label">{f.label}</label>
            <input
              className="input"
              type="text"
              placeholder={f.placeholder}
              value={form[f.key]}
              onChange={e => handleChange(f.key, e.target.value)}
              data-testid={`setting-${f.key}`}
            />
            {f.hint && <p className="input-hint">{f.hint}</p>}
          </div>
        ))}

        {secretFields.map(f => (
          <InputWithEye
            key={f.key}
            label={f.label}
            placeholder={f.placeholder}
            value={form[f.key]}
            onChange={e => handleChange(f.key, e.target.value)}
            testId={`setting-${f.key}`}
          />
        ))}

        <div className="input-group">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <label className="input-label" style={{ margin: 0 }}>Системный промпт AI</label>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={loadStockPrompt}
              data-testid="load-stock-prompt"
            >
              <Sparkles size={13} /> Стоковый промпт
            </button>
          </div>
          <textarea
            className="input"
            rows={8}
            placeholder="Оставьте пустым для промпта по умолчанию..."
            value={form.system_prompt_override}
            onChange={e => handleChange('system_prompt_override', e.target.value)}
            style={{ resize: 'vertical', minHeight: 120 }}
            data-testid="setting-system-prompt"
          />
          <div className="prompt-variables">
            <Info size={12} style={{ marginRight: 4 }} />
            <span>Переменные: </span>
            <code>{'{service_name}'}</code> — название сервиса,
            <code>{'{main_bot}'}</code> — username основного бота
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving} data-testid="save-settings-btn">
            {saving ? <><RefreshCw size={16} className="loading-spinner" /> Сохранение...</> : <><Save size={16} /> Сохранить</>}
          </button>
        </div>
      </div>
    </div>
  );
}

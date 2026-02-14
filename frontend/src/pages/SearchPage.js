import React, { useState, useEffect } from 'react';
import { Search, User, BarChart3, Calendar, Link2, Smartphone, RotateCcw, RefreshCw, Trash2, Lock, Unlock, Wallet, Copy, Check } from 'lucide-react';
import ConfirmModal from '../components/ConfirmModal';

const API = process.env.REACT_APP_BACKEND_URL;

function formatBytes(b) {
  let n = Number(b) || 0;
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(2) + ' ' + u[i];
}

function formatDate(str) {
  if (!str) return 'Не указано';
  try {
    const d = new Date(str.replace('Z', '+00:00'));
    if (isNaN(d.getTime())) return str;
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return str; }
}

// Компонент копирования ID нажатием
function CopyableField({ label, value, code }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  return (
    <div className="data-row copyable-row" onClick={handleCopy} style={{ cursor: value ? 'pointer' : 'default' }} title={value ? 'Нажмите для копирования' : ''}>
      <span className="data-label">{label}</span>
      <span className="data-value" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {code ? <code>{value || '—'}</code> : (value || '—')}
        {value && (
          <span className={`copy-icon ${copied ? 'copied' : ''}`}>
            {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} style={{ opacity: 0.5 }} />}
          </span>
        )}
      </span>
    </div>
  );
}

const DataRow = ({ label, value, code }) => (
  <div className="data-row">
    <span className="data-label">{label}</span>
    <span className="data-value">{code ? <code>{value || '—'}</code> : (value || '—')}</span>
  </div>
);

const SectionTabs = [
  { id: 'profile', label: 'Профиль', icon: User },
  { id: 'traffic', label: 'Трафик', icon: BarChart3 },
  { id: 'dates', label: 'Даты', icon: Calendar },
  { id: 'subscription', label: 'Подписка', icon: Link2 },
  { id: 'hwid', label: 'Устройства', icon: Smartphone },
  { id: 'balance', label: 'Баланс', icon: Wallet },
];

function ProfilePanel({ user }) {
  return (
    <div className="card animate-fade" data-testid="panel-profile">
      <div className="card-header"><span className="card-title">Профиль</span></div>
      <CopyableField label="UUID" value={user.uuid} code />
      <CopyableField label="Short UUID" value={user.shortUuid} code />
      <CopyableField label="ID" value={user.id} />
      <DataRow label="Username" value={user.username ? `@${user.username}` : 'N/A'} />
      <CopyableField label="Email" value={user.email || ''} />
      <CopyableField label="Telegram ID" value={user.telegramId || ''} />
      <DataRow label="Статус" value={user.status} />
      <DataRow label="Тег" value={user.tag || 'Не указан'} />
      {user.hwidDeviceLimit != null && <DataRow label="Лимит устройств" value={user.hwidDeviceLimit} />}
    </div>
  );
}

function TrafficPanel({ user }) {
  const ut = user.userTraffic || {};
  return (
    <div className="card animate-fade" data-testid="panel-traffic">
      <div className="card-header"><span className="card-title">Трафик</span></div>
      {ut.usedTrafficBytes !== undefined ? (
        <>
          <DataRow label="Использовано" value={formatBytes(ut.usedTrafficBytes || 0)} />
          <DataRow label="Всего за всё время" value={formatBytes(ut.lifetimeUsedTrafficBytes || 0)} />
          <DataRow label="Лимит" value={user.trafficLimitBytes > 0 ? formatBytes(user.trafficLimitBytes) : 'Безлимит'} />
          <DataRow label="Стратегия сброса" value={user.trafficLimitStrategy || 'NO_RESET'} />
          {ut.onlineAt && <DataRow label="Онлайн" value={formatDate(ut.onlineAt)} />}
          {ut.firstConnectedAt && <DataRow label="Первое подключение" value={formatDate(ut.firstConnectedAt)} />}
        </>
      ) : (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Нет данных о трафике</p>
      )}
    </div>
  );
}

function DatesPanel({ user }) {
  return (
    <div className="card animate-fade" data-testid="panel-dates">
      <div className="card-header"><span className="card-title">Даты</span></div>
      <DataRow label="Истекает" value={formatDate(user.expireAt)} />
      <DataRow label="Создан" value={formatDate(user.createdAt)} />
      <DataRow label="Обновлён" value={formatDate(user.updatedAt)} />
      {user.subRevokedAt && <DataRow label="Подписка отозвана" value={formatDate(user.subRevokedAt)} />}
      {user.subLastOpenedAt && <DataRow label="Последнее открытие" value={formatDate(user.subLastOpenedAt)} />}
    </div>
  );
}

function SubscriptionPanel({ subscription }) {
  if (!subscription) return (
    <div className="card animate-fade" data-testid="panel-subscription">
      <div className="card-header"><span className="card-title">Подписка</span></div>
      <p style={{ color: 'var(--text-muted)' }}>Данные недоступны</p>
    </div>
  );
  const su = subscription.user || {};
  return (
    <div className="card animate-fade" data-testid="panel-subscription">
      <div className="card-header"><span className="card-title">Подписка</span></div>
      <DataRow label="Найдена" value={subscription.isFound ? 'Да' : 'Нет'} />
      {su.daysLeft !== undefined && <DataRow label="Дней осталось" value={su.daysLeft} />}
      {su.trafficUsed && <DataRow label="Использовано" value={su.trafficUsed} />}
      {su.trafficLimit && <DataRow label="Лимит" value={su.trafficLimit} />}
      <DataRow label="Активна" value={su.isActive ? 'Да' : 'Нет'} />
      <DataRow label="Статус" value={su.userStatus || '—'} />
    </div>
  );
}

function HwidPanel({ devices, userUuid, onAction }) {
  return (
    <div className="card animate-fade" data-testid="panel-hwid">
      <div className="card-header"><span className="card-title">Устройства (HWID)</span></div>
      {!devices || !devices.length ? (
        <p style={{ color: 'var(--text-muted)' }}>Устройства не найдены</p>
      ) : (
        <>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 12 }}>Всего: {devices.length}</p>
          {devices.map((d, i) => (
            <div className="device-block" key={i}>
              <div className="device-title">Устройство {i + 1}</div>
              <DataRow label="HWID" value={d.hwid} code />
              {d.platform && <DataRow label="Платформа" value={d.platform} />}
              {d.osVersion && <DataRow label="ОС" value={d.osVersion} />}
              {d.deviceModel && <DataRow label="Модель" value={d.deviceModel} />}
              {d.createdAt && <DataRow label="Добавлено" value={formatDate(d.createdAt)} />}
              <button
                className="btn btn-danger btn-sm"
                style={{ marginTop: 8 }}
                onClick={() => onAction('hwid-delete', { userUuid, hwid: d.hwid }, 'Удаление устройства', `Удалить устройство ${d.platform || d.hwid.slice(0, 8)}?`, true)}
                data-testid={`hwid-delete-${i}`}
              >
                <Trash2 size={14} /> Удалить
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function BalancePanel({ telegramId }) {
  const [balance, setBalance] = useState(null);
  const [deposits, setDeposits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showHistory, setShowHistory] = useState(false);

  const fetchBalance = async () => {
    if (!telegramId) {
      setError('Telegram ID не найден');
      return;
    }
    setLoading(true);
    setError('');
    try {
      // Запрашиваем баланс и историю параллельно
      const [balanceRes, depositsRes] = await Promise.all([
        fetch(`${API}/api/bedolaga/balance/${telegramId}`),
        fetch(`${API}/api/bedolaga/deposits/${telegramId}`)
      ]);
      
      const balanceData = await balanceRes.json();
      const depositsData = await depositsRes.json();
      
      if (balanceData.ok) {
        setBalance(balanceData);
      } else {
        setError(balanceData.error || 'Ошибка загрузки баланса');
      }
      
      if (depositsData.ok) {
        setDeposits(depositsData.deposits || []);
      }
    } catch (e) {
      setError('Ошибка сети');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (telegramId) {
      fetchBalance();
    }
  }, [telegramId]);

  return (
    <div className="card animate-fade" data-testid="panel-balance">
      <div className="card-header">
        <span className="card-title">Баланс (Bedolaga)</span>
        <button className="btn btn-secondary btn-sm" onClick={fetchBalance} disabled={loading}>
          <RefreshCw size={13} className={loading ? 'loading-spinner' : ''} /> Обновить
        </button>
      </div>
      {error ? (
        <div className="alert alert-error" style={{ marginTop: 8 }}>{error}</div>
      ) : balance ? (
        <>
          <DataRow label="Баланс" value={`${balance.balance || 0} ${balance.currency || 'RUB'}`} />
          {balance.total_deposits !== undefined && <DataRow label="Всего пополнений" value={balance.total_deposits} />}
          {balance.last_deposit && <DataRow label="Последнее пополнение" value={formatDate(balance.last_deposit)} />}
          
          {/* История пополнений */}
          {deposits.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => setShowHistory(!showHistory)}
                style={{ marginBottom: 10, width: '100%' }}
              >
                {showHistory ? '▲ Скрыть историю' : `▼ История пополнений (${deposits.length})`}
              </button>
              
              {showHistory && (
                <div className="deposits-list" style={{ 
                  background: 'var(--bg-elevated)', 
                  borderRadius: 'var(--radius-md)',
                  padding: 12,
                  maxHeight: 300,
                  overflowY: 'auto'
                }}>
                  {deposits.map((d, i) => (
                    <div 
                      key={i} 
                      className="deposit-item" 
                      style={{ 
                        padding: '8px 10px',
                        background: 'var(--bg-card)',
                        borderRadius: 'var(--radius-sm)',
                        marginBottom: 6,
                        border: '1px solid var(--border-default)'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, color: 'var(--success)' }}>
                          +{d.amount || 0} {d.currency || 'RUB'}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {formatDate(d.created_at || d.date)}
                        </span>
                      </div>
                      {d.method && (
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                          {d.method}
                        </div>
                      )}
                      {d.status && (
                        <span 
                          className={`badge ${d.status === 'completed' ? 'badge-success' : 'badge-warning'}`}
                          style={{ marginTop: 4 }}
                        >
                          {d.status === 'completed' ? '✓ Завершён' : d.status}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {deposits.length === 0 && !loading && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 12 }}>
              История пополнений пуста
            </p>
          )}
        </>
      ) : (
        <p style={{ color: 'var(--text-muted)' }}>Загрузка...</p>
      )}
    </div>
  );
}

export default function SearchPage({ settings, searchState, setSearchState }) {
  const [query, setQuery] = useState(searchState?.query || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(searchState?.result || null);
  const [section, setSection] = useState(searchState?.section || 'profile');
  const [actionMsg, setActionMsg] = useState('');
  const [confirm, setConfirm] = useState({ open: false, action: null, data: null, title: '', message: '', danger: false });

  // Сохраняем состояние при изменении
  useEffect(() => {
    if (setSearchState) {
      setSearchState({ query, result, section });
    }
  }, [query, result, section, setSearchState]);

  const doSearch = async () => {
    const q = query.trim();
    if (!q) { setError('Введите Telegram ID или @username'); return; }
    setLoading(true);
    setError('');
    setResult(null);
    setActionMsg('');
    try {
      const r = await fetch(`${API}/api/lookup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
      });
      const data = await r.json();
      if (data.ok) {
        setResult(data);
        setSection('profile');
      } else {
        const msgs = { user_not_found: 'Пользователь не найден', remnawave_not_configured: 'API Remnawave не настроен', query_required: 'Введите запрос' };
        setError(msgs[data.error] || data.error || 'Ошибка');
      }
    } catch (e) {
      setError('Ошибка сети');
    } finally {
      setLoading(false);
    }
  };

  const showConfirm = (action, data, title, message, danger = false) => {
    setConfirm({ open: true, action, data, title, message, danger });
  };

  const handleConfirm = async () => {
    const { action, data } = confirm;
    setConfirm({ open: false, action: null, data: null, title: '', message: '', danger: false });
    setActionMsg('');
    try {
      const r = await fetch(`${API}/api/actions/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      const res = await r.json();
      setActionMsg(res.message || (res.ok ? 'Готово' : 'Ошибка'));
      if (res.ok && query.trim()) {
        setTimeout(() => doSearch(), 500);
      }
    } catch {
      setActionMsg('Ошибка сети');
    }
  };

  const user = result?.user;
  const uuid = user?.uuid || '';
  const telegramId = user?.telegramId || '';
  const isDisabled = (user?.status || '').toUpperCase() === 'DISABLED';

  return (
    <div data-testid="search-page">
      <div className="search-section">
        <div className="search-input-wrap">
          <Search />
          <input
            className="search-input"
            placeholder="Telegram ID или @username"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && doSearch()}
            data-testid="search-input"
          />
        </div>
        <button className="btn btn-primary" onClick={doSearch} disabled={loading} data-testid="search-btn">
          {loading ? <span className="loading-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} /> : 'Найти'}
        </button>
      </div>

      {error && <div className="alert alert-error" data-testid="search-error">{error}</div>}
      {actionMsg && <div className="alert alert-info" data-testid="action-message">{actionMsg}</div>}

      {result && user && (
        <div className="animate-slide">
          <div className="user-card-header" data-testid="user-card">
            <div className="user-info">
              <div className="user-avatar">{(user.username || 'U')[0].toUpperCase()}</div>
              <div>
                <div className="user-name">{user.username ? `@${user.username}` : `ID ${user.telegramId || user.id}`}</div>
              </div>
            </div>
            <span className={`badge ${(user.status || '').toUpperCase() === 'ACTIVE' ? 'badge-success' : 'badge-danger'}`}>
              {user.status || '—'}
            </span>
          </div>

          <div className="actions-bar">
            <button className="btn btn-secondary btn-sm" onClick={() => showConfirm('reset-traffic', { userUuid: uuid }, 'Сброс трафика', 'Сбросить использованный трафик пользователя?')} data-testid="btn-reset-traffic">
              <RotateCcw size={14} /> Сброс трафика
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => showConfirm('revoke-subscription', { userUuid: uuid }, 'Перевыпуск подписки', 'Перевыпустить подписку пользователя? Будет сгенерирован новый ключ.')} data-testid="btn-revoke-sub">
              <RefreshCw size={14} /> Перевыпуск
            </button>
            <button className="btn btn-danger btn-sm" onClick={() => showConfirm('hwid-delete-all', { userUuid: uuid }, 'Удаление всех устройств', 'Удалить ВСЕ привязанные устройства пользователя?', true)} data-testid="btn-hwid-all">
              <Trash2 size={14} /> HWID
            </button>
            {isDisabled ? (
              <button className="btn btn-secondary btn-sm" onClick={() => showConfirm('enable-user', { userUuid: uuid }, 'Разблокировка', 'Разблокировать профиль пользователя?')} data-testid="btn-enable">
                <Unlock size={14} /> Разблокировать
              </button>
            ) : (
              <button className="btn btn-danger btn-sm" onClick={() => showConfirm('disable-user', { userUuid: uuid }, 'Блокировка', 'Заблокировать профиль пользователя? Он потеряет доступ к VPN.', true)} data-testid="btn-disable">
                <Lock size={14} /> Заблокировать
              </button>
            )}
          </div>

          <div className="tabs">
            {SectionTabs.map(t => (
              <button
                key={t.id}
                className={`tab ${section === t.id ? 'active' : ''}`}
                onClick={() => setSection(t.id)}
                data-testid={`tab-${t.id}`}
              >
                <t.icon size={14} style={{ marginRight: 4, verticalAlign: -2 }} />
                {t.label}
              </button>
            ))}
          </div>

          {section === 'profile' && <ProfilePanel user={user} />}
          {section === 'traffic' && <TrafficPanel user={user} />}
          {section === 'dates' && <DatesPanel user={user} />}
          {section === 'subscription' && <SubscriptionPanel subscription={result.subscription} />}
          {section === 'hwid' && <HwidPanel devices={result.hwid_devices} userUuid={uuid} onAction={showConfirm} />}
          {section === 'balance' && <BalancePanel telegramId={telegramId} />}
        </div>
      )}

      {!result && !error && !loading && (
        <div className="empty-state" data-testid="empty-state">
          <div className="empty-icon"><Search size={24} /></div>
          <div className="empty-title">Поиск пользователя</div>
          <div className="empty-text">Введите Telegram ID или @username для поиска информации о пользователе в системе</div>
        </div>
      )}

      <ConfirmModal
        isOpen={confirm.open}
        title={confirm.title}
        message={confirm.message}
        danger={confirm.danger}
        onConfirm={handleConfirm}
        onCancel={() => setConfirm({ open: false, action: null, data: null, title: '', message: '', danger: false })}
      />
    </div>
  );
}

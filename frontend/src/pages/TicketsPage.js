import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Flame, RotateCcw, RefreshCw, Trash2, Lock, Unlock,
  AlertTriangle, Clock, Send, X, ChevronRight,
  User, Wifi, WifiOff, Shield, Calendar, BarChart3,
  MessageSquare, CheckCircle, Eye
} from 'lucide-react';
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
  if (!str) return '—';
  try {
    const d = new Date(str.replace ? str.replace('Z', '+00:00') : str);
    if (isNaN(d.getTime())) return str;
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return str; }
}

function formatDateShort(str) {
  if (!str) return '';
  try {
    const d = new Date(str.replace ? str.replace('Z', '+00:00') : str);
    if (isNaN(d.getTime())) return str;
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'только что';
    if (diff < 3600000) return Math.floor(diff / 60000) + ' мин назад';
    if (diff < 86400000) return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  } catch { return str; }
}

const TICKET_STATUSES = {
  open:       { emoji: '💬', label: 'Открыт',          color: 'info' },
  escalated:  { emoji: '🔥', label: 'Эскалация',       color: 'warning' },
  suspicious: { emoji: '🚨', label: 'Подозрительный',  color: 'danger' },
  closed:     { emoji: '✅', label: 'Закрыт',           color: 'success' },
};

// ─── Chat bubble component ─────────────────────────────────────────────────
function ChatBubble({ msg }) {
  const isUser    = msg.role === 'user';
  const isManager = msg.role === 'manager';
  const isAI      = msg.role === 'assistant' || msg.role === 'ai';

  const label = isUser ? '👤 Клиент'
    : isManager ? `👨‍💼 ${msg.name || 'Менеджер'}`
    : '🤖 AI';

  return (
    <div className={`bubble-row ${isUser ? 'bubble-row-user' : 'bubble-row-other'}`}>
      <div className={`bubble ${isUser ? 'bubble-user' : isManager ? 'bubble-manager' : 'bubble-ai'}`}>
        <div className="bubble-label">{label}</div>
        <div className="bubble-text">{msg.content}</div>
        {msg.timestamp && (
          <div className="bubble-time">{formatDateShort(msg.timestamp)}</div>
        )}
      </div>
    </div>
  );
}

// ─── Traffic bar ───────────────────────────────────────────────────────────
function TrafficBar({ used, limit }) {
  if (!limit || limit <= 0) return (
    <div className="traffic-info">
      <span>{formatBytes(used)}</span>
      <span className="badge badge-success">∞ безлимит</span>
    </div>
  );
  const pct = Math.min(100, Math.round((used / limit) * 100));
  const color = pct > 90 ? 'var(--danger)' : pct > 70 ? 'var(--warning)' : 'var(--accent)';
  return (
    <div>
      <div className="traffic-info">
        <span>{formatBytes(used)} / {formatBytes(limit)}</span>
        <span style={{ color, fontWeight: 700 }}>{pct}%</span>
      </div>
      <div className="traffic-bar-track">
        <div className="traffic-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

// ─── User panel (right) ────────────────────────────────────────────────────
function UserPanel({ ticket, userData, loadingUser, onAction, initData }) {
  const [replyText, setReplyText]   = useState('');
  const [sending, setSending]       = useState(false);
  const [sendMsg, setSendMsg]       = useState('');
  const [activeTab, setActiveTab]   = useState('chat');
  const messagesEndRef               = useRef(null);
  const headers = { 'Content-Type': 'application/json' };
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  // Auto-scroll when chat tab active
  useEffect(() => {
    if (activeTab === 'chat' && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [ticket?.history, ticket?.last_messages, activeTab]);

  const sendReply = async () => {
    if (!replyText.trim() || !ticket) return;
    setSending(true);
    try {
      const r = await fetch(`${API}/api/tickets/${ticket.id}/reply`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: replyText.trim(), manager_name: 'Менеджер' })
      });
      const data = await r.json();
      if (data.ok) {
        setReplyText('');
        setSendMsg('✅ Ответ отправлен клиенту');
        setTimeout(() => setSendMsg(''), 3000);
        onAction('refresh');
      } else {
        setSendMsg('❌ ' + (data.error || 'Ошибка отправки'));
      }
    } catch {
      setSendMsg('❌ Ошибка сети');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendReply();
    }
  };

  if (!ticket) {
    return (
      <div className="user-panel user-panel-empty">
        <div className="empty-state">
          <div className="empty-icon"><MessageSquare size={24} /></div>
          <div className="empty-title">Выберите тикет</div>
          <div className="empty-text">Нажмите на тикет слева для просмотра деталей и переписки</div>
        </div>
      </div>
    );
  }

  const status   = TICKET_STATUSES[ticket.status] || TICKET_STATUSES.open;
  const isSusp   = ticket.status === 'suspicious';
  const history  = ticket.history || ticket.last_messages || [];
  const user     = userData?.user;
  const uuid     = user?.uuid || '';
  const isDisabled = (user?.status || '').toUpperCase() === 'DISABLED';
  const traffic  = user?.userTraffic;

  return (
    <div className="user-panel">
      {/* Ticket header */}
      <div className="up-header">
        <div className="up-user-info">
          <div className={`user-avatar ${isSusp ? 'suspicious' : ''}`} style={{ width: 40, height: 40 }}>
            {isSusp ? '🚨' : (ticket.client_name || 'U')[0].toUpperCase()}
          </div>
          <div>
            <div className="up-name">
              {ticket.client_name || `ID ${ticket.client_id}`}
              {isSusp && <span className="badge badge-danger" style={{ marginLeft: 6, fontSize: '0.62rem' }}>ВНЕ СИСТЕМЫ</span>}
            </div>
            <div className="up-meta">
              @{ticket.client_username || '—'} · ID: {ticket.client_id}
            </div>
          </div>
        </div>
        <span className={`badge badge-${status.color}`}>{status.emoji} {status.label}</span>
      </div>

      {/* Tabs */}
      <div className="up-tabs">
        <button className={`up-tab ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
          💬 Переписка <span className="filter-count">{history.length}</span>
        </button>
        <button className={`up-tab ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => setActiveTab('profile')}>
          👤 Профиль
        </button>
        {!isSusp && user && (
          <button className={`up-tab ${activeTab === 'actions' ? 'active' : ''}`} onClick={() => setActiveTab('actions')}>
            ⚡ Действия
          </button>
        )}
      </div>

      {/* ── TAB: CHAT ── */}
      {activeTab === 'chat' && (
        <div className="up-chat">
          <div className="up-messages">
            {isSusp && (
              <div className="alert alert-error" style={{ margin: '0 0 10px', fontSize: '0.82rem' }}>
                <AlertTriangle size={14} />
                Пользователь не найден в Remnawave — возможен мошенник
              </div>
            )}
            {ticket.reason && !isSusp && (
              <div className="alert alert-info" style={{ margin: '0 0 10px', fontSize: '0.82rem' }}>
                <strong>Причина:</strong> {ticket.reason}
              </div>
            )}
            {history.length === 0 ? (
              <div className="empty-state" style={{ padding: '30px 0' }}>
                <div className="empty-text">Переписки нет</div>
              </div>
            ) : (
              history.map((msg, i) => <ChatBubble key={i} msg={msg} />)
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Reply input */}
          {ticket.status !== 'closed' && (
            <div className="up-reply">
              {sendMsg && <div className="up-send-msg">{sendMsg}</div>}
              <div className="up-reply-row">
                <textarea
                  className="up-reply-input"
                  placeholder="Ответить клиенту… (Enter — отправить, Shift+Enter — перенос строки)"
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                />
                <button
                  className="btn btn-primary up-reply-btn"
                  onClick={sendReply}
                  disabled={sending || !replyText.trim()}
                >
                  {sending ? <div className="loading-spinner" style={{ width: 16, height: 16 }} /> : <Send size={16} />}
                </button>
              </div>
            </div>
          )}

          {/* Ticket actions row */}
          <div className="up-ticket-actions">
            {ticket.status !== 'closed' && (
              <button className="btn btn-secondary btn-sm" onClick={() => onAction('close-ticket', { ticketId: ticket.id })}>
                <CheckCircle size={13} /> Закрыть тикет
              </button>
            )}
            {(isSusp || ticket.status === 'closed') && (
              <button className="btn btn-danger btn-sm" onClick={() => onAction('remove-ticket', { ticketId: ticket.id })}>
                <X size={13} /> Убрать
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: PROFILE ── */}
      {activeTab === 'profile' && (
        <div className="up-profile">
          {loadingUser ? (
            <div className="empty-state" style={{ padding: 40 }}>
              <div className="loading-spinner" />
              <div style={{ marginTop: 10 }}>Загрузка данных...</div>
            </div>
          ) : !user ? (
            <div className="empty-state" style={{ padding: 40 }}>
              <div className="empty-icon"><User size={22} /></div>
              <div className="empty-title">Данные не найдены</div>
              <div className="empty-text">Пользователь не зарегистрирован в Remnawave</div>
            </div>
          ) : (
            <div style={{ padding: '12px 16px', overflowY: 'auto', flex: 1 }}>
              {/* Status badge */}
              <div className="profile-status-row">
                {isDisabled
                  ? <span className="badge badge-danger"><WifiOff size={11} /> Заблокирован</span>
                  : <span className="badge badge-success"><Wifi size={11} /> Активен</span>
                }
                {userData?.subscription?.status && (
                  <span className="badge badge-info">{userData.subscription.status}</span>
                )}
              </div>

              <div className="card" style={{ marginBottom: 10 }}>
                <div className="card-header"><span className="card-title"><User size={13} style={{ marginRight: 4 }} />Идентификация</span></div>
                <div className="data-row"><span className="data-label">UUID</span><span className="data-value"><code>{user.uuid || '—'}</code></span></div>
                <div className="data-row"><span className="data-label">Username</span><span className="data-value">{user.username ? `@${user.username}` : '—'}</span></div>
                <div className="data-row"><span className="data-label">TG ID</span><span className="data-value">{ticket.client_id}</span></div>
              </div>

              <div className="card" style={{ marginBottom: 10 }}>
                <div className="card-header"><span className="card-title"><Calendar size={13} style={{ marginRight: 4 }} />Подписка</span></div>
                <div className="data-row"><span className="data-label">Истекает</span><span className="data-value">{formatDate(user.expireAt)}</span></div>
                {userData?.subscription && (
                  <div className="data-row"><span className="data-label">Тариф</span><span className="data-value">{userData.subscription.planName || userData.subscription.status || '—'}</span></div>
                )}
              </div>

              {traffic && (
                <div className="card" style={{ marginBottom: 10 }}>
                  <div className="card-header"><span className="card-title"><BarChart3 size={13} style={{ marginRight: 4 }} />Трафик</span></div>
                  <TrafficBar used={traffic.usedTrafficBytes || 0} limit={user.trafficLimitBytes} />
                </div>
              )}

              {userData?.balance !== undefined && (
                <div className="card" style={{ marginBottom: 10 }}>
                  <div className="card-header"><span className="card-title">💰 Баланс (Bedolaga)</span></div>
                  <div className="data-row"><span className="data-label">Баланс</span><span className="data-value" style={{ color: 'var(--accent)', fontWeight: 700 }}>{userData.balance} ₽</span></div>
                  {userData.bedolaga_id && <div className="data-row"><span className="data-label">ID в Bedolaga</span><span className="data-value"><code>{userData.bedolaga_id}</code></span></div>}
                </div>
              )}

              {userData?.devices && userData.devices.length > 0 && (
                <div className="card">
                  <div className="card-header"><span className="card-title"><Shield size={13} style={{ marginRight: 4 }} />Устройства ({userData.devices.length})</span></div>
                  {userData.devices.map((d, i) => (
                    <div key={i} className="device-block" style={{ marginBottom: 6 }}>
                      <div className="device-title">{d.name || `Устройство ${i + 1}`}</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{d.hwid || d.id || '—'}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── TAB: ACTIONS ── */}
      {activeTab === 'actions' && user && (
        <div className="up-actions-tab">
          <div style={{ padding: '14px 16px' }}>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
              Действия применяются к аккаунту пользователя в Remnawave немедленно.
            </p>

            <div className="action-block">
              <div className="action-block-title">🔄 Управление подпиской</div>
              <button className="btn btn-secondary" style={{ width: '100%', marginBottom: 8 }}
                onClick={() => onAction('reset-traffic', { userUuid: uuid })}>
                <RotateCcw size={14} /> Сбросить трафик
              </button>
              <button className="btn btn-secondary" style={{ width: '100%' }}
                onClick={() => onAction('revoke-subscription', { userUuid: uuid })}>
                <RefreshCw size={14} /> Перевыпустить подписку
              </button>
            </div>

            <div className="action-block">
              <div className="action-block-title">🖥️ HWID устройства</div>
              <button className="btn btn-danger" style={{ width: '100%' }}
                onClick={() => onAction('hwid-delete-all', { userUuid: uuid })}>
                <Trash2 size={14} /> Удалить все HWID
              </button>
            </div>

            <div className="action-block">
              <div className="action-block-title">🔒 Блокировка</div>
              {isDisabled ? (
                <button className="btn btn-secondary" style={{ width: '100%' }}
                  onClick={() => onAction('enable-user', { userUuid: uuid })}>
                  <Unlock size={14} /> Разблокировать пользователя
                </button>
              ) : (
                <button className="btn btn-danger" style={{ width: '100%' }}
                  onClick={() => onAction('disable-user', { userUuid: uuid })}>
                  <Lock size={14} /> Заблокировать пользователя
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────
export default function TicketsPage({ settings, initData }) {
  const [tickets, setTickets]           = useState([]);
  const [loading, setLoading]           = useState(true);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [filter, setFilter]             = useState('all');
  const [confirm, setConfirm]           = useState({ open: false });
  const [actionMsg, setActionMsg]       = useState('');
  // Cache: client_id → userData
  const [userCache, setUserCache]       = useState({});
  const [loadingUser, setLoadingUser]   = useState(false);

  const headers = {};
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  // ── Fetch active tickets ──────────────────────────────────────────────
  const fetchTickets = useCallback(async () => {
    try {
      const r    = await fetch(`${API}/api/tickets/active`, { headers });
      const data = await r.json();
      const list = data.tickets || [];
      setTickets(list);

      // Keep selectedTicket in sync
      setSelectedTicket(prev => {
        if (!prev) return null;
        const updated = list.find(t => t.id === prev.id);
        return updated || prev;
      });
    } catch (e) {
      console.error('Tickets fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [initData]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchTickets();
    const interval = setInterval(fetchTickets, 10000);
    return () => clearInterval(interval);
  }, [fetchTickets]);

  // ── Load user data when ticket selected ──────────────────────────────
  useEffect(() => {
    if (!selectedTicket) return;
    const cid = selectedTicket.client_id;

    // Already have from ticket.user_data or cache
    if (selectedTicket.user_data?.user) {
      setUserCache(prev => ({ ...prev, [cid]: selectedTicket.user_data }));
      return;
    }
    if (userCache[cid]) return;

    // Fetch from lookup
    setLoadingUser(true);
    fetch(`${API}/api/lookup?tg_id=${cid}`, { headers })
      .then(r => r.json())
      .then(data => {
        if (data.user) {
          setUserCache(prev => ({ ...prev, [cid]: data }));
        }
      })
      .catch(e => console.error('User lookup error:', e))
      .finally(() => setLoadingUser(false));
  }, [selectedTicket?.id, selectedTicket?.client_id]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Ticket actions handler ────────────────────────────────────────────
  const handleAction = (action, data) => {
    if (action === 'refresh') {
      fetchTickets();
      return;
    }

    const confirmMeta = {
      'close-ticket':       { title: 'Закрытие тикета',      message: 'Закрыть этот тикет? Пользователь получит уведомление.' },
      'remove-ticket':      { title: 'Удаление тикета',       message: 'Полностью удалить тикет из списка?',                    danger: true },
      'reset-traffic':      { title: 'Сброс трафика',         message: 'Сбросить использованный трафик пользователя?' },
      'revoke-subscription':{ title: 'Перевыпуск подписки',   message: 'Перевыпустить ключ подписки пользователя?' },
      'hwid-delete-all':    { title: 'Удаление HWID',         message: 'Удалить ВСЕ привязанные устройства?',                   danger: true },
      'enable-user':        { title: 'Разблокировка',         message: 'Разблокировать пользователя?' },
      'disable-user':       { title: 'Блокировка',            message: 'Заблокировать пользователя?',                           danger: true },
    };
    const meta = confirmMeta[action] || { title: action, message: 'Выполнить действие?' };
    setConfirm({ open: true, action, data, ...meta });
  };

  const executeAction = async () => {
    const { action, data } = confirm;
    setConfirm({ open: false });
    setActionMsg('');

    try {
      if (action === 'close-ticket') {
        await fetch(`${API}/api/tickets/${data.ticketId}/close`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers } });
        setActionMsg('✅ Тикет закрыт');
        setSelectedTicket(null);
        fetchTickets();
      } else if (action === 'remove-ticket') {
        await fetch(`${API}/api/tickets/${data.ticketId}/remove`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers } });
        setActionMsg('🗑️ Тикет удалён');
        setSelectedTicket(null);
        fetchTickets();
      } else {
        const r      = await fetch(`${API}/api/actions/${action}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers },
          body: JSON.stringify(data)
        });
        const result = await r.json();
        setActionMsg(result.message || (result.ok ? '✅ Готово' : '❌ Ошибка'));
        if (result.ok) {
          // Invalidate cache for this user so profile refreshes
          if (data.userUuid && selectedTicket) {
            setUserCache(prev => {
              const next = { ...prev };
              delete next[selectedTicket.client_id];
              return next;
            });
          }
          fetchTickets();
        }
      }
    } catch {
      setActionMsg('❌ Ошибка сети');
    }
  };

  // ── Filter ────────────────────────────────────────────────────────────
  const counts = {
    all:        tickets.length,
    escalated:  tickets.filter(t => t.status === 'escalated').length,
    suspicious: tickets.filter(t => t.status === 'suspicious').length,
  };

  const filteredTickets = tickets.filter(t => {
    if (filter === 'escalated')  return t.status === 'escalated';
    if (filter === 'suspicious') return t.status === 'suspicious';
    return true;
  });

  const currentUserData = selectedTicket
    ? (userCache[selectedTicket.client_id] || selectedTicket.user_data || null)
    : null;

  if (loading) {
    return (
      <div className="empty-state" data-testid="tickets-loading">
        <div className="loading-spinner" />
        <div style={{ marginTop: 12 }}>Загрузка тикетов...</div>
      </div>
    );
  }

  return (
    <div className="tickets-split" data-testid="tickets-page">
      {/* ── LEFT PANEL — ticket list ── */}
      <div className="tickets-split-left">
        {/* Filter bar */}
        <div className="split-filter-bar">
          <button className={`filter-tab ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
            Все <span className="filter-count">{counts.all}</span>
          </button>
          <button className={`filter-tab ${filter === 'escalated' ? 'active' : ''}`} onClick={() => setFilter('escalated')}>
            🔥 <span className="filter-count">{counts.escalated}</span>
          </button>
          <button className={`filter-tab suspicious ${filter === 'suspicious' ? 'active' : ''}`} onClick={() => setFilter('suspicious')}>
            🚨 <span className="filter-count">{counts.suspicious}</span>
          </button>
        </div>

        {actionMsg && (
          <div className="alert alert-info" style={{ margin: '8px 12px 0', fontSize: '0.82rem' }}>
            {actionMsg}
          </div>
        )}

        {filteredTickets.length === 0 ? (
          <div className="empty-state" style={{ padding: '40px 16px' }}>
            <div className="empty-icon"><Flame size={22} /></div>
            <div className="empty-title">Нет тикетов</div>
            <div className="empty-text">
              {filter === 'suspicious' ? 'Нет подозрительных'
                : filter === 'escalated' ? 'Нет эскалированных'
                : 'Все вопросы решены ИИ'}
            </div>
          </div>
        ) : (
          <div className="split-ticket-list">
            {filteredTickets.map(ticket => {
              const status   = TICKET_STATUSES[ticket.status] || TICKET_STATUSES.open;
              const isSusp   = ticket.status === 'suspicious';
              const isActive = selectedTicket?.id === ticket.id;

              return (
                <div
                  key={ticket.id}
                  className={`split-ticket-item ${isActive ? 'active' : ''} ${isSusp ? 'suspicious' : ''}`}
                  onClick={() => setSelectedTicket(isActive ? null : ticket)}
                  data-testid={`ticket-${ticket.id}`}
                >
                  <div className={`user-avatar split-ticket-avatar ${isSusp ? 'suspicious' : ''}`}>
                    {isSusp ? '🚨' : (ticket.client_name || 'U')[0].toUpperCase()}
                  </div>
                  <div className="split-ticket-info">
                    <div className="split-ticket-name">
                      {ticket.client_name || `ID ${ticket.client_id}`}
                    </div>
                    <div className="split-ticket-meta">
                      @{ticket.client_username || '—'} · {formatDateShort(ticket.escalated_at || ticket.created_at)}
                    </div>
                    <div style={{ marginTop: 4 }}>
                      <span className={`badge badge-${status.color}`} style={{ fontSize: '0.62rem' }}>
                        {status.emoji} {status.label}
                      </span>
                    </div>
                  </div>
                  <ChevronRight size={14} className="split-ticket-arrow" />
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL — detail ── */}
      <div className="tickets-split-right">
        <UserPanel
          ticket={selectedTicket}
          userData={currentUserData}
          loadingUser={loadingUser}
          onAction={handleAction}
          initData={initData}
        />
      </div>

      <ConfirmModal
        isOpen={confirm.open}
        title={confirm.title}
        message={confirm.message}
        danger={confirm.danger}
        onConfirm={executeAction}
        onCancel={() => setConfirm({ open: false })}
      />
    </div>
  );
}

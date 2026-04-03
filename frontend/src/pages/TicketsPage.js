import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Flame, User, BarChart3, Calendar, Link2, Smartphone, RotateCcw, RefreshCw, Trash2, Lock, Unlock, AlertTriangle, Clock, Send, X, Image, CheckCircle, Bot, UserCheck, ChevronDown, ChevronUp, Search, Wallet, Zap } from 'lucide-react';
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
    const d = new Date(str.replace('Z', '+00:00'));
    if (isNaN(d.getTime())) return str;
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return str; }
}

function timeAgo(str) {
  if (!str) return '';
  try {
    const d = new Date(str.replace('Z', '+00:00'));
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'только что';
    if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
    return formatDate(str);
  } catch { return ''; }
}

const STATUS_CONFIG = {
  open: { emoji: '💬', label: 'Открыт', color: '#3b82f6' },
  escalated: { emoji: '🔥', label: 'Эскалация', color: '#f59e0b' },
  suspicious: { emoji: '🚨', label: 'Подозрительный', color: '#ef4444' },
  closed: { emoji: '✅', label: 'Закрыт', color: '#22c55e' },
};

// Bubble сообщения
function ChatBubble({ msg }) {
  const isUser = msg.role === 'user';
  const isAI = msg.role === 'assistant' || msg.role === 'ai';
  const isManager = msg.role === 'manager';
  
  const roleLabel = isUser ? '👤 Клиент' : isAI ? '🤖 AI' : `👨‍💼 ${msg.name || 'Менеджер'}`;
  const bubbleStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: isUser ? 'flex-start' : 'flex-end',
    marginBottom: 8,
  };
  const msgStyle = {
    maxWidth: '80%',
    padding: '8px 12px',
    borderRadius: isUser ? '4px 16px 16px 16px' : '16px 4px 16px 16px',
    background: isUser ? 'var(--bg-secondary, #1e293b)' : isAI ? 'var(--bg-tertiary, #1a2744)' : 'var(--primary-dark, #1d4ed8)',
    color: 'var(--text-primary, #f1f5f9)',
    fontSize: '0.88rem',
    lineHeight: 1.5,
    wordBreak: 'break-word',
  };
  
  return (
    <div style={bubbleStyle}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)', marginBottom: 2, padding: '0 4px' }}>
        {roleLabel} · {timeAgo(msg.timestamp)}
      </div>
      <div style={msgStyle}>{msg.content}</div>
    </div>
  );
}

// Карточка данных пользователя
function UserDataCard({ userData, onAction }) {
  const [expanded, setExpanded] = useState(false);
  const [confirm, setConfirm] = useState({ open: false });
  
  if (!userData) return null;
  
  const user = userData.user || {};
  const subscription = userData.subscription || {};
  const subUser = subscription.user || {};
  const devices = userData.hwid_devices || [];
  const status = (user.status || '').toUpperCase();
  const isDisabled = ['DISABLED', 'INACTIVE', 'BANNED'].includes(status);
  const uuid = user.uuid || '';
  
  const traffic = user.userTraffic || {};
  const usedBytes = traffic.usedTrafficBytes || 0;
  const limitBytes = user.trafficLimitBytes || 0;
  const trafficPct = limitBytes > 0 ? Math.min(100, (usedBytes / limitBytes) * 100) : 0;
  
  const doAction = async (action, label) => {
    setConfirm({ open: false });
    try {
      const r = await fetch(`${API}/api/actions/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userUuid: uuid })
      });
      const d = await r.json();
      if (onAction) onAction(d.ok ? `✅ ${label} выполнено` : `❌ ${d.message || 'Ошибка'}`);
    } catch { if (onAction) onAction('❌ Ошибка сети'); }
  };
  
  const askConfirm = (action, title, message, danger = false) => {
    setConfirm({ open: true, action, title, message, danger });
  };
  
  return (
    <div className="card" style={{ marginTop: 12 }}>
      <div 
        className="card-header" 
        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="card-title">📋 Данные пользователя Remnawave</span>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>
      
      {expanded && (
        <div className="animate-fade">
          {/* UUID + статус */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: 8, background: isDisabled ? '#7f1d1d' : '#14532d', color: isDisabled ? '#fca5a5' : '#86efac' }}>
              {status || 'UNKNOWN'}
            </span>
            {uuid && <code style={{ fontSize: '0.7rem', color: 'var(--text-muted)', alignSelf: 'center' }}>{uuid.slice(0, 8)}...</code>}
          </div>
          
          {/* Трафик прогресс-бар */}
          {limitBytes > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: 3, color: 'var(--text-secondary)' }}>
                <span>Трафик: {formatBytes(usedBytes)}</span>
                <span>/ {formatBytes(limitBytes)} ({trafficPct.toFixed(0)}%)</span>
              </div>
              <div style={{ height: 4, background: 'var(--bg-secondary)', borderRadius: 2 }}>
                <div style={{ height: '100%', width: `${trafficPct}%`, background: trafficPct > 80 ? '#ef4444' : trafficPct > 60 ? '#f59e0b' : '#22c55e', borderRadius: 2, transition: 'width 0.3s' }} />
              </div>
            </div>
          )}
          
          <div className="data-row"><span className="data-label">Истекает</span><span className="data-value">{formatDate(user.expireAt)}</span></div>
          <div className="data-row"><span className="data-label">Username</span><span className="data-value">{user.username ? `@${user.username}` : '—'}</span></div>
          <div className="data-row"><span className="data-label">Устройств HWID</span><span className="data-value">{devices.length}</span></div>
          
          {/* Кнопки действий */}
          {uuid && (
            <div className="actions-bar" style={{ marginTop: 12, flexWrap: 'wrap' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => askConfirm('reset-traffic', 'Сброс трафика', 'Сбросить трафик пользователя?')}>
                <RotateCcw size={13} /> Сброс трафика
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => askConfirm('revoke-subscription', 'Перевыпуск', 'Перевыпустить подписку?')}>
                <RefreshCw size={13} /> Перевыпуск
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => askConfirm('hwid-delete-all', 'Удалить HWID', 'Удалить ВСЕ устройства?', true)}>
                <Trash2 size={13} /> Очистить HWID
              </button>
              {isDisabled ? (
                <button className="btn btn-secondary btn-sm" onClick={() => askConfirm('enable-user', 'Разблокировка', 'Разблокировать пользователя?')}>
                  <Unlock size={13} /> Разблокировать
                </button>
              ) : (
                <button className="btn btn-danger btn-sm" onClick={() => askConfirm('disable-user', 'Блокировка', 'Заблокировать пользователя?', true)}>
                  <Lock size={13} /> Заблокировать
                </button>
              )}
            </div>
          )}
        </div>
      )}
      
      <ConfirmModal
        isOpen={confirm.open}
        title={confirm.title}
        message={confirm.message}
        danger={confirm.danger}
        onConfirm={() => doAction(confirm.action, confirm.title)}
        onCancel={() => setConfirm({ open: false })}
      />
    </div>
  );
}

// Основной компонент страницы тикетов
export default function TicketsPage({ settings, initData }) {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const [filter, setFilter] = useState('all');
  const [actionMsg, setActionMsg] = useState('');
  const [lookupData, setLookupData] = useState({}); // cache user data by client_id
  const [loadingLookup, setLoadingLookup] = useState(false);
  const messagesEndRef = useRef(null);
  const replyInputRef = useRef(null);

  const headers = { 'Content-Type': 'application/json', ...(initData ? { 'X-Telegram-Init-Data': initData } : {}) };

  const fetchTickets = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/tickets/active`, { headers: initData ? { 'X-Telegram-Init-Data': initData } : {} });
      const data = await r.json();
      setTickets(data.tickets || []);
    } catch (e) { console.error('Tickets fetch error:', e); }
    finally { setLoading(false); }
  }, [initData]);

  useEffect(() => {
    fetchTickets();
    const iv = setInterval(fetchTickets, 10000);
    return () => clearInterval(iv);
  }, [fetchTickets]);

  // Подгрузка данных пользователя из Remnawave при выборе тикета
  const loadUserData = useCallback(async (clientId) => {
    if (lookupData[clientId]) return;
    setLoadingLookup(true);
    try {
      const r = await fetch(`${API}/api/lookup`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: String(clientId) })
      });
      const d = await r.json();
      if (d.ok) {
        setLookupData(prev => ({ ...prev, [clientId]: d }));
      }
    } catch (e) { console.error('Lookup error:', e); }
    finally { setLoadingLookup(false); }
  }, [lookupData, headers]);

  const selectedTicket = tickets.find(t => t.id === selectedId);

  useEffect(() => {
    if (selectedTicket) {
      loadUserData(selectedTicket.client_id);
      // Скролл к последнему сообщению
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  }, [selectedId, selectedTicket?.history?.length]);

  const sendReply = async () => {
    if (!replyText.trim() || !selectedTicket) return;
    setSending(true);
    try {
      const r = await fetch(`${API}/api/tickets/${selectedTicket.id}/reply`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: replyText.trim(), manager_name: 'Менеджер' })
      });
      const d = await r.json();
      if (d.ok) {
        setReplyText('');
        setActionMsg('✅ Ответ отправлен клиенту в Telegram');
        fetchTickets();
        setTimeout(() => setActionMsg(''), 3000);
      } else {
        setActionMsg(`❌ ${d.error || 'Ошибка отправки'}`);
      }
    } catch { setActionMsg('❌ Ошибка сети'); }
    finally { setSending(false); }
  };

  const closeTicketAction = async (ticketId) => {
    try {
      await fetch(`${API}/api/tickets/${ticketId}/close`, { method: 'POST', headers });
      fetchTickets();
      setSelectedId(null);
      setActionMsg('✅ Тикет закрыт');
      setTimeout(() => setActionMsg(''), 3000);
    } catch (e) { console.error(e); }
  };

  const removeTicketAction = async (ticketId) => {
    try {
      await fetch(`${API}/api/tickets/${ticketId}/remove`, { method: 'POST', headers });
      fetchTickets();
      setSelectedId(null);
    } catch (e) { console.error(e); }
  };

  const filteredTickets = tickets.filter(t => {
    if (filter === 'escalated') return t.status === 'escalated';
    if (filter === 'suspicious') return t.status === 'suspicious';
    return true;
  });

  const counts = {
    all: tickets.length,
    escalated: tickets.filter(t => t.status === 'escalated').length,
    suspicious: tickets.filter(t => t.status === 'suspicious').length,
  };

  if (loading) return (
    <div className="empty-state">
      <div className="loading-spinner" />
      <div style={{ marginTop: 12 }}>Загрузка тикетов...</div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Фильтры */}
      <div className="card" style={{ marginBottom: 8, flexShrink: 0 }}>
        <div className="card-header" style={{ paddingBottom: 8 }}>
          <span className="card-title">Активные тикеты</span>
          <button className="btn btn-secondary btn-sm" onClick={fetchTickets} style={{ marginLeft: 'auto' }}>
            <RefreshCw size={13} />
          </button>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[['all', 'Все'], ['escalated', '🔥 Эскалация'], ['suspicious', '🚨 Подозрительные']].map(([f, label]) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '4px 10px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: '0.8rem',
                background: filter === f ? 'var(--primary)' : 'var(--bg-secondary)',
                color: filter === f ? '#fff' : 'var(--text-secondary)',
                fontWeight: filter === f ? 600 : 400,
              }}
            >
              {label} <span style={{ opacity: 0.7 }}>({counts[f]})</span>
            </button>
          ))}
        </div>
      </div>

      {actionMsg && (
        <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bg-secondary)', marginBottom: 8, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
          {actionMsg}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Список тикетов (левая панель) */}
        <div style={{ width: selectedTicket ? '35%' : '100%', overflowY: 'auto', flexShrink: 0 }}>
          {filteredTickets.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon"><Flame size={24} /></div>
              <div className="empty-title">Нет тикетов</div>
              <div className="empty-text">Все вопросы решены AI</div>
            </div>
          ) : filteredTickets.map(ticket => {
            const cfg = STATUS_CONFIG[ticket.status] || STATUS_CONFIG.open;
            const isSelected = ticket.id === selectedId;
            const history = ticket.history || ticket.last_messages || [];
            const lastMsg = history[history.length - 1];
            
            return (
              <div
                key={ticket.id}
                onClick={() => setSelectedId(isSelected ? null : ticket.id)}
                style={{
                  padding: '10px 12px', marginBottom: 6, borderRadius: 10, cursor: 'pointer',
                  background: isSelected ? 'var(--primary-bg, rgba(59,130,246,0.15))' : 'var(--bg-secondary)',
                  borderLeft: `3px solid ${cfg.color}`,
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>
                      {ticket.client_name || `ID ${ticket.client_id}`}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: 1 }}>
                      @{ticket.client_username || '—'} · {ticket.client_id}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 8 }}>
                    <div style={{ fontSize: '0.72rem', color: cfg.color, fontWeight: 600 }}>{cfg.emoji} {cfg.label}</div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 2 }}>
                      {timeAgo(ticket.escalated_at || ticket.created_at)}
                    </div>
                  </div>
                </div>
                {lastMsg && (
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {lastMsg.role === 'manager' ? '👨‍💼' : lastMsg.role === 'assistant' ? '🤖' : '👤'} {lastMsg.content}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Панель тикета (правая) */}
        {selectedTicket && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg-secondary)', borderRadius: 12, overflow: 'hidden' }}>
            {/* Заголовок */}
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', flexShrink: 0, background: 'var(--bg-tertiary, var(--bg-secondary))' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                    {selectedTicket.client_name || `User ${selectedTicket.client_id}`}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    @{selectedTicket.client_username || '—'} · ID: {selectedTicket.client_id}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  {selectedTicket.status !== 'closed' && (
                    <button className="btn btn-secondary btn-sm" onClick={() => closeTicketAction(selectedTicket.id)}>
                      <CheckCircle size={13} /> Закрыть
                    </button>
                  )}
                  {(selectedTicket.status === 'suspicious' || selectedTicket.status === 'closed') && (
                    <button className="btn btn-danger btn-sm" onClick={() => removeTicketAction(selectedTicket.id)}>
                      <X size={13} /> Убрать
                    </button>
                  )}
                  <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }} onClick={() => setSelectedId(null)}>
                    <X size={18} />
                  </button>
                </div>
              </div>
              
              {/* Причина */}
              {selectedTicket.reason && (
                <div style={{ marginTop: 6, fontSize: '0.76rem', color: 'var(--text-secondary)', padding: '4px 8px', background: 'rgba(245,158,11,0.1)', borderRadius: 6 }}>
                  ⚡ {selectedTicket.reason}
                </div>
              )}
              {selectedTicket.status === 'suspicious' && (
                <div style={{ marginTop: 6, fontSize: '0.76rem', color: '#ef4444', padding: '4px 8px', background: 'rgba(239,68,68,0.1)', borderRadius: 6 }}>
                  🚨 Пользователь НЕ НАЙДЕН в Remnawave — возможный мошенник
                </div>
              )}
            </div>

            {/* Переписка */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
              {(selectedTicket.history || selectedTicket.last_messages || []).length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 20 }}>
                  Нет сообщений
                </div>
              ) : (
                (selectedTicket.history || selectedTicket.last_messages || []).map((msg, i) => (
                  <ChatBubble key={i} msg={msg} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Данные пользователя */}
            {lookupData[selectedTicket.client_id] && (
              <div style={{ padding: '0 14px', flexShrink: 0 }}>
                <UserDataCard
                  userData={lookupData[selectedTicket.client_id]}
                  onAction={(msg) => { setActionMsg(msg); setTimeout(() => setActionMsg(''), 4000); }}
                />
              </div>
            )}
            {loadingLookup && !lookupData[selectedTicket.client_id] && (
              <div style={{ padding: '8px 14px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                🔍 Загружаем данные из Remnawave...
              </div>
            )}

            {/* Поле ответа */}
            <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <textarea
                  ref={replyInputRef}
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply(); } }}
                  placeholder="Написать ответ... (Enter — отправить, Shift+Enter — новая строка)"
                  rows={2}
                  style={{
                    flex: 1, background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 8,
                    color: 'var(--text-primary)', padding: '8px 12px', fontSize: '0.88rem', resize: 'none', outline: 'none',
                  }}
                />
                <button
                  className="btn btn-primary"
                  onClick={sendReply}
                  disabled={sending || !replyText.trim()}
                  style={{ alignSelf: 'flex-end', padding: '8px 16px' }}
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

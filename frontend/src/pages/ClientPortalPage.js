/**
 * ClientPortalPage — клиентский портал самообслуживания.
 *
 * Работает независимо от бота: через браузер по magic-link токену
 * или как Telegram Mini App (через initData).
 *
 * Три вкладки:
 *   💬 Чат     — переписка с AI и менеджером
 *   👤 Профиль — подписка, трафик, баланс
 *   📋 История — все предыдущие обращения
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Send, RefreshCw, MessageSquare, History,
  AlertCircle, ChevronRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

// ──────────────────────────────────────────────
//  Утилиты
// ──────────────────────────────────────────────

function formatBytes(b) {
  let n = Number(b) || 0;
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(2)} ${units[i]}`;
}

function formatDate(str) {
  if (!str) return '—';
  try {
    const d = new Date(str.replace('Z', '+00:00'));
    if (isNaN(d.getTime())) return str;
    return d.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return str; }
}

function timeAgo(str) {
  if (!str) return '';
  try {
    const diff = (Date.now() - new Date(str.replace('Z', '+00:00')).getTime()) / 1000;
    if (diff < 60) return 'только что';
    if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
    return formatDate(str);
  } catch { return ''; }
}

const STATUS_COLORS = {
  open: '#3b82f6',
  escalated: '#f59e0b',
  suspicious: '#ef4444',
  closed: '#22c55e',
};

const STATUS_LABELS = {
  open: '💬 Открыт',
  escalated: '🔥 Ожидает менеджера',
  suspicious: '🚨 На проверке',
  closed: '✅ Закрыт',
};

// ──────────────────────────────────────────────
//  Компоненты
// ──────────────────────────────────────────────

function ChatBubble({ msg }) {
  const isUser    = msg.role === 'user';
  const isAI      = msg.role === 'assistant' || msg.role === 'ai';
  const isManager = msg.role === 'manager';

  const label  = isUser ? '👤 Вы' : isAI ? '🤖 Ассистент' : `👨‍💼 ${msg.name || 'Поддержка'}`;
  const align  = isUser ? 'flex-end' : 'flex-start';
  const bg     = isUser
    ? 'var(--primary, #3b82f6)'
    : isManager
      ? 'rgba(34,197,94,0.15)'
      : 'var(--bg-secondary, #1e293b)';
  const color  = isUser ? '#fff' : 'var(--text-primary)';
  const radius = isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px';
  const border = isManager ? '1px solid rgba(34,197,94,0.3)' : 'none';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: align, marginBottom: 10 }}>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 2, padding: '0 4px' }}>
        {label} · {timeAgo(msg.timestamp)}
      </div>
      <div style={{ maxWidth: '82%', padding: '8px 14px', borderRadius: radius, background: bg, color, border, fontSize: '0.88rem', lineHeight: 1.55, wordBreak: 'break-word' }}>
        {msg.content}
      </div>
    </div>
  );
}

function TrafficBar({ used, limit }) {
  if (!limit) return null;
  const pct = Math.min(100, (used / limit) * 100);
  const barColor = pct > 80 ? '#ef4444' : pct > 60 ? '#f59e0b' : '#22c55e';
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: 3, color: 'var(--text-secondary)' }}>
        <span>Трафик: {formatBytes(used)}</span>
        <span>/ {formatBytes(limit)} ({pct.toFixed(0)}%)</span>
      </div>
      <div style={{ height: 6, background: 'var(--bg-secondary)', borderRadius: 3 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
//  Главный компонент
// ──────────────────────────────────────────────

export default function ClientPortalPage({ initData, clientToken }) {
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [profile, setProfile]         = useState(null);
  const [activeTicket, setActiveTicket] = useState(null);
  const [tickets, setTickets]         = useState([]);
  const [tab, setTab]                 = useState('chat');
  const [message, setMessage]         = useState('');
  const [sending, setSending]         = useState(false);
  const [sendMsg, setSendMsg]         = useState('');
  const messagesEndRef                = useRef(null);

  // ── Заголовки запросов ──
  const buildHeaders = useCallback(() => {
    const h = { 'Content-Type': 'application/json' };
    if (initData)     h['X-Telegram-Init-Data'] = initData;
    if (clientToken)  h['X-Client-Token'] = clientToken;
    return h;
  }, [initData, clientToken]);

  const qs = clientToken ? `?token=${clientToken}` : '';

  // ── Загрузка данных ──
  const fetchAll = useCallback(async () => {
    try {
      const headers = buildHeaders();
      const [pRes, aRes, hRes] = await Promise.all([
        fetch(`${API}/api/client/profile${qs}`,         { headers }),
        fetch(`${API}/api/client/tickets/active${qs}`,  { headers }),
        fetch(`${API}/api/client/tickets${qs}`,         { headers }),
      ]);

      if (pRes.status === 401) { setError('unauthorized'); setLoading(false); return; }

      const [pData, aData, hData] = await Promise.all([pRes.json(), aRes.json(), hRes.json()]);

      setProfile(pData);
      setActiveTicket(aData.ticket || null);
      setTickets(hData.tickets || []);
    } catch {
      setError('network');
    } finally {
      setLoading(false);
    }
  }, [buildHeaders, qs]);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 15000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  // Скролл к последнему сообщению
  const histLen = (activeTicket?.history || []).length;
  useEffect(() => {
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 80);
  }, [histLen]);

  // ── Отправка сообщения ──
  const sendMessage = async () => {
    if (!message.trim() || sending) return;
    setSending(true);
    setSendMsg('');
    try {
      const r = await fetch(`${API}/api/client/tickets/message${qs}`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({ message: message.trim() }),
      });
      const d = await r.json();
      if (d.ok) {
        setMessage('');
        await fetchAll();
      } else {
        setSendMsg(`❌ ${d.error || 'Ошибка'}`);
      }
    } catch {
      setSendMsg('❌ Ошибка сети');
    } finally {
      setSending(false);
    }
  };

  // ── Состояния загрузки/ошибки ──
  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100dvh', gap: 12 }}>
      <div className="loading-spinner" />
      <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Загрузка...</span>
    </div>
  );

  if (error === 'unauthorized') return (
    <div style={{ padding: 32, textAlign: 'center' }}>
      <AlertCircle size={40} color="#ef4444" style={{ marginBottom: 12 }} />
      <h2 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>Требуется авторизация</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
        Откройте портал через бота или используйте ссылку из личного кабинета.
      </p>
    </div>
  );

  // ── Данные для рендера ──
  const rw       = profile?.remnawave || {};
  const rwUser   = rw.user || {};
  const devices  = rw.devices || [];
  const bedolaga = profile?.bedolaga || {};
  const traffic  = rwUser.userTraffic || {};
  const usedB    = traffic.usedTrafficBytes || 0;
  const limitB   = rwUser.trafficLimitBytes || 0;
  const status   = (rwUser.status || '').toUpperCase();
  const isActive = status === 'ACTIVE';
  const history  = activeTicket?.history || activeTicket?.last_messages || [];

  const tabStyle = (t) => ({
    flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer',
    fontSize: '0.82rem', fontWeight: tab === t ? 600 : 400,
    background: 'transparent',
    color: tab === t ? 'var(--primary, #3b82f6)' : 'var(--text-muted)',
    borderBottom: tab === t ? '2px solid var(--primary, #3b82f6)' : '2px solid transparent',
    transition: 'all 0.15s',
  });

  return (
    <div style={{ height: '100dvh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>

      {/* ── Шапка ── */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>🛡 Портал поддержки</div>
            {rwUser.username && (
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>@{rwUser.username}</div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {activeTicket && (
              <span style={{
                fontSize: '0.72rem', padding: '2px 8px', borderRadius: 12,
                background: `${STATUS_COLORS[activeTicket.status] || '#3b82f6'}22`,
                color: STATUS_COLORS[activeTicket.status] || '#3b82f6',
                border: `1px solid ${STATUS_COLORS[activeTicket.status] || '#3b82f6'}44`,
              }}>
                {STATUS_LABELS[activeTicket.status] || '💬 Открыт'}
              </span>
            )}
            <button onClick={fetchAll} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Табы ── */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <button style={tabStyle('chat')}    onClick={() => setTab('chat')}>    💬 Чат</button>
        <button style={tabStyle('profile')} onClick={() => setTab('profile')}> 👤 Профиль</button>
        <button style={tabStyle('history')} onClick={() => setTab('history')}> 📋 История</button>
      </div>

      {/* ── Контент ── */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

        {/* ────── ЧАТ ────── */}
        {tab === 'chat' && (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
              {history.length === 0 ? (
                <div style={{ textAlign: 'center', paddingTop: 48 }}>
                  <MessageSquare size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 600 }}>Напишите ваш вопрос</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: 6 }}>
                    AI-ассистент ответит мгновенно, если не сможет — подключит менеджера
                  </div>
                </div>
              ) : (
                history.map((msg, i) => <ChatBubble key={i} msg={msg} />)
              )}
              <div ref={messagesEndRef} />
            </div>

            {sendMsg && (
              <div style={{ padding: '4px 16px', fontSize: '0.78rem', color: '#ef4444' }}>
                {sendMsg}
              </div>
            )}

            <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <textarea
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
                  }}
                  placeholder="Написать сообщение... (Enter — отправить)"
                  rows={2}
                  style={{
                    flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                    borderRadius: 10, color: 'var(--text-primary)', padding: '8px 12px',
                    fontSize: '0.88rem', resize: 'none', outline: 'none', fontFamily: 'inherit',
                  }}
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !message.trim()}
                  style={{
                    alignSelf: 'flex-end', padding: '9px 16px', borderRadius: 10,
                    border: 'none', background: 'var(--primary, #3b82f6)', color: '#fff',
                    cursor: 'pointer', opacity: (sending || !message.trim()) ? 0.5 : 1,
                    transition: 'opacity 0.15s',
                  }}
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          </>
        )}

        {/* ────── ПРОФИЛЬ ────── */}
        {tab === 'profile' && (
          <div style={{ overflowY: 'auto', padding: '12px 16px' }}>

            {/* Статус подписки */}
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="card-header"><span className="card-title">📡 Подписка</span></div>

              {rw.not_found ? (
                <div style={{ color: '#ef4444', fontSize: '0.88rem', padding: '4px 0' }}>
                  ⚠️ Вы не найдены в системе. Обратитесь в поддержку — вкладка «Чат».
                </div>
              ) : (
                <>
                  <div style={{ marginBottom: 10 }}>
                    <span style={{
                      padding: '3px 12px', borderRadius: 12, fontSize: '0.78rem', fontWeight: 600,
                      background: isActive ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                      color: isActive ? '#22c55e' : '#ef4444',
                    }}>
                      {isActive ? '✅ Активна' : `❌ ${status || 'Нет данных'}`}
                    </span>
                  </div>

                  <TrafficBar used={usedB} limit={limitB} />

                  <div className="data-row">
                    <span className="data-label">Истекает</span>
                    <span className="data-value">{formatDate(rwUser.expireAt)}</span>
                  </div>
                  <div className="data-row">
                    <span className="data-label">Устройств (HWID)</span>
                    <span className="data-value">{devices.length}</span>
                  </div>
                  {rwUser.hwidDeviceLimit != null && (
                    <div className="data-row">
                      <span className="data-label">Лимит устройств</span>
                      <span className="data-value">{rwUser.hwidDeviceLimit}</span>
                    </div>
                  )}
                  {rwUser.username && (
                    <div className="data-row">
                      <span className="data-label">Username</span>
                      <span className="data-value">@{rwUser.username}</span>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Баланс */}
            {bedolaga && !bedolaga.error && bedolaga.balance !== undefined && (
              <div className="card" style={{ marginBottom: 12 }}>
                <div className="card-header"><span className="card-title">💰 Баланс</span></div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--primary, #3b82f6)', padding: '4px 0' }}>
                  {bedolaga.balance} ₽
                </div>
              </div>
            )}

            {/* Кнопка в чат */}
            <button
              className="btn btn-secondary"
              onClick={() => setTab('chat')}
              style={{ width: '100%' }}
            >
              <MessageSquare size={15} style={{ marginRight: 6 }} />
              Написать в поддержку
            </button>
          </div>
        )}

        {/* ────── ИСТОРИЯ ────── */}
        {tab === 'history' && (
          <div style={{ overflowY: 'auto', padding: '12px 16px' }}>
            {tickets.length === 0 ? (
              <div className="empty-state" style={{ paddingTop: 48 }}>
                <History size={28} style={{ color: 'var(--text-muted)' }} />
                <div className="empty-title" style={{ marginTop: 10 }}>Нет обращений</div>
                <div className="empty-text">История ваших обращений появится здесь</div>
              </div>
            ) : tickets.map(ticket => {
              const msgs = ticket.history || ticket.last_messages || [];
              const last = msgs[msgs.length - 1];
              return (
                <div
                  key={ticket.id}
                  style={{
                    padding: '10px 12px', marginBottom: 8, borderRadius: 10,
                    background: 'var(--bg-secondary)',
                    borderLeft: `3px solid ${STATUS_COLORS[ticket.status] || '#3b82f6'}`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.78rem', color: STATUS_COLORS[ticket.status], fontWeight: 600 }}>
                      {STATUS_LABELS[ticket.status] || '💬'}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      {formatDate(ticket.created_at)}
                    </span>
                  </div>
                  {ticket.reason && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                      {ticket.reason}
                    </div>
                  )}
                  {last && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {last.role === 'manager' ? '👨‍💼' : last.role === 'assistant' ? '🤖' : '👤'} {last.content}
                    </div>
                  )}
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    {msgs.length} сообщений
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

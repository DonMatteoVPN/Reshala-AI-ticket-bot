import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Send, User, Wifi, Calendar, Cpu, Wallet, History, MessageSquare, RefreshCw, AlertCircle, CheckCircle, Clock } from 'lucide-react';

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

const STATUS_COLORS = {
  open: '#3b82f6',
  escalated: '#f59e0b',
  suspicious: '#ef4444',
  closed: '#22c55e',
};

const STATUS_LABELS = {
  open: '💬 Открыт',
  escalated: '🔥 Ожидает менеджера',
  suspicious: '🚨 Проверка',
  closed: '✅ Закрыт',
};

function ChatBubble({ msg }) {
  const isUser = msg.role === 'user';
  const isAI = msg.role === 'assistant' || msg.role === 'ai';
  
  const roleLabel = isUser ? '👤 Вы' : isAI ? '🤖 Ассистент' : '👨‍💼 Поддержка';
  const bgColor = isUser ? 'var(--primary, #3b82f6)' : isAI ? 'var(--bg-tertiary, #1e293b)' : 'rgba(34,197,94,0.15)';
  const alignItems = isUser ? 'flex-end' : 'flex-start';
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems, marginBottom: 10 }}>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 2, padding: '0 4px' }}>
        {roleLabel} · {timeAgo(msg.timestamp)}
      </div>
      <div style={{
        maxWidth: '80%', padding: '8px 14px', borderRadius: isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
        background: bgColor, color: isUser ? '#fff' : 'var(--text-primary)',
        fontSize: '0.88rem', lineHeight: 1.5, wordBreak: 'break-word',
      }}>
        {msg.content}
      </div>
    </div>
  );
}

export default function ClientPortalPage({ initData, clientToken }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [profile, setProfile] = useState(null);
  const [activeTicket, setActiveTicket] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [tab, setTab] = useState('chat'); // chat | profile | history
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');
  const messagesEndRef = useRef(null);

  const getHeaders = useCallback(() => {
    const h = { 'Content-Type': 'application/json' };
    if (initData) h['X-Telegram-Init-Data'] = initData;
    if (clientToken) h['X-Client-Token'] = clientToken;
    return h;
  }, [initData, clientToken]);

  const getQueryToken = () => clientToken ? `?token=${clientToken}` : '';

  const fetchData = useCallback(async () => {
    try {
      const headers = getHeaders();
      const qs = getQueryToken();
      
      const [profileRes, ticketRes, ticketsRes] = await Promise.all([
        fetch(`${API}/api/client/profile${qs}`, { headers }),
        fetch(`${API}/api/client/tickets/active${qs}`, { headers }),
        fetch(`${API}/api/client/tickets${qs}`, { headers }),
      ]);
      
      if (profileRes.status === 401) { setError('not_authorized'); setLoading(false); return; }
      
      const profileData = await profileRes.json();
      const ticketData = await ticketRes.json();
      const ticketsData = await ticketsRes.json();
      
      setProfile(profileData);
      setActiveTicket(ticketData.ticket);
      setTickets(ticketsData.tickets || []);
    } catch (e) {
      setError('network');
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 15000);
    return () => clearInterval(iv);
  }, [fetchData]);

  useEffect(() => {
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  }, [activeTicket?.history?.length]);

  const sendMessage = async () => {
    if (!message.trim()) return;
    setSending(true);
    setSendError('');
    try {
      const r = await fetch(`${API}/api/client/tickets/message${getQueryToken()}`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ message: message.trim() })
      });
      const d = await r.json();
      if (d.ok) {
        setMessage('');
        await fetchData();
      } else {
        setSendError(d.error || 'Ошибка отправки');
      }
    } catch { setSendError('Ошибка сети'); }
    finally { setSending(false); }
  };

  const callManager = async () => {
    if (!activeTicket) return;
    // TODO: реализовать через API escalate
    setSendError('Менеджер уведомлён');
    setTimeout(() => setSendError(''), 3000);
  };

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 12 }}>
      <div className="loading-spinner" />
      <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Загрузка портала...</span>
    </div>
  );

  if (error === 'not_authorized') return (
    <div style={{ padding: 24, textAlign: 'center' }}>
      <AlertCircle size={40} style={{ color: '#ef4444', marginBottom: 12 }} />
      <h2 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>Войдите через Telegram</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
        Для доступа к порталу откройте его через бота @DonMatteo_VPN_bot
      </p>
    </div>
  );

  const rw = profile?.remnawave || {};
  const rwUser = rw.user || {};
  const rwSub = rw.subscription?.user || {};
  const devices = rw.devices || [];
  const bedolaga = profile?.bedolaga || {};
  const traffic = rwUser.userTraffic || {};
  const usedBytes = traffic.usedTrafficBytes || 0;
  const limitBytes = rwUser.trafficLimitBytes || 0;
  const trafficPct = limitBytes > 0 ? Math.min(100, (usedBytes / limitBytes) * 100) : 0;
  const status = (rwUser.status || '').toUpperCase();
  const isActive = status === 'ACTIVE';
  
  const history = activeTicket?.history || activeTicket?.last_messages || [];

  return (
    <div className="app" style={{ height: '100dvh', display: 'flex', flexDirection: 'column' }}>
      {/* Шапка */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem' }}>🛡 Поддержка</div>
            {rwUser.username && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>@{rwUser.username}</div>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {activeTicket && (
              <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: 12, background: `${STATUS_COLORS[activeTicket.status]}22`, color: STATUS_COLORS[activeTicket.status], border: `1px solid ${STATUS_COLORS[activeTicket.status]}44` }}>
                {STATUS_LABELS[activeTicket.status]}
              </span>
            )}
            <button onClick={fetchData} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* Табы */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {[['chat', '💬 Чат'], ['profile', '👤 Профиль'], ['history', '📋 История']].map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer', fontSize: '0.82rem', fontWeight: tab === t ? 600 : 400,
              background: 'transparent', color: tab === t ? 'var(--primary)' : 'var(--text-muted)',
              borderBottom: tab === t ? '2px solid var(--primary)' : '2px solid transparent',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Контент */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        
        {/* ЧАТ */}
        {tab === 'chat' && (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
              {history.length === 0 ? (
                <div style={{ textAlign: 'center', paddingTop: 40 }}>
                  <MessageSquare size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Напишите ваш вопрос</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: 6 }}>AI-ассистент ответит сразу, а если не сможет — подключит менеджера</div>
                </div>
              ) : (
                history.map((msg, i) => <ChatBubble key={i} msg={msg} />)
              )}
              <div ref={messagesEndRef} />
            </div>

            {sendError && (
              <div style={{ padding: '4px 16px', fontSize: '0.78rem', color: '#ef4444' }}>{sendError}</div>
            )}

            <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <textarea
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                  placeholder="Написать сообщение..."
                  rows={2}
                  style={{
                    flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                    borderRadius: 10, color: 'var(--text-primary)', padding: '8px 12px',
                    fontSize: '0.88rem', resize: 'none', outline: 'none',
                  }}
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !message.trim()}
                  style={{
                    alignSelf: 'flex-end', padding: '8px 16px', borderRadius: 10, border: 'none',
                    background: 'var(--primary, #3b82f6)', color: '#fff', cursor: 'pointer',
                    opacity: sending || !message.trim() ? 0.5 : 1,
                  }}
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          </>
        )}

        {/* ПРОФИЛЬ */}
        {tab === 'profile' && (
          <div style={{ overflowY: 'auto', padding: '12px 16px' }}>
            {/* Статус подписки */}
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="card-header"><span className="card-title">📡 Статус подписки</span></div>
              {rw.not_found ? (
                <div style={{ color: '#ef4444', fontSize: '0.9rem', padding: '8px 0' }}>
                  ⚠️ Вы не найдены в системе. Обратитесь в поддержку.
                </div>
              ) : (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <span style={{
                      padding: '3px 12px', borderRadius: 12, fontSize: '0.78rem', fontWeight: 600,
                      background: isActive ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                      color: isActive ? '#22c55e' : '#ef4444',
                    }}>
                      {isActive ? '✅ Активна' : `❌ ${status || 'Нет данных'}`}
                    </span>
                  </div>
                  
                  {limitBytes > 0 && (
                    <div style={{ marginBottom: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: 3, color: 'var(--text-secondary)' }}>
                        <span>Трафик: {formatBytes(usedBytes)}</span>
                        <span>/ {formatBytes(limitBytes)} ({trafficPct.toFixed(0)}%)</span>
                      </div>
                      <div style={{ height: 6, background: 'var(--bg-secondary)', borderRadius: 3 }}>
                        <div style={{ height: '100%', width: `${trafficPct}%`, background: trafficPct > 80 ? '#ef4444' : trafficPct > 60 ? '#f59e0b' : '#22c55e', borderRadius: 3, transition: 'width 0.3s' }} />
                      </div>
                    </div>
                  )}
                  
                  <div className="data-row"><span className="data-label">Истекает</span><span className="data-value">{formatDate(rwUser.expireAt)}</span></div>
                  <div className="data-row"><span className="data-label">Устройств</span><span className="data-value">{devices.length}</span></div>
                  {rwUser.hwidDeviceLimit && <div className="data-row"><span className="data-label">Лимит устройств</span><span className="data-value">{rwUser.hwidDeviceLimit}</span></div>}
                </>
              )}
            </div>

            {/* Баланс */}
            {bedolaga && !bedolaga.error && (
              <div className="card" style={{ marginBottom: 12 }}>
                <div className="card-header"><span className="card-title">💰 Баланс</span></div>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--primary)', padding: '4px 0' }}>
                  {bedolaga.balance || 0} ₽
                </div>
              </div>
            )}

            {/* Кнопка вызова менеджера */}
            <button
              className="btn btn-secondary"
              onClick={() => setTab('chat')}
              style={{ width: '100%', marginTop: 8 }}
            >
              💬 Написать в поддержку
            </button>
          </div>
        )}

        {/* ИСТОРИЯ ТИКЕТОВ */}
        {tab === 'history' && (
          <div style={{ overflowY: 'auto', padding: '12px 16px' }}>
            {tickets.length === 0 ? (
              <div className="empty-state" style={{ paddingTop: 40 }}>
                <History size={28} style={{ color: 'var(--text-muted)' }} />
                <div className="empty-title" style={{ marginTop: 10 }}>Нет обращений</div>
                <div className="empty-text">История ваших тикетов появится здесь</div>
              </div>
            ) : tickets.map(ticket => {
              const history = ticket.history || ticket.last_messages || [];
              const lastMsg = history[history.length - 1];
              return (
                <div key={ticket.id} style={{ padding: '10px 12px', marginBottom: 8, borderRadius: 10, background: 'var(--bg-secondary)', borderLeft: `3px solid ${STATUS_COLORS[ticket.status] || '#3b82f6'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.78rem', color: STATUS_COLORS[ticket.status], fontWeight: 600 }}>
                      {STATUS_LABELS[ticket.status] || '💬 Тикет'}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {formatDate(ticket.created_at)}
                    </span>
                  </div>
                  {ticket.reason && <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4 }}>{ticket.reason}</div>}
                  {lastMsg && (
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {lastMsg.role === 'manager' ? '👨‍💼' : lastMsg.role === 'assistant' ? '🤖' : '👤'} {lastMsg.content}
                    </div>
                  )}
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    {history.length} сообщений
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

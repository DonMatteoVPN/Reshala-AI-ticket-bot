import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, RefreshCw, Sparkles } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function AIChatTestPage({ settings, initData }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text, time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const r = await fetch(`${API}/api/ai/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: text })
      });
      const data = await r.json();

      const aiMsg = {
        role: 'assistant',
        content: data.ok ? data.reply : `Ошибка: ${data.error || 'Не удалось получить ответ'}`,
        time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        error: !data.ok
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Ошибка сети. Проверьте подключение.',
        time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        error: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => setMessages([]);

  const testQuestions = [
    'Как подключить VPN?',
    'Не работает подписка',
    'Какие тарифы есть?',
    'Как сбросить устройства?'
  ];

  return (
    <div data-testid="ai-chat-test-page">
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-header">
          <span className="card-title">AI Чат-тест</span>
          <button className="btn btn-secondary btn-sm" onClick={clearChat} data-testid="clear-chat">
            <RefreshCw size={13} /> Очистить
          </button>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginBottom: 8 }}>
          Тестирование AI-ассистента. Проверьте качество ответов перед запуском в production.
        </p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {testQuestions.map((q, i) => (
            <button
              key={i}
              className="btn btn-secondary btn-sm"
              onClick={() => setInput(q)}
              style={{ fontSize: '0.75rem' }}
              data-testid={`quick-question-${i}`}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="chat-container" ref={chatRef} data-testid="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state" style={{ padding: '40px 20px' }}>
            <div className="empty-icon"><Sparkles size={24} /></div>
            <div className="empty-title">Начните диалог</div>
            <div className="empty-text">Напишите сообщение для тестирования AI-ассистента</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`} data-testid={`message-${i}`}>
            <div className="chat-avatar">
              {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className="chat-bubble">
              <div className={`chat-text ${msg.error ? 'error' : ''}`}>{msg.content}</div>
              <div className="chat-time">{msg.time}</div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant">
            <div className="chat-avatar"><Bot size={16} /></div>
            <div className="chat-bubble">
              <div className="chat-typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input-container" data-testid="chat-input-container">
        <input
          className="chat-input"
          placeholder="Напишите сообщение..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          disabled={loading}
          data-testid="chat-input"
        />
        <button
          className="btn btn-primary"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          data-testid="send-message"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

import React from 'react';
import { Search, Cpu, Settings, BookOpen, MessageSquare, Flame } from 'lucide-react';

const tabs = [
  { id: 'search', label: 'Поиск', icon: Search },
  { id: 'tickets', label: 'Тикеты', icon: Flame },
  { id: 'chat-test', label: 'AI Чат', icon: MessageSquare },
  { id: 'providers', label: 'AI', icon: Cpu },
  { id: 'knowledge', label: 'База', icon: BookOpen },
  { id: 'settings', label: 'Настройки', icon: Settings },
];

export default function Navigation({ page, setPage }) {
  return (
    <nav className="nav" data-testid="navigation">
      {tabs.map(t => (
        <button
          key={t.id}
          className={`nav-btn ${page === t.id ? 'active' : ''}`}
          onClick={() => setPage(t.id)}
          data-testid={`nav-${t.id}`}
        >
          <t.icon />
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  );
}

import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import Header from './components/Header';
import Navigation from './components/Navigation';
import SearchPage from './pages/SearchPage';
import SettingsPage from './pages/SettingsPage';
import ProvidersPage from './pages/ProvidersPage';
import KnowledgePage from './pages/KnowledgePage';
import AIChatTestPage from './pages/AIChatTestPage';
import TicketsPage from './pages/TicketsPage';
import { ShieldX } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function AccessDenied() {
  return (
    <div className="access-denied" data-testid="access-denied">
      <div className="access-denied-icon">
        <ShieldX size={48} />
      </div>
      <h2>Доступ запрещён</h2>
      <p>Mini App доступен только для менеджеров.</p>
      <p className="text-muted">Если вы менеджер — обратитесь к администратору для добавления вашего ID.</p>
    </div>
  );
}

function App() {
  const [page, setPage] = useState('search');
  const [settings, setSettings] = useState(null);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [telegramUser, setTelegramUser] = useState(null);
  
  // Сохранение состояния поиска между вкладками
  const [searchState, setSearchState] = useState({
    query: '',
    result: null,
    section: 'profile'
  });

  const fetchSettings = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/settings`);
      const data = await r.json();
      setSettings(data);
      return data;
    } catch (e) {
      console.error('Settings fetch error:', e);
      return null;
    }
  }, []);

  const fetchProviders = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/settings/providers`);
      const data = await r.json();
      setProviders(data.providers || []);
    } catch (e) {
      console.error('Providers fetch error:', e);
    }
  }, []);

  const checkAccess = useCallback((settingsData, userId) => {
    if (!settingsData || !userId) return false;
    const allowedIds = settingsData.allowed_manager_ids || [];
    return allowedIds.includes(userId);
  }, []);

  useEffect(() => {
    const init = async () => {
      let tgUser = null;
      
      if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        
        const initData = window.Telegram.WebApp.initDataUnsafe;
        if (initData?.user) {
          tgUser = initData.user;
          setTelegramUser(tgUser);
        }
      }
      
      const settingsData = await fetchSettings();
      await fetchProviders();
      
      if (tgUser?.id) {
        const hasAccess = checkAccess(settingsData, tgUser.id);
        setAccessDenied(!hasAccess);
      } else {
        const isDev = !window.Telegram?.WebApp?.initData;
        setAccessDenied(!isDev);
      }
      
      setLoading(false);
    };
    
    init();
  }, [fetchSettings, fetchProviders, checkAccess]);

  if (loading) {
    return (
      <div className="app-loading" data-testid="app-loading">
        <div className="loading-spinner" />
        <span>Загрузка...</span>
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="app" data-testid="app-container">
        <Header settings={settings} />
        <AccessDenied />
      </div>
    );
  }

  return (
    <div className="app" data-testid="app-container">
      <Header settings={settings} telegramUser={telegramUser} />
      <Navigation page={page} setPage={setPage} />
      <main className="app-main">
        {/* Поиск — сохраняет состояние */}
        <div style={{ display: page === 'search' ? 'block' : 'none' }}>
          <SearchPage 
            settings={settings} 
            searchState={searchState}
            setSearchState={setSearchState}
          />
        </div>
        
        {/* Тикеты */}
        <div style={{ display: page === 'tickets' ? 'block' : 'none' }}>
          <TicketsPage settings={settings} />
        </div>
        
        {/* AI Чат */}
        {page === 'chat-test' && <AIChatTestPage settings={settings} />}
        
        {/* AI Провайдеры */}
        {page === 'providers' && (
          <ProvidersPage
            providers={providers}
            settings={settings}
            onRefresh={() => { fetchProviders(); fetchSettings(); }}
          />
        )}
        
        {/* База знаний */}
        {page === 'knowledge' && <KnowledgePage />}
        
        {/* Настройки */}
        {page === 'settings' && (
          <SettingsPage
            settings={settings}
            onUpdate={() => fetchSettings()}
          />
        )}
      </main>
    </div>
  );
}

export default App;

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
import ClientPortalPage from './pages/ClientPortalPage';
import { ShieldX } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function AccessDenied() {
  return (
    <div className="access-denied" data-testid="access-denied">
      <div className="access-denied-icon"><ShieldX size={48} /></div>
      <h2>Доступ запрещён</h2>
      <p>Mini App доступен только для менеджеров.</p>
      <p className="text-muted">Если вы менеджер — обратитесь к администратору.</p>
    </div>
  );
}

// Проверяем — это клиентский портал или менеджерский?
function getPortalMode() {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.search);
  
  // /client или ?mode=client или ?token=... → клиентский режим
  if (path.includes('/client') || params.get('mode') === 'client' || params.get('token')) {
    return { mode: 'client', token: params.get('token'), clientId: params.get('client_id') };
  }
  
  // ?client_id=... → менеджер открыл карточку через кнопку в топике
  if (params.get('client_id') && !params.get('token')) {
    return { mode: 'manager_client_view', clientId: params.get('client_id'), section: params.get('section') };
  }
  
  return { mode: 'manager' };
}

function App() {
  const portalMode = getPortalMode();
  
  // Клиентский портал
  if (portalMode.mode === 'client') {
    return <ClientPortalWrapper token={portalMode.token} />;
  }
  
  // Менеджерский интерфейс
  return <ManagerApp initialClientId={portalMode.mode === 'manager_client_view' ? portalMode.clientId : null} initialSection={portalMode.section} />;
}

function ClientPortalWrapper({ token }) {
  const [initData, setInitData] = useState('');
  
  useEffect(() => {
    if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
      setInitData(window.Telegram.WebApp.initData || '');
    }
  }, []);
  
  return <ClientPortalPage initData={initData} clientToken={token} />;
}

function ManagerApp({ initialClientId, initialSection }) {
  const [page, setPage] = useState('search');
  const [settings, setSettings] = useState(null);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [telegramUser, setTelegramUser] = useState(null);
  const [initData, setInitData] = useState('');

  const [searchState, setSearchState] = useState({
    query: initialClientId || '',
    result: null,
    section: initialSection || 'profile'
  });

  const fetchSettings = useCallback(async (dataStr) => {
    try {
      const headers = {};
      if (dataStr) headers['X-Telegram-Init-Data'] = dataStr;
      const r = await fetch(`${API}/api/settings`, { headers });
      const data = await r.json();
      setSettings(data);
      return data;
    } catch (e) { console.error('Settings fetch error:', e); return null; }
  }, []);

  const fetchProviders = useCallback(async (dataStr) => {
    try {
      const headers = {};
      if (dataStr) headers['X-Telegram-Init-Data'] = dataStr;
      const r = await fetch(`${API}/api/settings/providers`, { headers });
      const data = await r.json();
      setProviders(data.providers || []);
    } catch (e) { console.error('Providers fetch error:', e); }
  }, []);

  const checkAccess = useCallback((settingsData, userId) => {
    if (!settingsData || !userId) return false;
    return (settingsData.allowed_manager_ids || []).includes(userId);
  }, []);

  useEffect(() => {
    const init = async () => {
      let tgUser = null;
      let rawData = '';

      if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        rawData = window.Telegram.WebApp.initData;
        setInitData(rawData);
        const initDataUnsafe = window.Telegram.WebApp.initDataUnsafe;
        if (initDataUnsafe?.user) { tgUser = initDataUnsafe.user; setTelegramUser(tgUser); }
      }

      const settingsData = await fetchSettings(rawData);
      await fetchProviders(rawData);

      if (tgUser?.id) {
        setAccessDenied(!checkAccess(settingsData, tgUser.id));
      } else {
        setAccessDenied(!!rawData); // Если есть initData но нет user — deny
      }
      
      // Если открыт с client_id — переходим на поиск
      if (initialClientId) {
        setPage('search');
      }

      setLoading(false);
    };
    init();
  }, [fetchSettings, fetchProviders, checkAccess, initialClientId]);

  // Если открыт с client_id — автопоиск
  useEffect(() => {
    if (initialClientId && !loading && !accessDenied) {
      setPage('search');
    }
  }, [initialClientId, loading, accessDenied]);

  if (loading) return (
    <div className="app-loading" data-testid="app-loading">
      <div className="loading-spinner" />
      <span>Загрузка...</span>
    </div>
  );

  if (accessDenied) return (
    <div className="app" data-testid="app-container">
      <Header settings={settings} />
      <AccessDenied />
    </div>
  );

  return (
    <div className="app" data-testid="app-container">
      <Header settings={settings} telegramUser={telegramUser} />
      <Navigation page={page} setPage={setPage} />
      <main className="app-main">
        <div style={{ display: page === 'search' ? 'block' : 'none' }}>
          <SearchPage settings={settings} searchState={searchState} setSearchState={setSearchState} initData={initData} />
        </div>
        <div style={{ display: page === 'tickets' ? 'block' : 'none' }}>
          <TicketsPage settings={settings} initData={initData} />
        </div>
        {page === 'chat-test' && <AIChatTestPage settings={settings} initData={initData} />}
        {page === 'providers' && <ProvidersPage providers={providers} settings={settings} initData={initData} onRefresh={() => { fetchProviders(initData); fetchSettings(initData); }} />}
        {page === 'knowledge' && <KnowledgePage initData={initData} />}
        {page === 'settings' && <SettingsPage settings={settings} initData={initData} onUpdate={() => fetchSettings(initData)} />}
      </main>
    </div>
  );
}

export default App;

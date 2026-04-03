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

// ─── Detect portal mode ────────────────────────────────────────────────────
// Rules (checked in priority order):
//  1. Path starts with /client  → client portal
//  2. URL has ?token=XXX        → client portal (magic-link)
//  3. URL has ?mode=client      → client portal
//  4. Otherwise                 → manager mode
function getPortalMode() {
  const path   = window.location.pathname;
  const params = new URLSearchParams(window.location.search);
  if (path.startsWith('/client'))   return 'client';
  if (params.get('token'))          return 'client';
  if (params.get('mode') === 'client') return 'client';
  return 'manager';
}

// Extract magic-link token from URL if present
function getMagicToken() {
  return new URLSearchParams(window.location.search).get('token') || null;
}

// Get pre-selected client_id for manager auto-search
function getPreselectedClientId() {
  return new URLSearchParams(window.location.search).get('client_id') || null;
}

// ─── Access Denied screen ─────────────────────────────────────────────────
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

// ─── Client Portal wrapper ─────────────────────────────────────────────────
// Initialises Telegram WebApp (if available) and passes token down
function ClientPortalWrapper() {
  const [initData, setInitData]     = useState('');
  const [clientToken, setClientToken] = useState(getMagicToken());

  useEffect(() => {
    if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
      const raw = window.Telegram.WebApp.initData;
      if (raw) setInitData(raw);
    }
  }, []);

  return (
    <div className="app">
      <ClientPortalPage initData={initData} clientToken={clientToken} />
    </div>
  );
}

// ─── Manager App ───────────────────────────────────────────────────────────
function ManagerApp() {
  const [page, setPage]               = useState('search');
  const [settings, setSettings]       = useState(null);
  const [providers, setProviders]     = useState([]);
  const [loading, setLoading]         = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [telegramUser, setTelegramUser] = useState(null);
  const [initData, setInitData]       = useState('');

  // Pre-selected client from URL params (when opened from manager topic button)
  const preselectedClientId = getPreselectedClientId();
  const preselectedSection  = new URLSearchParams(window.location.search).get('section') || 'profile';

  // Сохранение состояния поиска между вкладками
  const [searchState, setSearchState] = useState({
    query:   preselectedClientId || '',
    result:  null,
    section: preselectedSection
  });

  const fetchSettings = useCallback(async (dataStr) => {
    try {
      const hdrs = {};
      if (dataStr) hdrs['X-Telegram-Init-Data'] = dataStr;
      const r    = await fetch(`${API}/api/settings`, { headers: hdrs });
      const data = await r.json();
      setSettings(data);
      return data;
    } catch (e) {
      console.error('Settings fetch error:', e);
      return null;
    }
  }, []);

  const fetchProviders = useCallback(async (dataStr) => {
    try {
      const hdrs = {};
      if (dataStr) hdrs['X-Telegram-Init-Data'] = dataStr;
      const r    = await fetch(`${API}/api/settings/providers`, { headers: hdrs });
      const data = await r.json();
      setProviders(data.providers || []);
    } catch (e) {
      console.error('Providers fetch error:', e);
    }
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
        const unsafe = window.Telegram.WebApp.initDataUnsafe;
        if (unsafe?.user) {
          tgUser = unsafe.user;
          setTelegramUser(tgUser);
        }
      }

      const settingsData = await fetchSettings(rawData);
      await fetchProviders(rawData);

      if (tgUser?.id) {
        setAccessDenied(!checkAccess(settingsData, tgUser.id));
      } else {
        // Dev mode: no Telegram context → allow (useful for browser testing)
        setAccessDenied(!!rawData); // deny only if initData is present but user not in list
      }

      // If pre-selected client_id is in URL, auto-navigate to search tab
      if (preselectedClientId) {
        setPage('search');
      }

      setLoading(false);
    };
    init();
  }, [fetchSettings, fetchProviders, checkAccess, preselectedClientId]);

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
        {/* Search — keeps state between tabs */}
        <div style={{ display: page === 'search' ? 'block' : 'none' }}>
          <SearchPage
            settings={settings}
            searchState={searchState}
            setSearchState={setSearchState}
            initData={initData}
          />
        </div>

        {/* Tickets (split-panel) */}
        <div style={{ display: page === 'tickets' ? 'block' : 'none' }}>
          <TicketsPage settings={settings} initData={initData} />
        </div>

        {/* AI Chat test */}
        {page === 'chat-test' && <AIChatTestPage settings={settings} initData={initData} />}

        {/* AI Providers */}
        {page === 'providers' && (
          <ProvidersPage
            providers={providers}
            settings={settings}
            initData={initData}
            onRefresh={() => { fetchProviders(initData); fetchSettings(initData); }}
          />
        )}

        {/* Knowledge base */}
        {page === 'knowledge' && <KnowledgePage initData={initData} />}

        {/* Settings */}
        {page === 'settings' && (
          <SettingsPage
            settings={settings}
            initData={initData}
            onUpdate={() => fetchSettings(initData)}
          />
        )}
      </main>
    </div>
  );
}

// ─── Root ──────────────────────────────────────────────────────────────────
function App() {
  const mode = getPortalMode();
  if (mode === 'client') return <ClientPortalWrapper />;
  return <ManagerApp />;
}

export default App;

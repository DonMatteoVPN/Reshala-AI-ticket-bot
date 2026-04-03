# Reshala AI v2 — Полная инструкция по установке и настройке

> **Ветка:** `feature/v2-full-rework`  
> **Последнее обновление:** апрель 2026

---

## Содержание

1. [Что нового в v2](#1-что-нового-в-v2)  
2. [Архитектура](#2-архитектура)  
3. [Требования](#3-требования)  
4. [Быстрый старт (Docker)](#4-быстрый-старт-docker)  
5. [Переменные окружения (.env)](#5-переменные-окружения-env)  
6. [Настройка Telegram-бота](#6-настройка-telegram-бота)  
7. [Настройка Nginx (HTTPS)](#7-настройка-nginx-https)  
8. [Клиентский портал (/client)](#8-клиентский-портал-client)  
9. [Менеджерский MiniApp](#9-менеджерский-miniapp)  
10. [AI-агент — настройка](#10-ai-агент--настройка)  
11. [Remnawave — интеграция](#11-remnawave--интеграция)  
12. [Bedolaga — интеграция](#12-bedolaga--интеграция)  
13. [MongoDB — схема коллекций](#13-mongodb--схема-коллекций)  
14. [API — все эндпоинты](#14-api--все-эндпоинты)  
15. [Маршрутизация фронтенда](#15-маршрутизация-фронтенда)  
16. [Разработка локально](#16-разработка-локально)  
17. [Обновление с main](#17-обновление-с-main)  
18. [Решение проблем](#18-решение-проблем)

---

## 1. Что нового в v2

### Backend

| Изменение | Файл | Описание |
|---|---|---|
| Исправлен баг `hwid_all` | `bot/keyboards/__init__.py` | Callback был `hwid_all`, обработчик ждал `hwid_del_all` — теперь совпадает |
| Исправлен баг `close_ticket` | `bot/keyboards/__init__.py` | Передавался `client_id` вместо `ticket_id` |
| Кнопки менеджера → MiniApp | `bot/keyboards/__init__.py` | Все кнопки в топике теперь открывают MiniApp через `WebAppInfo` с параметрами `?client_id=&section=` |
| Закрытие тикета по `client_id` | `bot/handlers/support_manager.py` | Новый хендлер `close_ticket_by_client_callback` |
| Умный AI-агент | `bot/handlers/support_client.py` | Промпт подтягивает реальные данные: UUID, статус, трафик, срок, устройства, баланс Bedolaga |
| Клиентский Portal API | `backend/routers/client_portal.py` (новый) | 6 эндпоинтов: авторизация, профиль, тикеты, переписка |
| Регистрация роутера | `backend/server.py` | `client_portal_router` зарегистрирован под `/api/client` |

### Frontend

| Изменение | Файл | Описание |
|---|---|---|
| Режим клиентского портала | `App.js` | URL `/client` или `?token=` → рендерит `ClientPortalPage` |
| Авто-поиск по `client_id` | `App.js` | Параметр `?client_id=123` → менеджер сразу видит нужного пользователя |
| Сплит-панель тикетов | `pages/TicketsPage.js` | Список слева (35%) + детали справа (65%), тикет-чат пузырями |
| Авто-загрузка профиля | `pages/TicketsPage.js` | При выборе тикета автоматически подтягивает данные из `/api/lookup` |
| Новые вкладки в тикете | `pages/TicketsPage.js` | Переписка / Профиль / Действия — без перехода на другую страницу |
| Клиентский портал | `pages/ClientPortalPage.js` (новый) | Три вкладки: Чат / Профиль / История — работает без Telegram |

---

## 2. Архитектура

```
                        ┌──────────────────────────────┐
                        │       Telegram Bot           │
                        │  (python-telegram-bot v20)   │
                        └──────────┬───────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
             Клиент пишет   Менеджер          Кнопки
             в поддержку    отвечает в        открывают
                            топике            MiniApp
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                         FastAPI Backend (:8001)                        │
│                                                                         │
│  /api/tickets/*       — CRUD тикетов, ответы менеджера                 │
│  /api/actions/*       — reset-traffic, revoke, hwid, block/unblock      │
│  /api/lookup          — поиск пользователя в Remnawave по TG ID        │
│  /api/settings/*      — настройки, провайдеры AI, база знаний          │
│  /api/client/*        — клиентский портал (профиль, тикеты, чат)       │
└───────────┬───────────────────┬────────────────────────────────────────┘
            │                   │
     ┌──────▼──────┐     ┌──────▼──────┐
     │  MongoDB    │     │  Remnawave  │
     │  (тикеты,  │     │  Panel API  │
     │  настройки,│     │             │
     │  токены)   │     └─────────────┘
     └────────────┘
                            ┌──────────────────────────────┐
                            │       React Frontend (:3000) │
                            │                              │
                            │  yourdomain.com/             │
                            │    → Менеджерский MiniApp    │
                            │                              │
                            │  yourdomain.com/client       │
                            │    → Клиентский портал       │
                            │                              │
                            │  yourdomain.com/?token=XXX   │
                            │    → Портал по magic-link    │
                            └──────────────────────────────┘
```

---

## 3. Требования

- **Docker** ≥ 24 + **Docker Compose** ≥ 2.20
- **Telegram Bot** — создать у `@BotFather`
- **Remnawave** — панель с настроенным API
- **VPS/сервер** с публичным IP и доменом
- **HTTPS** — обязательно для Telegram WebApp (можно через Nginx + Let's Encrypt)
- Минимальные ресурсы: 1 vCPU, 512 MB RAM, 5 GB диск

---

## 4. Быстрый старт (Docker)

### 4.1 Клонировать ветку v2

```bash
git clone -b feature/v2-full-rework https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot.git reshala
cd reshala
```

### 4.2 Создать файл окружения

```bash
cp .env.example .env
nano .env   # или vim .env
```

Заполните все обязательные переменные (см. раздел 5).

### 4.3 Запустить

```bash
docker compose up -d --build
```

Проверить статус:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f bot
```

### 4.4 Проверить работу

| Проверка | URL |
|---|---|
| Backend API | `https://api.your-domain.com/docs` |
| Frontend | `https://your-domain.com` |
| Клиентский портал | `https://your-domain.com/client?token=TEST` (при `SKIP_AUTH=true`) |

---

## 5. Переменные окружения (.env)

### Обязательные

```env
# Telegram Bot Token (получить у @BotFather)
BOT_TOKEN=1234567890:AAF...

# Remnawave API
REMNAWAVE_API_URL=https://panel.your-domain.com
REMNAWAVE_API_TOKEN=eyJhbGci...

# Telegram-группа с топиками (ID начинается с -100)
SUPPORT_GROUP_ID=-1001234567890

# ID Telegram-менеджеров через запятую (получить у @userinfobot)
ALLOWED_MANAGER_IDS=123456789,987654321
```

### URL для MiniApp

```env
# Публичный URL бэкенда (используется React)
REACT_APP_BACKEND_URL=https://api.your-domain.com

# Домен MiniApp (бот вставляет в кнопки WebAppInfo)
MINI_APP_DOMAIN=https://your-domain.com

# Опционально — прямой URL (если отличается от MINI_APP_DOMAIN)
# MINI_APP_URL=https://your-domain.com
```

### MongoDB

```env
MONGO_URL=mongodb://mongodb:27017
DB_NAME=reshala_support
```

### Разработка

```env
# ВАЖНО: false для продакшена!
# true — отключает проверку Telegram initData (удобно для локального теста)
SKIP_AUTH=false
```

### Опционально — Bedolaga

```env
# Bedolaga billing API (необязательно)
BEDOLAGA_API_URL=https://billing.your-domain.com
BEDOLAGA_API_TOKEN=bedolaga_token_here
```

### Название сервиса

```env
SERVICE_NAME=Решала Support
```

---

## 6. Настройка Telegram-бота

### 6.1 Создать бота

1. Написать `@BotFather` → `/newbot`
2. Получить `BOT_TOKEN` → вставить в `.env`

### 6.2 Включить Groups Mode

В `@BotFather`:
```
/setjoingroups @your_bot → Enabled
/setprivacy @your_bot → Disabled   (чтобы бот видел все сообщения)
```

### 6.3 Создать группу с топиками

1. Создать Telegram-группу → сделать **супергруппой**
2. Включить **Темы (Topics)**: `Настройки группы → Темы → Включить`
3. Добавить бота как **администратора** с правами:
   - Управление сообщениями ✅
   - Удаление сообщений ✅  
   - Управление темами ✅
4. Получить ID группы: написать `@userinfobot` или `/start` в группе через `@get_id_bot`
5. Вставить ID в `.env` → `SUPPORT_GROUP_ID=-1001234567890`

### 6.4 Зарегистрировать MiniApp

В `@BotFather`:
```
/newapp @your_bot
```
- **URL:** `https://your-domain.com` (фронтенд)
- **Short name:** `support` (или любое)

Полный URL MiniApp будет: `https://t.me/your_bot/support`

### 6.5 Добавить MiniApp-кнопку в меню бота

```
/setmenubutton @your_bot
→ Web App
→ URL: https://your-domain.com
→ Text: Поддержка
```

---

## 7. Настройка Nginx (HTTPS)

Telegram WebApp требует HTTPS. Пример конфигурации:

```nginx
# /etc/nginx/sites-available/reshala

# Frontend (React)
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Все маршруты → React (SPA)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Backend API
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # Нужно для WebSocket если будет добавлено
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Редирект с HTTP
server {
    listen 80;
    server_name your-domain.com api.your-domain.com;
    return 301 https://$host$request_uri;
}
```

Получить сертификат Let's Encrypt:

```bash
certbot --nginx -d your-domain.com -d api.your-domain.com
```

---

## 8. Клиентский портал (/client)

### Что это

Отдельная страница для конечного пользователя VPN-сервиса. Работает **без Telegram** — пользователь открывает ссылку в браузере. Три вкладки:

- **💬 Чат** — переписка с менеджером/AI в реальном времени (polling 15 сек)
- **👤 Профиль** — статус подписки, трафик, устройства, баланс
- **📋 История** — все прошлые тикеты

### Способы авторизации

#### A. Через Telegram WebApp (автоматически)

Если клиент открывает портал через Telegram MiniApp, `initData` передаётся автоматически. Никаких дополнительных настроек не нужно.

#### B. Magic-link (браузер без Telegram)

1. Менеджер генерирует ссылку через API:
   ```http
   POST /api/client/auth/generate-link
   Content-Type: application/json
   X-Telegram-Init-Data: <manager_initData>

   { "client_id": 123456789 }
   ```
   Ответ: `{ "token": "abc123...", "url": "https://your-domain.com/client?token=abc123..." }`

2. Ссылка действует **7 дней**, открывается в любом браузере.
3. Токен хранится в MongoDB, коллекция `client_tokens`.

#### C. Режим разработки (`SKIP_AUTH=true`)

При `SKIP_AUTH=true` любой запрос с заголовком `X-Client-Token: anyvalue` или `?token=anyvalue` проходит без проверки. **Использовать только для разработки!**

### URL маршруты портала

```
https://your-domain.com/client           — клиент открывает из Telegram
https://your-domain.com/client?token=XXX — magic-link в браузере
https://your-domain.com/?token=XXX       — альтернативный вид
https://your-domain.com/?mode=client     — принудительный режим клиента
```

---

## 9. Менеджерский MiniApp

### Открытие из Telegram

Менеджеры открывают MiniApp двумя способами:

**A. Через меню бота** (общий вход):
```
https://your-domain.com/
```

**B. Через кнопки в топике** (автоматический переход к пользователю):

Все кнопки в первом системном сообщении топика (`🔍 Данные`, `📊 Трафик`, `📱 Устройства` и т.д.) открывают MiniApp с параметрами:
```
https://your-domain.com/?client_id=123456789&section=profile
https://your-domain.com/?client_id=123456789&section=traffic
https://your-domain.com/?client_id=123456789&section=devices
```

При открытии с `client_id` менеджер автоматически видит карточку нужного пользователя с нужной вкладкой.

### Вкладки менеджера

| Вкладка | Описание |
|---|---|
| 🔍 Поиск | Поиск по Telegram ID или username, полная карточка пользователя + Remnawave-данные |
| 🎫 Тикеты | Сплит-панель: список активных тикетов + переписка/профиль/действия |
| 💬 AI Чат | Тест AI-агента (отдельная sandbox-среда) |
| ⚡ Провайдеры | Управление AI-провайдерами (OpenAI, Anthropic, кастомный) |
| 📚 База знаний | CRUD статей для AI-агента |
| ⚙️ Настройки | Системные настройки, промпт AI, Remnawave/Bedolaga ключи |

### Сплит-панель тикетов

Левая часть (320 px):
- Список активных тикетов с аватаром, статусом, временем
- Фильтры: Все / 🔥 Эскалация / 🚨 Подозрительные
- Обновление каждые 10 сек

Правая часть:
- **Вкладка Переписка** — пузырьковый чат (клиент слева / менеджер+AI справа), поле ответа, Enter=отправить
- **Вкладка Профиль** — UUID, статус, трафик (прогресс-бар), баланс, устройства
- **Вкладка Действия** — кнопки управления подпиской без перехода на другую страницу

---

## 10. AI-агент — настройка

### Что умеет AI-агент в v2

При обращении пользователя агент автоматически получает из Remnawave:
- UUID пользователя
- Статус подписки (ACTIVE / DISABLED / ...)
- Дата окончания
- Использованный трафик / лимит
- Количество устройств (HWID)
- Баланс в Bedolaga (если настроен)

На основе этих данных агент формирует персонализированные ответы.

### Добавить AI-провайдера

1. Открыть MiniApp → вкладка **⚡ Провайдеры**
2. Нажать **Добавить провайдера**
3. Выбрать тип: `openai` / `anthropic` / `custom`
4. Заполнить:
   - **Название** — любое
   - **API Key**
   - **Модель** — например `gpt-4o`, `claude-3-5-sonnet-20241022`
   - **Base URL** (для кастомных: `https://api.openai.com/v1`)
5. Нажать **Активировать** — агент переключится на этот провайдер

### Системный промпт

В разделе **⚙️ Настройки → Промпт AI** можно настроить системный промпт. Переменные, которые подставляются автоматически:

```
{username}       — username или имя пользователя
{uuid}           — UUID в Remnawave
{status}         — статус подписки
{expire_date}    — дата окончания
{traffic_used}   — использованный трафик
{traffic_limit}  — лимит трафика
{device_count}   — количество HWID-устройств
{balance}        — баланс (Bedolaga)
{bedolaga_id}    — ID в Bedolaga
```

### База знаний

В разделе **📚 База знаний** можно добавить статьи, которые AI-агент будет использовать для ответов. Рекомендуется добавить:

- FAQ по подключению
- Инструкции по приложениям
- Типичные проблемы и решения

---

## 11. Remnawave — интеграция

### Настройка

```env
REMNAWAVE_API_URL=https://panel.your-domain.com
REMNAWAVE_API_TOKEN=eyJhbGci...
```

Токен — это JWT из настроек панели Remnawave (раздел API / Токены).

### Какие данные подтягиваются

| Данные | Эндпоинт Remnawave | Используется в |
|---|---|---|
| Профиль пользователя | `GET /api/users/by-telegram-id/{id}` | AI-промпт, профиль менеджера, клиентский портал |
| Трафик | из объекта пользователя (`userTraffic`) | Прогресс-бар трафика |
| Устройства (HWID) | `GET /api/hwid/{uuid}` | Вкладка устройств |
| Сброс трафика | `POST /api/users/{uuid}/reset-traffic` | Кнопка менеджера |
| Перевыпуск подписки | `POST /api/users/{uuid}/revoke-subscription` | Кнопка менеджера |
| Удаление HWID | `DELETE /api/hwid/{uuid}` | Кнопка менеджера |
| Блок/разблок | `PATCH /api/users/{uuid}` | Кнопка менеджера |

### Тест подключения

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://panel.your-domain.com/api/users | head -c 500
```

---

## 12. Bedolaga — интеграция

### Настройка

```env
BEDOLAGA_API_URL=https://billing.your-domain.com
BEDOLAGA_API_TOKEN=your_bedolaga_token
```

Параметры также можно указать в настройках через MiniApp (⚙️ Настройки).

### Что используется

- Поиск пользователя по TG ID → получение баланса
- Отображается в профиле (менеджер и клиентский портал)
- AI-агент знает баланс и может ответить на вопросы "сколько у меня денег"

---

## 13. MongoDB — схема коллекций

### `tickets`

```json
{
  "_id": "ObjectId",
  "id": "uuid4-string",
  "client_id": 123456789,
  "client_name": "Ivan",
  "client_username": "ivan",
  "status": "open|escalated|suspicious|closed",
  "reason": "Текст причины эскалации",
  "history": [
    {
      "role": "user|assistant|manager",
      "content": "Текст сообщения",
      "name": "Имя менеджера (если manager)",
      "timestamp": "ISO-8601"
    }
  ],
  "attachments": [],
  "topic_id": 12345,
  "created_at": "ISO-8601",
  "escalated_at": "ISO-8601",
  "closed_at": "ISO-8601",
  "user_data": {}
}
```

### `client_tokens`

Новая коллекция (создаётся автоматически):

```json
{
  "client_id": 123456789,
  "token": "random-32-hex",
  "expires_at": "ISO-8601 + 7 days",
  "created_at": "ISO-8601"
}
```

TTL-индекс создаётся автоматически при старте (`expires_at`).

### `settings`

```json
{
  "key": "main",
  "remnawave_url": "...",
  "remnawave_token": "...",
  "bedolaga_url": "...",
  "bedolaga_token": "...",
  "ai_system_prompt": "...",
  "service_name": "Решала Support",
  "allowed_manager_ids": [123, 456],
  "miniapp_url": "https://your-domain.com"
}
```

### `ai_providers`

```json
{
  "name": "GPT-4o",
  "type": "openai",
  "api_key": "sk-...",
  "model": "gpt-4o",
  "base_url": "https://api.openai.com/v1",
  "is_active": true,
  "created_at": "ISO-8601"
}
```

### `knowledge_base`

```json
{
  "title": "Как подключиться на Android",
  "content": "Текст статьи...",
  "tags": ["android", "подключение"],
  "created_at": "ISO-8601"
}
```

---

## 14. API — все эндпоинты

Полная документация Swagger: `https://api.your-domain.com/docs`

### Менеджерские эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/tickets/active` | Все активные тикеты |
| `POST` | `/api/tickets/{id}/reply` | Ответить клиенту (отправляет в Telegram) |
| `POST` | `/api/tickets/{id}/close` | Закрыть тикет |
| `POST` | `/api/tickets/{id}/remove` | Удалить тикет |
| `GET` | `/api/lookup` | Поиск пользователя (`?tg_id=` или `?username=`) |
| `POST` | `/api/actions/reset-traffic` | Сброс трафика |
| `POST` | `/api/actions/revoke-subscription` | Перевыпуск подписки |
| `POST` | `/api/actions/hwid-delete-all` | Удаление всех HWID |
| `POST` | `/api/actions/enable-user` | Разблокировать |
| `POST` | `/api/actions/disable-user` | Заблокировать |
| `GET` | `/api/settings` | Получить настройки |
| `POST` | `/api/settings` | Сохранить настройки |
| `GET` | `/api/settings/providers` | Список AI-провайдеров |
| `POST` | `/api/settings/providers` | Добавить провайдера |
| `PUT` | `/api/settings/providers/{id}` | Обновить провайдера |
| `DELETE` | `/api/settings/providers/{id}` | Удалить провайдера |
| `POST` | `/api/settings/providers/{id}/activate` | Активировать провайдера |
| `GET` | `/api/knowledge` | Список статей базы знаний |
| `POST` | `/api/knowledge` | Добавить статью |
| `PUT` | `/api/knowledge/{id}` | Обновить статью |
| `DELETE` | `/api/knowledge/{id}` | Удалить статью |

**Авторизация менеджера:** заголовок `X-Telegram-Init-Data: <initData из Telegram WebApp>`

### Клиентские эндпоинты (`/api/client/`)

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/client/auth/generate-link` | Генерация magic-link (вызывает менеджер) |
| `GET` | `/api/client/profile` | Профиль + подписка + устройства + баланс |
| `GET` | `/api/client/tickets` | История тикетов (последние 20) |
| `GET` | `/api/client/tickets/active` | Текущий открытый тикет |
| `POST` | `/api/client/tickets/message` | Отправить сообщение (создаёт тикет если нет) |
| `GET` | `/api/client/tickets/{id}/history` | Полная история тикета |

**Авторизация клиента:**
- Заголовок `X-Telegram-Init-Data: <initData>` (из Telegram WebApp)
- Заголовок `X-Client-Token: <token>` (magic-link)
- Query-параметр `?token=<token>`

---

## 15. Маршрутизация фронтенда

React-приложение работает как SPA. Чтобы маршруты `/client` работали при прямом открытии (не через Telegram), Nginx должен всегда отдавать `index.html`:

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

### Таблица маршрутов

| URL | Режим | Описание |
|---|---|---|
| `https://your-domain.com/` | Менеджер | Основной MiniApp для менеджеров |
| `https://your-domain.com/?client_id=123` | Менеджер | Менеджер с авто-поиском пользователя 123 |
| `https://your-domain.com/?client_id=123&section=traffic` | Менеджер | Менеджер, вкладка трафика для пользователя 123 |
| `https://your-domain.com/client` | Клиент | Клиентский портал (нужен initData из Telegram) |
| `https://your-domain.com/client?token=XXX` | Клиент | Клиентский портал по magic-link |
| `https://your-domain.com/?token=XXX` | Клиент | Альтернативный вид magic-link |
| `https://your-domain.com/?mode=client` | Клиент | Принудительный режим клиента |

---

## 16. Разработка локально

### Требования

- Python 3.11+
- Node.js 18+
- MongoDB (локально или через Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Создать .env с SKIP_AUTH=true для разработки
export SKIP_AUTH=true
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=reshala_dev
export BOT_TOKEN=your_token

# Запустить сервер
uvicorn server:app --reload --port 8001

# В отдельном терминале — бот
python -m bot.main
```

### Frontend

```bash
cd frontend
npm install

# .env.local
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env.local

npm start
# Открыть http://localhost:3000
```

### Только MongoDB через Docker

```bash
docker run -d --name mongo -p 27017:27017 mongo:7
```

---

## 17. Обновление с main

Если у вас уже запущена основная ветка (`main`), для перехода на v2:

```bash
# 1. Остановить текущий стек
docker compose down

# 2. Получить новую ветку
git fetch origin
git checkout feature/v2-full-rework
git pull origin feature/v2-full-rework

# 3. Скопировать текущий .env (если он не менялся, просто убедитесь что есть)
# cp /path/to/old/.env .env

# 4. Пересобрать и запустить
docker compose up -d --build

# 5. Проверить логи
docker compose logs -f --tail=50
```

**MongoDB** — данные сохраняются в Docker volume `mongodb_data`, они не удаляются при пересборке. Новая коллекция `client_tokens` создаётся автоматически.

---

## 18. Решение проблем

### Бот не отвечает

```bash
docker compose logs bot --tail=50
```

Проверить:
- `BOT_TOKEN` — правильный?
- `SUPPORT_GROUP_ID` — начинается с `-100...`?
- Бот добавлен в группу как администратор с правом управления темами?

### MiniApp не открывается / Access Denied

```bash
docker compose logs backend --tail=50
```

Проверить:
- `ALLOWED_MANAGER_IDS` — ваш TG ID добавлен?
- `REACT_APP_BACKEND_URL` — указывает на реальный публичный URL бэкенда (не localhost)?
- HTTPS настроен? Telegram WebApp требует только HTTPS.

### Клиентский портал: 403 Forbidden

Проверить:
- `SKIP_AUTH=false` в продакшене — нужен реальный `initData` или валидный `token`
- Токен magic-link не истёк (TTL 7 дней)
- В `client_tokens` коллекции есть запись для этого `client_id`

### AI не отвечает

```bash
docker compose logs backend | grep -i "ai\|openai\|anthropic"
```

Проверить:
- Добавлен хотя бы один провайдер в **⚡ Провайдеры** и помечен как активный
- API-ключ правильный и баланс не исчерпан
- Модель существует у провайдера

### Remnawave: данные не подтягиваются

```bash
curl -H "Authorization: Bearer $REMNAWAVE_API_TOKEN" \
     $REMNAWAVE_API_URL/api/users | python3 -m json.tool | head -30
```

Если ошибка — проверить `REMNAWAVE_API_URL` и `REMNAWAVE_API_TOKEN`.

### Полный сброс (без удаления данных)

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Пересобрать только фронтенд

```bash
docker compose build --no-cache frontend
docker compose up -d frontend
```

---

## Контакты и поддержка

- **GitHub:** https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot
- **Ветка v2:** `feature/v2-full-rework`
- **Pull Request:** https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot/pull/new/feature/v2-full-rework

---

*Этот документ актуален для ветки `feature/v2-full-rework`. Для основной ветки (`main`) используйте оригинальный README.*

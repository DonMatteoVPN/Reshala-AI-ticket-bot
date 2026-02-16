# Решала Support от DonMatteo 🤖

Telegram бот для технической поддержки VPN сервиса с AI-автоответами и Mini App для менеджеров.

---

## 🚀 Возможности

- **🤖 AI-автоответы** — поддержка 5 провайдеров (Groq, OpenAI, Anthropic, Google, OpenRouter) с автоматическим failover
- **📱 Telegram Mini App** — панель управления для менеджеров с поиском пользователей и управлением тикетами
- **💬 Система тикетов** — автоматическое создание топиков в группе поддержки
  - Статусы: 💬 открыт → 🔥 эскалация → 🚨 подозрительный → 🟢 закрыт
  - Карточка клиента с данными Remnawave и Bedolaga
  - Двусторонняя связь: клиент ↔ менеджер через топик
- **📚 База знаний** — контекст для AI из редактируемых статей
- **🔍 Поиск пользователей** — интеграция с Remnawave Panel API
- **💰 Баланс и транзакции** — интеграция с Bedolaga API

---

## 📦 Быстрый старт (Docker Compose)

### 1. Клонирование репозитория

```bash
git clone https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot.git
cd Reshala-AI-ticket-bot
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

**Обязательные переменные:**

```env
# Telegram Bot (получить у @BotFather)
BOT_TOKEN=1234567890:ABCDEFghijklmnop_qrstuvwxyz123456789

# Remnawave Panel API
REMNAWAVE_API_URL=https://your-panel.example.com
REMNAWAVE_API_TOKEN=your_jwt_token_from_panel

# Группа поддержки (ID группы с топиками, начинается с -100)
SUPPORT_GROUP_ID=-1001234567890

# ID менеджеров через запятую (получить у @userinfobot)
ALLOWED_MANAGER_IDS=123456789,987654321

# URL бэкенда для Mini App
REACT_APP_BACKEND_URL=http://localhost:8001  # Для локальной разработки
# REACT_APP_BACKEND_URL=https://api.your-domain.com  # Для продакшена

# Домен Mini App (для кнопок в боте)
MINI_APP_DOMAIN=your-domain.com
MINI_APP_URL=http://localhost:3000  # Для локальной разработки

# Режим разработки (отключает проверку Telegram Init Data)
SKIP_AUTH=true  # Для локальной разработки
# SKIP_AUTH=false  # Для продакшена
```

**Опциональные переменные (Bedolaga):**

```env
BEDOLAGA_API_URL=https://bedolaga.example.com
BEDOLAGA_API_TOKEN=your_bedolaga_token
```

### 3. Запуск

```bash
docker-compose up -d --build
```

### 4. Проверка статуса

```bash
docker-compose ps
```

Должны работать 4 контейнера:
- `reshala-mongodb` — база данных
- `reshala-backend` — FastAPI сервер
- `reshala-bot` — Telegram бот
- `reshala-frontend` — React Mini App

### 5. Настройка Mini App в BotFather

1. Откройте @BotFather в Telegram
2. `/mybots` → выберите вашего бота
3. **Bot Settings** → **Menu Button** → **Configure Menu Button**
4. URL: `https://your-domain.com` (ваш домен с фронтендом)
5. Название кнопки: `Панель`

---

## 🛠 Локальная разработка (без Docker)

### Требования

- Python 3.11+
- Node.js 18+
- MongoDB 7+

### Backend

```bash
cd backend

# Установка зависимостей
pip install -r requirements.txt

# Запуск MongoDB локально (или используйте Docker)
docker run -d -p 27017:27017 --name mongodb mongo:7

# Настройка .env
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=reshala_support
export BOT_TOKEN=your_bot_token
# ... остальные переменные

# Запуск FastAPI сервера
python server.py

# Запуск бота (в отдельном терминале)
python -m bot.main
```

### Frontend

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск dev сервера
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

---

## 🚀 Продакшен установка

### Вариант 1: Docker Compose (рекомендуется)

1. **Настройте Nginx reverse proxy:**

```nginx
# /etc/nginx/sites-available/reshala-support

# Backend API
server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Frontend Mini App
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

2. **Установите SSL сертификаты (Let's Encrypt):**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.your-domain.com -d your-domain.com
```

3. **Обновите .env:**

```env
REACT_APP_BACKEND_URL=https://api.your-domain.com
MINI_APP_DOMAIN=your-domain.com
MINI_APP_URL=https://your-domain.com
SKIP_AUTH=false
```

4. **Запустите:**

```bash
docker-compose up -d --build
```

### Вариант 2: Systemd сервисы

```bash
# /etc/systemd/system/reshala-backend.service
[Unit]
Description=Reshala Backend API
After=network.target mongodb.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/reshala-support/backend
Environment="MONGO_URL=mongodb://localhost:27017"
Environment="DB_NAME=reshala_support"
EnvironmentFile=/opt/reshala-support/.env
ExecStart=/usr/bin/python3 /opt/reshala-support/backend/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# /etc/systemd/system/reshala-bot.service
[Unit]
Description=Reshala Telegram Bot
After=network.target mongodb.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/reshala-support/backend
EnvironmentFile=/opt/reshala-support/.env
ExecStart=/usr/bin/python3 -m bot.main
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable reshala-backend reshala-bot
sudo systemctl start reshala-backend reshala-bot
```

---

## 📊 Порты и URL

| Сервис | Порт | URL (локально) |
|--------|------|----------------|
| Backend API | 8001 | http://localhost:8001 |
| Frontend | 3000 | http://localhost:3000 |
| MongoDB | 27017 | mongodb://localhost:27017 |

---

## 📁 Структура проекта

```
Reshala-AI-ticket-bot/
├── backend/                    # Python backend
│   ├── bot/                    # Telegram бот
│   │   ├── main.py             # Точка входа бота
│   │   ├── handlers/           # Обработчики команд
│   │   │   ├── start.py        # /start, /help
│   │   │   ├── support_client.py  # Тикеты (клиент + менеджер)
│   │   │   ├── search.py       # Поиск пользователей
│   │   │   ├── settings.py     # Настройки
│   │   │   └── actions.py      # Действия менеджеров
│   │   └── keyboards/          # Inline клавиатуры
│   ├── services/               # Бизнес-логика
│   │   ├── ticket_service.py   # Управление тикетами
│   │   ├── telegram_service.py # Telegram API
│   │   └── ai/                 # AI провайдеры
│   │       └── manager.py      # Failover между провайдерами
│   ├── routers/                # FastAPI эндпоинты
│   │   ├── tickets.py          # API тикетов
│   │   ├── ai_router.py        # AI API
│   │   ├── settings.py         # Настройки API
│   │   ├── knowledge.py        # База знаний
│   │   ├── lookup.py           # Поиск пользователей (Remnawave)
│   │   ├── bedolaga.py         # Баланс и транзакции (Bedolaga)
│   │   └── actions.py          # Действия менеджеров
│   ├── utils/                  # Утилиты
│   │   ├── db_config.py        # MongoDB подключение
│   │   └── support_common.py   # Константы и хелперы
│   ├── server.py               # FastAPI сервер
│   ├── requirements.txt        # Python зависимости
│   └── Dockerfile              # Docker образ backend
├── frontend/                   # React Mini App
│   ├── src/
│   │   ├── App.js              # Главный компонент
│   │   ├── pages/              # Страницы
│   │   │   ├── SearchPage.js   # Поиск пользователей
│   │   │   ├── TicketsPage.js  # Активные тикеты
│   │   │   ├── KnowledgePage.js # База знаний
│   │   │   ├── SettingsPage.js # Настройки
│   │   │   └── AIProvidersPage.js # AI провайдеры
│   │   └── components/         # Компоненты
│   ├── nginx.conf              # Nginx конфигурация
│   ├── package.json            # Node.js зависимости
│   └── Dockerfile              # Docker образ frontend
├── docker-compose.yml          # Docker Compose конфигурация
├── .env.example                # Пример переменных окружения
├── .gitignore                  # Git ignore
├── README.md                   # Эта документация
└── TASKS.md                    # Задачи проекта
```

---

## 🔧 API Эндпоинты

### Настройки
- `GET /api/settings` — получить настройки
- `PUT /api/settings` — обновить настройки

### AI
- `POST /api/ai/chat` — отправить сообщение AI
- `GET /api/ai/providers` — список провайдеров
- `PUT /api/ai/provider/{name}` — обновить провайдера
- `POST /api/ai/provider/{name}/test` — тестировать ключ

### Тикеты
- `GET /api/tickets/active` — активные тикеты
- `POST /api/tickets/{id}/reply` — ответить на тикет
- `POST /api/tickets/{id}/close` — закрыть тикет

### Поиск (Remnawave)
- `POST /api/lookup` — поиск пользователя по ID/username/email

### База знаний
- `GET /api/knowledge/articles` — список статей
- `POST /api/knowledge/articles` — создать статью
- `PUT /api/knowledge/articles/{id}` — обновить
- `DELETE /api/knowledge/articles/{id}` — удалить

### Bedolaga
- `GET /api/bedolaga/balance/{telegram_id}` — баланс пользователя
- `GET /api/bedolaga/deposits/{telegram_id}` — история транзакций

### Действия (Remnawave)
- `POST /api/actions/reset-traffic` — сброс трафика
- `POST /api/actions/revoke-subscription` — перевыпуск подписки
- `POST /api/actions/toggle-user` — блокировка/разблокировка
- `POST /api/actions/remove-hwid` — удаление HWID

---

## 🤖 AI Провайдеры

Настройка через Mini App → AI Провайдеры:

| Провайдер | Модели | Получить ключ |
|-----------|--------|---------------|
| **Groq** | llama-3.1, mixtral | [console.groq.com](https://console.groq.com) |
| **OpenAI** | GPT-4o, GPT-4 | [platform.openai.com](https://platform.openai.com) |
| **Anthropic** | Claude 3 | [console.anthropic.com](https://console.anthropic.com) |
| **Google** | Gemini Pro, Flash | [aistudio.google.com](https://aistudio.google.com) |
| **OpenRouter** | Все модели | [openrouter.ai](https://openrouter.ai) |

**Автоматический failover:** если один ключ перестаёт работать (rate limit, invalid key), система автоматически переключается на следующий провайдер.

---

## 🔄 Архитектура

```
┌─────────────┐
│   Клиент    │
│  (Telegram) │
└──────┬──────┘
       │
       │ Сообщение
       ▼
┌─────────────────────────────────────┐
│       Telegram Bot (Python)         │
│  ┌───────────────────────────────┐  │
│  │  1. Создание топика в группе  │  │
│  │  2. Карточка клиента          │  │
│  │  3. AI автоответ (если вкл.)  │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────────┬───────┘
       │                      │
       │                      │ Данные клиента
       │                      ▼
       │              ┌──────────────┐
       │              │  Remnawave   │
       │              │  Panel API   │
       │              └──────────────┘
       │
       │ Сохранение тикета
       ▼
┌─────────────────┐
│    MongoDB      │
│  ┌───────────┐  │
│  │  tickets  │  │
│  │  settings │  │
│  │ knowledge │  │
│  └───────────┘  │
└─────────────────┘
       ▲
       │
       │ API запросы
       │
┌──────┴──────────────────────────────┐
│     FastAPI Backend (Python)        │
│  ┌────────────────────────────────┐ │
│  │  /api/tickets                  │ │
│  │  /api/ai/chat                  │ │
│  │  /api/lookup (Remnawave)       │ │
│  │  /api/bedolaga (Баланс)        │ │
│  └────────────────────────────────┘ │
└──────┬──────────────────────────────┘
       │
       │ HTTP запросы
       ▼
┌─────────────────┐
│  React Mini App │
│   (Frontend)    │
│  ┌───────────┐  │
│  │  Поиск    │  │
│  │  Тикеты   │  │
│  │  База     │  │
│  │  знаний   │  │
│  │  Настройки│  │
│  └───────────┘  │
└─────────────────┘
       ▲
       │
       │ Открывает
       │
┌──────┴──────┐
│  Менеджер   │
│  (Telegram) │
└─────────────┘
```

---

## 📝 Логи

```bash
# Все сервисы
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Только backend
docker-compose logs -f backend

# Последние 100 строк
docker-compose logs --tail=100 bot
```

---

## 🔄 Обновление

```bash
# Остановка
docker-compose down

# Получение обновлений
git pull

# Пересборка и запуск
docker-compose up -d --build
```

---

## 🛠 Troubleshooting

### Бот не запускается

```bash
docker-compose logs bot | grep -i "error"
```

Проверьте:
- `BOT_TOKEN` правильный (формат: `123456789:ABCdef...`)
- MongoDB запущен (`docker-compose ps`)

### Mini App показывает "Доступ запрещён"

1. Проверьте `ALLOWED_MANAGER_IDS` в `.env`
2. Узнайте свой ID: @userinfobot

### Не работает поиск пользователей

1. Проверьте `REMNAWAVE_API_URL` и `REMNAWAVE_API_TOKEN`
2. Убедитесь что API панели доступен:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" https://your-panel.example.com/api/users
```

### MongoDB не запускается

```bash
docker-compose restart mongodb
docker-compose logs mongodb
```

### Полная очистка и перезапуск

```bash
docker-compose down -v  # ⚠️ Удалит все данные!
docker-compose up -d --build
```

---

## 📄 Лицензия

MIT License

---

## 💬 Поддержка

- Telegram: @DonMatteo
- GitHub Issues: [github.com/DonMatteoVPN/Reshala-AI-ticket-bot](https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot)

---

*Обновлено: 16 февраля 2026*

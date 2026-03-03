<p align="right">
  <a href="README.md"><img src="https://cdn.jsdelivr.net/gh/hampusborgos/country-flags@main/svg/ru.svg" alt="RU" width="20" /> RU</a> |
  <a href="README.en.md"><img src="https://cdn.jsdelivr.net/gh/hampusborgos/country-flags@main/svg/us.svg" alt="EN" width="20" /> EN</a>
</p>

<a id="ru"></a>

# Решала Support от DonMatteo 🚀

![Решала Support](https://customer-assets.emergentagent.com/job_reshala-support/artifacts/hsrp3ao6_photo_2026-02-15%2002.01.49.jpeg)

<br>

### ❗️❗️❗️❗️ ОБНОВЛЕНИЯ И РАБОТЫ В ЭТОМ РЕПАЗИТОРИИ БОЛЬШЕ НЕ ВЕДУТЬСЯ! ИНТЕГРИРОВАН НА ПРЯМУЮ В БОТА БЕДОЛАГА! ❗️❗️❗️❗️

<br>

### 🎯 КОРОТКО О ГЛАВНОМ

**Решала Support** — это мой личный AI-ассистент для технической поддержки VPN сервиса, которым я делюсь с вами. Я херачил как конь, чтобы создать этот инструмент и избавить себя и вас от рутины ответов на одни и те же вопросы. Не трать время на "Привет, как дела?", пусть робот пашет.

> **Философия проста:** максимум автоматизации, минимум рутины. Я сделал это, чтобы бот работал на тебя, а не ты на него.

---

<details>
  <summary><b>✨ КЛЮЧЕВЫЕ ВОЗМОЖНОСТИ</b></summary>
  
<br>
  
Я потратил кучу времени, чтобы продумать каждый аспект технической поддержки и собрать лучшие практики в удобные модули.

---

#### 🤖 AI-автоответы: твой виртуальный саппорт
> Это святой грааль и моя главная гордость. Забудь про копипасту одних и тех же ответов. AI сам разберется с 90% вопросов клиентов.
>
> -   **💥 5 AI провайдеров:** Groq, OpenAI, Anthropic, Google, OpenRouter. Один сдох? Система автоматически переключится на следующий.
> -   **🧠 База знаний:** Загружай статьи с ответами на частые вопросы. AI сам найдет нужную информацию и ответит клиенту.
> -   **🚀 Умная эскалация:** Если AI не уверен в ответе — автоматически вызывает менеджера.
> -   **🎛️ Фильтрация мыслей:** AI думает в `<think>` тегах, но клиент видит только готовый ответ.

---

#### 💬 Система тикетов: каждому клиенту — свой топик
> Никаких общих чатов и путаницы. Каждый клиент получает свой персональный топик в группе поддержки.
>
> -   **📱 Автоматическое создание:** Клиент пишет боту → создается топик с его данными.
> -   **🎨 Статусы тикетов:** 💬 открыт → 🔥 эскалация → 🚨 подозрительный → 🟢 закрыт.
> -   **📊 Карточка клиента:** Telegram ID, UUID, баланс Bedolaga, статус подписки Remnawave — все в одном месте.
> -   **🔄 Двусторонняя связь:** Менеджер отвечает в топике → сообщение уходит клиенту в ЛС бота.

---

#### 📱 Telegram Mini App: панель управления для менеджеров
> Полноценная веб-панель прямо в Telegram. Никаких SSH и консолей.
>
> -   **🔍 Поиск пользователей:** По Telegram ID, username, email — интеграция с Remnawave Panel API.
> -   **📋 Эскалированные тикеты:** Работа с тикетами, требующими внимания менеджера (эскалированные и подозрительные).
> -   **📚 База знаний:** Создавай и редактируй статьи для AI прямо из Mini App.
> -   **⚙️ Настройки:** Управление AI провайдерами, токенами, группой поддержки.
> -   **🎯 Действия с пользователями:** Сброс трафика, перевыпуск подписки, блокировка, удаление HWID.

---

#### 🔗 Интеграция с Remnawave Panel
> Полная интеграция с панелью управления VPN сервисом.
>
> -   **👤 Данные пользователя:** UUID, статус подписки, использованный трафик, дата истечения.
> -   **🛠️ Управление:** Сброс трафика, перевыпуск подписки, блокировка/разблокировка.
> -   **🔍 Поиск:** По Telegram ID, username, email.

---

#### 💰 Интеграция с Bedolaga
> Система биллинга и балансов пользователей.
>
> -   **💳 Баланс:** Отображение баланса пользователя в рублях.
> -   **📜 История транзакций:** Последние 30 пополнений с суммами и датами.

---

#### 🎛️ Умное управление AI
> Держим AI в узде и экономим на токенах.
>
> -   **🔄 Автоматический failover:** Один ключ перестал работать? Система сама переключится на следующий.
> -   **🎯 Тестирование ключей:** Проверяй работоспособность API ключей прямо из Mini App.

</details>

---

<details>
  <summary><b>📥 УСТАНОВКА</b></summary>
 
  <br>
  
Один раз. Навсегда. Копируй, вставляй, жми Enter.
 
  <br>
  
### 🚀 Быстрый старт (Docker Compose)

#### 1. Клонирование репозитория
```bash
git clone https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot.git
cd Reshala-AI-ticket-bot
```

#### 2. Настройка переменных окружения
```bash
cp .env.example .env
nano .env
```

**Обязательные переменные:**
```env
BOT_TOKEN=1234567890:ABCDEF...
REMNAWAVE_API_URL=https://your-panel.example.com
REMNAWAVE_API_TOKEN=your_jwt_token
SUPPORT_GROUP_ID=-1001234567890
ALLOWED_MANAGER_IDS=123456789,987654321
REACT_APP_BACKEND_URL=https://api.your-domain.com
MINI_APP_DOMAIN=your-domain.com
MINI_APP_URL=https://your-domain.com
SKIP_AUTH=false
```

#### 3. Запуск
```bash
docker compose up -d --build
```

#### 4. Проверка
```bash
docker compose ps
```

Должны работать 4 контейнера: `reshala-mongodb`, `reshala-backend`, `reshala-bot`, `reshala-frontend`.

#### 5. Настройка Mini App в BotFather
1. @BotFather -> `/mybots` -> Select Bot -> **Bot Settings** -> **Menu Button**.
2. URL: `https://your-domain.com`.
3. Title: `Панель`.

### 🚀 ПРОДАКШЕН УСТАНОВКА (Production Guide)

<br>

В продакшене мы не используем `npm start` и `python main.py`. Мы используем **Docker Compose** и **Nginx** как реверс-прокси с SSL.

### 🏗️ Архитектура деплоя

1.  **Backend** крутится в Docker контейнере на порту `8001`.
2.  **Frontend** собирается в статику и раздается Nginx внутри контейнера на порту `3000`.
3.  **Внешний Nginx** (на хосте) принимает запросы на `80` и `443` портах и проксирует их:
    *   `api.your-domain.com` -> `localhost:8001` (Backend)
    *   `your-domain.com` -> `localhost:3000` (Frontend)

<br>

### 🛠️ Пошаговая инструкция

#### 1. Подготовка сервера
Установи Docker и Nginx:
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
```

#### 2. Настройка проекта
Клонируй репо и настрой `.env` как описано в "Быстром старте", но с важными изменениями для прода:

```env
# URL бэкенда (указываем внешний домен)
REACT_APP_BACKEND_URL=https://api.your-domain.com

# URL фронтенда
MINI_APP_DOMAIN=your-domain.com
MINI_APP_URL=https://your-domain.com

# Отключаем режим разработки!
SKIP_AUTH=false
```


#### 3. Настройка Nginx (Reverse Proxy)

В репозитории уже есть готовый пример конфига `nginx.conf.example`.

1. Скопируй его в nginx (убрав .example):
```bash
sudo cp nginx.conf.example /etc/nginx/sites-available/nginx.conf
sudo nano /etc/nginx/sites-available/nginx.conf
```

2. Внутри файла замени `your-domain.com` на свой домен.

Активируй конфиг и проверь ошибки:
```bash
sudo ln -s /etc/nginx/sites-available/nginx.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 4. Получение SSL (HTTPS)
Certbot сам все настроит:
```bash
sudo certbot --nginx -d your-domain.com
```

#### 5. Запуск
```bash
docker compose up -d --build
```
Теперь твой бот доступен по HTTPS, а фронтенд открывается в Telegram без ошибок.

---

### 📦 Вариант без Docker (Systemd)

Если ты олдскул и не любишь Docker, вот unit-файлы для systemd.

**Backend (`/etc/systemd/system/reshala-backend.service`):**
```ini
[Unit]
Description=Reshala Backend API
After=network.target mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Reshala-AI-ticket-bot/backend
EnvironmentFile=/opt/Reshala-AI-ticket-bot/.env
ExecStart=/usr/bin/python3 server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Bot (`/etc/systemd/system/reshala-bot.service`):**
```ini
[Unit]
Description=Reshala Telegram Bot
After=network.target mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Reshala-AI-ticket-bot/backend
EnvironmentFile=/opt/Reshala-AI-ticket-bot/.env
ExecStart=/usr/bin/python3 -m bot.main
Restart=always

[Install]
WantedBy=multi-user.target
```

Управление:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now reshala-backend reshala-bot
```

</details>

---

<details>
  <summary><b>📁 СТРУКТУРА ПРОЕКТА</b></summary>
 
  <br>

```
Reshala-AI-ticket-bot/
├── backend/                    # Python backend
│   ├── bot/                    # Telegram бот
│   ├── services/               # Бизнес-логика
│   ├── routers/                # FastAPI эндпоинты
│   └── utils/                  # Утилиты
├── frontend/                   # React Mini App
├── docker-compose.yml          # Docker Compose
└── README.md                   # Ты здесь
```

</details>

---

## 🥃 ФИНАЛЬНОЕ СЛОВО

Я сделал этот инструмент, чтобы ты мог зарабатывать, а не отвечать на одни и те же вопросы. Видишь баг? Пиши. Нравится фича? Пользуйся.

**Удачи в бизнесе.** 👊
 
  <br>
  
### КТО ЮЗАЕТ И НЕ СТАВИТ ЗВЕЗДУ, ТОТ 🐓 

  <br>
  
### Поддержать проект 💸 (на пиво и нервы):

#### Криптовалюта:
- **USDT (TRC20):** `TKPnnmtJcDM7B2uCoLQciwZmS7f8ckMNx9` 💎
- **Bitcoin (BTC):** `bc1q235adg3dd4t43jmkpqka0hj305la43md38fc0n` ₿
- **Ethereum (ETH):** `0xB42a384A7d14f8cd0f29f1984a5eA47C25d9AA48` 💠
 
[💰 Донатик через Telegram](https://t.me/tribute/app?startapp=dxrn)
 
  <br>
  
<details>
  <summary><b>🌟 История успеха</b></summary>



[![Star History Chart](https://api.star-history.com/svg?repos=DonMatteoVPN/Reshala-AI-ticket-bot&type=date&legend=top-left)](https://www.star-history.com/#DonMatteoVPN/Reshala-AI-ticket-bot&type=date&legend=top-left)
  
</details>

## 🤝 Братва (Контрибьюторы)
Респект всем, кто помогает делать этот инструмент лучше:

<a href="https://github.com/DonMatteoVPN/Reshala-AI-ticket-bot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=DonMatteoVPN/Reshala-AI-ticket-bot" />
</a>

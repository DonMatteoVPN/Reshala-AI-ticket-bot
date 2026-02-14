"""
Обработчики поддержки — Решала support от DonMatteo

Статусы тикетов:
  💬 — Открыт (новый тикет от клиента)
  🔥 — Эскалация (клиент вызвал менеджера / AI не знает ответа)
  🚨 — Подозрительный (пользователь не найден в системе)
  ✅ — Закрыт

Логика для подозрительных:
  1. AI НЕ говорит сразу что пользователя нет
  2. AI запрашивает скриншот/ссылку подписки как обычно
  3. После получения скриншота/ссылки — сообщает о проблеме
  4. Направляет в основной бот для покупки подписки
"""
import logging
import httpx
import re
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.ai.manager import AIProviderManager

logger = logging.getLogger(__name__)

TOPIC_OPEN = "💬"
TOPIC_ESCALATED = "🔥"
TOPIC_SUSPICIOUS = "🚨"
TOPIC_CLOSED = "✅"

ESCALATION_TRIGGERS = [
    "уточнить у менеджера",
    "вызываю менеджера",
    "нужна помощь менеджера",
    "не могу ответить на этот вопрос",
    "передаю менеджеру",
    "require manager",
    "нужен менеджер",
    "обратитесь к менеджеру",
]


def _get_config(context):
    config = context.application.bot_data.get("_config", {})
    if not config:
        logger.warning(f"_get_config: empty config! bot_data keys: {list(context.application.bot_data.keys())}")
    return config


def _get_db(context):
    # Получаем DB из глобальной переменной main.py, а не из bot_data (не сериализуется)
    from bot.main import db as main_db
    return main_db


def _check_access(user_id, context):
    config = _get_config(context)
    allowed = set(config.get("allowed_manager_ids", []))
    return user_id in allowed


def _client_keyboard(is_suspicious=False):
    """Клавиатура для клиента (без кнопки баланса)"""
    buttons = [
        [
            InlineKeyboardButton("🔥 Вызвать менеджера", callback_data="ask_call_manager"),
            InlineKeyboardButton("✅ Закрыть тикет", callback_data="ask_close_ticket"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _manager_keyboard(ticket_id="", is_suspicious=False):
    buttons = [[InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_ticket:{ticket_id}")]]
    if is_suspicious:
        buttons.append([InlineKeyboardButton("🗑 Убрать тикет", callback_data=f"remove_ticket:{ticket_id}")])
    return InlineKeyboardMarkup(buttons)


def _build_support_header(user, user_info: dict, balance_data: dict, is_suspicious: bool, section: str = "profile") -> str:
    """Красивый заголовок карточки клиента в топике поддержки (как в референсном боте)"""
    user_name = user.username or user.first_name or str(user.id)
    
    # Заголовок с информацией о клиенте
    header_lines = [
        f"💬 <b>Тикет поддержки</b>",
        f"",
        f"👤 <b>Клиент:</b> @{user_name}",
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>",
    ]
    
    # Баланс Bedolaga (всегда показываем если есть)
    if balance_data and balance_data.get("balance") is not None:
        header_lines.append(f"💰 <b>Баланс:</b> {balance_data.get('balance', 0):.2f} ₽")
    
    if is_suspicious:
        header_lines.append("")
        header_lines.append("⁉️ <b>Пользователь не найден в Remnawave!</b>")
        header_lines.append("<i>Проверьте данные вручную</i>")
        return "\n".join(header_lines)
    
    header_lines.append("")
    
    # Секция профиля
    if section == "profile" and user_info:
        header_lines.append("👤 <b>ПРОФИЛЬ</b>")
        header_lines.append("")
        header_lines.append(f"🆔 <b>UUID:</b> <code>{user_info.get('uuid', '—')}</code>")
        header_lines.append(f"📝 <b>Short UUID:</b> <code>{user_info.get('shortUuid', '—')}</code>")
        header_lines.append(f"🔢 <b>ID:</b> {user_info.get('id', '—')}")
        header_lines.append(f"👤 <b>Username:</b> @{user_info.get('username', '—')}")
        header_lines.append(f"📧 <b>Email:</b> {user_info.get('email') or 'Не указан'}")
        header_lines.append(f"💬 <b>Telegram ID:</b> {user_info.get('telegramId') or '—'}")
        header_lines.append(f"📊 <b>Статус:</b> {user_info.get('status', '—')}")
        header_lines.append(f"🏷️ <b>Тег:</b> {user_info.get('tag') or 'Не указан'}")
        if user_info.get('hwidDeviceLimit'):
            header_lines.append(f"📱 <b>Лимит устройств:</b> {user_info.get('hwidDeviceLimit')}")
    
    # Секция трафика
    elif section == "traffic" and user_info:
        header_lines.append("📊 <b>ТРАФИК</b>")
        header_lines.append("")
        traffic = user_info.get("userTraffic", {})
        if traffic:
            used = traffic.get("usedTrafficBytes", 0)
            lifetime = traffic.get("lifetimeUsedTrafficBytes", 0)
            limit = user_info.get("trafficLimitBytes", 0)
            header_lines.append(f"📥 <b>Использовано:</b> {_format_bytes(used)}")
            header_lines.append(f"📈 <b>Всего использовано:</b> {_format_bytes(lifetime)}")
            header_lines.append(f"📊 <b>Лимит:</b> {_format_bytes(limit) if limit > 0 else 'Безлимит'}")
            header_lines.append(f"🔄 <b>Стратегия сброса:</b> {user_info.get('trafficLimitStrategy', 'NO_RESET')}")
            if traffic.get("onlineAt"):
                header_lines.append(f"🟢 <b>Онлайн:</b> {traffic.get('onlineAt')[:19].replace('T', ' ')}")
        else:
            header_lines.append("Нет данных о трафике.")
    
    # Секция даты
    elif section == "dates" and user_info:
        header_lines.append("📅 <b>ДАТЫ</b>")
        header_lines.append("")
        expire = user_info.get("expireAt")
        if expire:
            try:
                exp_date = datetime.fromisoformat(expire.replace('Z', '+00:00'))
                days_left = (exp_date - datetime.now(timezone.utc)).days
                emoji = "✅" if days_left > 0 else "❌"
                header_lines.append(f"⏰ <b>Истекает:</b> {exp_date.strftime('%d.%m.%Y %H:%M')} ({days_left} дн.) {emoji}")
            except:
                header_lines.append(f"⏰ <b>Истекает:</b> {expire[:19]}")
        created = user_info.get("createdAt")
        if created:
            header_lines.append(f"📅 <b>Создан:</b> {created[:19].replace('T', ' ')}")
        updated = user_info.get("updatedAt")
        if updated:
            header_lines.append(f"🔄 <b>Обновлен:</b> {updated[:19].replace('T', ' ')}")
    
    # Секция подписка
    elif section == "subscription" and user_info:
        header_lines.append("🔗 <b>ПОДПИСКА</b>")
        header_lines.append("")
        expire = user_info.get("expireAt")
        if expire:
            try:
                exp_date = datetime.fromisoformat(expire.replace('Z', '+00:00'))
                days_left = (exp_date - datetime.now(timezone.utc)).days
                header_lines.append(f"📊 <b>Дней осталось:</b> {days_left}")
            except:
                pass
        traffic = user_info.get("userTraffic", {})
        if traffic:
            used = traffic.get("usedTrafficBytes", 0)
            limit = user_info.get("trafficLimitBytes", 0)
            header_lines.append(f"📥 <b>Использовано:</b> {_format_bytes(used)}")
            header_lines.append(f"📊 <b>Лимит:</b> {_format_bytes(limit) if limit > 0 else 'Безлимит'}")
        status = user_info.get("status", "—")
        is_active = status.upper() in ("ACTIVE", "ENABLED")
        header_lines.append(f"✅ <b>Активна:</b> {'Да' if is_active else 'Нет'}")
        header_lines.append(f"📊 <b>Статус:</b> {status}")
    
    # Секция устройства (HWID)
    elif section == "hwid":
        header_lines.append("📱 <b>ПРИВЯЗАННЫЕ УСТРОЙСТВА (HWID)</b>")
        header_lines.append("")
        header_lines.append("<i>Нажмите кнопку ниже для просмотра/удаления устройств</i>")
    
    return "\n".join(header_lines)


def _build_support_keyboard(client_id: int, user_info: dict, balance_data: dict, is_suspicious: bool, section: str = "profile") -> InlineKeyboardMarkup:
    """Клавиатура действий для менеджера в топике (как в референсном боте)"""
    rows = []
    
    # Навигация по секциям
    sections = [
        ("👤 Профиль", "profile"),
        ("📊 Трафик", "traffic"),
        ("📅 Даты", "dates"),
        ("🔗 Подписка", "subscription"),
        ("📱 Устройства", "hwid"),
    ]
    
    nav_row1 = []
    nav_row2 = []
    for i, (label, sec) in enumerate(sections):
        text = f"✓ {label}" if sec == section else label
        btn = InlineKeyboardButton(text, callback_data=f"sup:{client_id}:{sec}")
        if i < 3:
            nav_row1.append(btn)
        else:
            nav_row2.append(btn)
    
    rows.append(nav_row1)
    rows.append(nav_row2)
    
    # Действия если пользователь найден
    if user_info and user_info.get("uuid") and not is_suspicious:
        is_disabled = user_info.get("status", "").upper() in ("DISABLED", "INACTIVE", "BANNED")
        
        rows.append([
            InlineKeyboardButton("🔄 Сброс трафика", callback_data=f"sup_act:{client_id}:reset_traffic"),
            InlineKeyboardButton("🔗 Перевыпуск подписки", callback_data=f"sup_act:{client_id}:revoke_sub"),
        ])
        
        if is_disabled:
            rows.append([InlineKeyboardButton("🔓 Разблокировать", callback_data=f"sup_act:{client_id}:enable")])
        else:
            rows.append([InlineKeyboardButton("🔒 Заблокировать", callback_data=f"sup_act:{client_id}:disable")])
        
        rows.append([InlineKeyboardButton("🗑 Удалить все HWID", callback_data=f"sup_act:{client_id}:hwid_all")])
    
    # Кнопка баланса для менеджера (Bedolaga)
    rows.append([
        InlineKeyboardButton("💰 Баланс", callback_data=f"sup_act:{client_id}:check_balance"),
        InlineKeyboardButton("📜 Транзакции", callback_data=f"sup_act:{client_id}:bedolaga_tx"),
    ])
    
    # Управление AI и тикетом
    rows.append([
        InlineKeyboardButton("🤖 Остановить AI", callback_data=f"sup_act:{client_id}:stop_ai"),
        InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_ticket:{client_id}"),
    ])
    
    return InlineKeyboardMarkup(rows)


async def _rename_topic(bot, chat_id, thread_id, prefix, username=""):
    try:
        new_name = f"{prefix} {username}".strip()[:128]
        await bot.edit_forum_topic(chat_id=chat_id, message_thread_id=thread_id, name=new_name)
    except Exception as e:
        logger.warning("rename_topic: %s", e)


def _format_bytes(b):
    n = float(b or 0)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


async def _fetch_user_data(context, telegram_id: int) -> dict:
    """Получение полных данных пользователя из Remnawave API (как в Mini App)"""
    config = _get_config(context)
    api_url = config.get("remnawave_api_url", "").rstrip("/")
    api_token = config.get("remnawave_api_token", "")
    
    if not api_url or not api_token:
        return {"not_configured": True}
    
    headers = {"Authorization": f"Bearer {api_token}"}
    result = {}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Используем тот же эндпоинт что и Mini App
            r = await client.get(f"{api_url}/api/users/by-telegram-id/{telegram_id}", headers=headers)
            
            if r.status_code == 200:
                data = r.json()
                raw = data.get("response")
                
                # API может вернуть список или объект
                if isinstance(raw, list):
                    user = raw[0] if raw else None
                elif isinstance(raw, dict) and raw.get("uuid"):
                    user = raw
                else:
                    user = None
                
                if not user:
                    result["not_found"] = True
                    return result
                
                result["user"] = user
                uuid = user.get("uuid", "")
                
                # Получаем подписку
                if uuid:
                    try:
                        r2 = await client.get(f"{api_url}/api/subscriptions/by-uuid/{uuid}", headers=headers)
                        if r2.status_code == 200:
                            result["subscription"] = r2.json().get("response")
                    except:
                        pass
                    
                    # Получаем HWID устройства
                    try:
                        r3 = await client.get(f"{api_url}/api/hwid/devices/{uuid}", headers=headers)
                        if r3.status_code == 200:
                            devices_data = r3.json().get("response", {})
                            result["devices"] = devices_data.get("devices", []) if isinstance(devices_data, dict) else []
                    except:
                        pass
                        
            elif r.status_code == 404:
                result["not_found"] = True
            else:
                result["error"] = f"API error: {r.status_code}"
                
    except Exception as e:
        logger.warning("fetch_user_data: %s", e)
        result["error"] = str(e)
    
    return result


async def _fetch_bedolaga_balance(context, telegram_id: int) -> dict:
    """
    Получение баланса из Bedolaga API
    
    ПРАВИЛЬНАЯ РЕАЛИЗАЦИЯ:
    - Заголовок: X-API-Key (НЕ Bearer!)
    - Эндпоинт: GET /users/{telegram_id}
    """
    config = _get_config(context)
    api_url = (config.get("bedolaga_webhook_url") or config.get("bedolaga_api_url") or "").rstrip("/")
    api_token = config.get("bedolaga_web_api_token") or config.get("bedolaga_api_token") or ""
    
    if not api_url or not api_token:
        return {}
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            r = await http_client.get(
                f"{api_url}/users/{telegram_id}",
                headers={"X-API-Key": api_token}  # НЕ Bearer!
            )
            if r.status_code == 200:
                data = r.json()
                # Баланс может быть в рублях или копейках
                balance = data.get("balance_rubles")
                if balance is None:
                    balance = data.get("balance_kopeks", 0) / 100
                return {
                    "balance": balance,
                    "currency": "RUB",
                    "id": data.get("id")  # Внутренний ID для транзакций
                }
    except:
        pass
    return {}


async def _fetch_bedolaga_transactions(context, bedolaga_user_id: int) -> list:
    """
    Получение транзакций из Bedolaga API
    
    ВАЖНО: Нужен ВНУТРЕННИЙ id из Bedolaga, не telegram_id!
    """
    config = _get_config(context)
    api_url = (config.get("bedolaga_webhook_url") or config.get("bedolaga_api_url") or "").rstrip("/")
    api_token = config.get("bedolaga_web_api_token") or config.get("bedolaga_api_token") or ""
    
    if not api_url or not api_token or not bedolaga_user_id:
        return []
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            r = await http_client.get(
                f"{api_url}/transactions",
                params={"user_id": bedolaga_user_id, "limit": 30, "offset": 0},
                headers={"X-API-Key": api_token}
            )
            if r.status_code == 200:
                return r.json().get("items") or []
    except:
        pass
    return []


async def _fetch_bedolaga_deposits(context, telegram_id: int) -> list:
    """Получение истории пополнений (обёртка для совместимости)"""
    # Сначала получаем баланс чтобы узнать внутренний ID
    balance_data = await _fetch_bedolaga_balance(context, telegram_id)
    bedolaga_user_id = balance_data.get("id")
    
    if not bedolaga_user_id:
        return []
    
    # Получаем транзакции по внутреннему ID
    items = await _fetch_bedolaga_transactions(context, bedolaga_user_id)
    
    # Нормализуем формат
    deposits = []
    for item in items:
        amount = item.get("amount_rubles")
        if amount is None:
            amount = item.get("amount_kopeks", 0) / 100
        
        deposits.append({
            "amount": amount,
            "currency": "RUB",
            "type": item.get("type", ""),
            "description": item.get("description", ""),
            "created_at": item.get("created_at", ""),
        })
    
    return deposits


def _format_user_context(user_data: dict, balance_data: dict = None, has_provided_proof: bool = False, config: dict = None) -> str:
    """Форматирование данных пользователя для AI"""
    
    # Получаем переменные из конфига
    main_bot = ""
    if config:
        main_bot = config.get("main_bot_username") or ""
    
    # Пользователь не найден — специальный скрытый контекст
    if user_data.get("not_found"):
        if has_provided_proof:
            # После предоставления скриншота/ссылки — раскрываем правду
            bot_mention = f"@{main_bot}" if main_bot else "основной бот"
            return f"""## СТАТУС: ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН В СИСТЕМЕ

Пользователь прислал скриншот или ссылку подписки, но его НЕТ в нашей базе данных.

ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ТАКИМ:
"К сожалению, я проверил вашу информацию и не нашёл активной подписки в нашей системе.

Возможно, подписка была оформлена на другой аккаунт или истекла.

Для оформления новой подписки, пожалуйста, перейдите в {bot_mention}

Если вы уверены, что подписка была оформлена — нажмите кнопку 'Вызвать менеджера' и мы разберёмся в ситуации."

ВАЖНО: Будь вежлив, не обвиняй в мошенничестве."""
        else:
            # До получения скриншота — НЕ раскрываем, собираем информацию
            return """## ВНУТРЕННЯЯ ИНФОРМАЦИЯ (НЕ ГОВОРИ ПОЛЬЗОВАТЕЛЮ!)
У меня нет данных об этом пользователе в системе. Но я НЕ должен говорить ему об этом напрямую!

СТРАТЕГИЯ:
1. Веди себя как обычный техподдержка
2. Для диагностики запроси скриншот главного экрана VPN-приложения
3. Или попроси прислать ссылку подписки (обычно начинается с https:// или vless://)
4. Скажи что это нужно для диагностики проблемы
5. НЕ ГОВОРИ что пользователя нет в системе!

ПРИМЕРЫ ФРАЗ:
- "Для диагностики проблемы пришлите, пожалуйста, скриншот главного экрана вашего VPN-приложения"
- "Можете прислать ссылку вашей подписки? Это поможет мне проверить настройки"
- "Покажите скриншот — так я смогу быстрее понять в чём дело"

После получения скриншота или ссылки — система определит следующий шаг."""
    
    if user_data.get("not_configured"):
        return "## API Remnawave не настроен. Данные пользователя недоступны."
    
    if not user_data.get("user"):
        return "## Данные пользователя не найдены."
    
    user = user_data["user"]
    devices = user_data.get("devices", [])
    traffic = user.get("userTraffic", {})
    
    parts = [
        "## ДАННЫЕ ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ:",
        f"- Username: @{user.get('username', 'не указан')}",
        f"- Telegram ID: {user.get('telegramId', 'N/A')}",
        f"- UUID: {user.get('uuid', 'N/A')}",
        f"- Статус подписки: {user.get('status', 'UNKNOWN')}",
    ]
    
    expire_at = user.get("expireAt")
    if expire_at:
        try:
            exp_date = datetime.fromisoformat(expire_at.replace('Z', '+00:00'))
            days_left = (exp_date - datetime.now(timezone.utc)).days
            status_emoji = "✅" if days_left > 0 else "❌"
            parts.append(f"- Истекает: {exp_date.strftime('%d.%m.%Y')} ({days_left} дней) {status_emoji}")
        except:
            parts.append(f"- Истекает: {expire_at}")
    
    if traffic:
        used = traffic.get("usedTrafficBytes", 0)
        limit = user.get("trafficLimitBytes", 0)
        parts.append(f"- Использовано трафика: {_format_bytes(used)}")
        parts.append(f"- Лимит трафика: {_format_bytes(limit) if limit > 0 else 'Безлимит'}")
    
    hwid_limit = user.get("hwidDeviceLimit", 0)
    parts.append(f"- Устройств подключено: {len(devices)} из {hwid_limit}")
    
    if balance_data and balance_data.get("balance") is not None:
        parts.append(f"- Баланс (Bedolaga): {balance_data.get('balance', 0)} {balance_data.get('currency', 'RUB')}")
    
    return "\n".join(parts)


def _get_conversation_history(context, user_id: int, max_messages: int = 10) -> list:
    history = context.user_data.get("ai_history", [])
    return history[-max_messages:] if history else []


def _save_to_conversation(context, role: str, content: str):
    if "ai_history" not in context.user_data:
        context.user_data["ai_history"] = []
    
    context.user_data["ai_history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    if len(context.user_data["ai_history"]) > 20:
        context.user_data["ai_history"] = context.user_data["ai_history"][-20:]


def _clear_conversation(context):
    context.user_data.pop("ai_history", None)
    context.user_data.pop("user_context", None)
    context.user_data.pop("is_suspicious", None)
    context.user_data.pop("has_provided_proof", None)


def _detect_subscription_link(text: str) -> str:
    """Попытка найти ссылку подписки в тексте"""
    patterns = [
        r'(https?://[^\s]+/sub/[^\s]+)',
        r'(https?://[^\s]+subscription[^\s]*)',
        r'(vless://[^\s]+)',
        r'(vmess://[^\s]+)',
        r'(trojan://[^\s]+)',
        r'(ss://[^\s]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


async def _get_ai_reply(context, user_message: str, user_id: int, user_name: str = "") -> str:
    """Получение ответа от AI с полным контекстом"""
    db = _get_db(context)
    if db is None:
        return None

    config = _get_config(context)
    if not config.get("ai_enabled", True):
        return None

    ai_manager = AIProviderManager(db)
    service_name = config.get("service_name", "Решала support")
    
    # Получаем данные пользователя
    if "user_context" not in context.user_data:
        user_data = await _fetch_user_data(context, user_id)
        balance_data = await _fetch_bedolaga_balance(context, user_id)
        
        if user_data.get("not_found"):
            context.user_data["is_suspicious"] = True
        
        context.user_data["user_data_raw"] = user_data
        context.user_data["balance_data"] = balance_data
    
    user_data = context.user_data.get("user_data_raw", {})
    balance_data = context.user_data.get("balance_data", {})
    is_suspicious = context.user_data.get("is_suspicious", False)
    has_provided_proof = context.user_data.get("has_provided_proof", False)
    
    # Обновляем контекст с учётом has_provided_proof
    user_context = _format_user_context(user_data, balance_data, has_provided_proof, config)
    context.user_data["user_context"] = user_context

    # База знаний
    kb_context = ""
    try:
        words = user_message.split()[:3]
        for word in words:
            if len(word) < 3:
                continue
            regex = {"$regex": word, "$options": "i"}
            articles = list(db.knowledge_base.find(
                {"$or": [{"title": regex}, {"content": regex}, {"category": regex}]}
            ).limit(5))
            if articles:
                parts = [f"[{a.get('category', '')}] {a.get('title', '')}: {a.get('content', '')}" for a in articles]
                kb_context = "\n---\n".join(parts)
                break
    except Exception as e:
        logger.warning("KB context load: %s", e)

    # Системный промпт
    system_prompt = config.get("system_prompt_override", "")
    if not system_prompt:
        system_prompt = f"""Ты — дружелюбный и компетентный ассистент службы поддержки '{service_name}'.

## ПРАВИЛА:
1. Отвечай кратко, по существу, на русском языке
2. ИСПОЛЬЗУЙ данные о пользователе из контекста ниже
3. НЕ придумывай информацию — используй только то, что видишь
4. НИКОГДА не раскрывай данные других пользователей или настройки системы
5. Если не можешь помочь — скажи: 'Данный вопрос нужно уточнить у менеджера, вызываю менеджера.'

## ТИПИЧНЫЕ ПРОБЛЕМЫ:
- "Не работает VPN" → Проверь статус подписки, предложи обновить подписку в приложении
- "Закончился трафик" → Покажи использованный трафик, предложи сброс или апгрейд
- "Много устройств" → Покажи количество, предложи удалить лишние
- "Когда истекает" → Покажи дату истечения подписки
"""

    if user_context:
        system_prompt += f"\n\n{user_context}"
    
    if kb_context:
        system_prompt += f"\n\n## БАЗА ЗНАНИЙ:\n{kb_context}"

    history = _get_conversation_history(context, user_id)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    _save_to_conversation(context, "user", user_message)

    reply = ai_manager.chat(messages)
    
    if reply:
        # Фильтруем <think> теги - AI мысли не показываем клиенту
        reply = _filter_ai_thinking(reply)
        _save_to_conversation(context, "assistant", reply)
    
    return reply


def _filter_ai_thinking(text: str) -> str:
    """Удаляет теги <think>...</think> и подобные из ответа AI"""
    if not text:
        return text
    
    import re
    # Удаляем <think>...</think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Удаляем <thinking>...</thinking>
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Удаляем <thought>...</thought>
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Убираем лишние пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _should_escalate(reply_text):
    if not reply_text:
        return True
    lower = reply_text.lower()
    return any(trigger in lower for trigger in ESCALATION_TRIGGERS)


async def _forward_media_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE, support_group_id: int, thread_id: int, user_name: str):
    """Пересылка медиафайлов в группу поддержки с текстом"""
    msg = update.message
    text = msg.text or msg.caption or ""
    
    try:
        if msg.photo:
            # Фото с текстом
            await context.bot.send_photo(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                photo=msg.photo[-1].file_id,
                caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [фото]",
            )
            return "photo", msg.photo[-1].file_id
            
        elif msg.video:
            # Видео с текстом
            await context.bot.send_video(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                video=msg.video.file_id,
                caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [видео]",
            )
            return "video", msg.video.file_id
            
        elif msg.document:
            # Документ с текстом
            await context.bot.send_document(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                document=msg.document.file_id,
                caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [файл]",
            )
            return "document", msg.document.file_id
            
        elif msg.voice:
            # Голосовое сообщение
            await context.bot.send_voice(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                voice=msg.voice.file_id,
                caption=f"👤 @{user_name}",
            )
            return "voice", msg.voice.file_id
            
        elif msg.video_note:
            # Видеосообщение (кружок)
            await context.bot.send_video_note(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                video_note=msg.video_note.file_id,
            )
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"👤 @{user_name}: [видеосообщение]",
            )
            return "video_note", msg.video_note.file_id
            
        elif msg.sticker:
            # Стикер
            await context.bot.send_sticker(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                sticker=msg.sticker.file_id,
            )
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"👤 @{user_name}: [стикер]",
            )
            return "sticker", msg.sticker.file_id
            
        elif msg.audio:
            # Аудио
            await context.bot.send_audio(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                audio=msg.audio.file_id,
                caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [аудио]",
            )
            return "audio", msg.audio.file_id
            
        elif msg.animation:
            # GIF
            await context.bot.send_animation(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                animation=msg.animation.file_id,
                caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [GIF]",
            )
            return "animation", msg.animation.file_id
            
        elif text:
            # Просто текст
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"👤 @{user_name}:\n{text}",
            )
            return "text", None
            
    except Exception as e:
        logger.error(f"forward_media_to_support error: {e}")
        # Фоллбэк — просто текст
        if text:
            try:
                await context.bot.send_message(
                    chat_id=support_group_id,
                    message_thread_id=thread_id,
                    text=f"👤 @{user_name}:\n{text}\n\n[Медиафайл не удалось переслать]",
                )
            except:
                pass
    
    return None, None


async def handle_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщения от клиента."""
    config = _get_config(context)
    db = _get_db(context)
    support_group_id = config.get("support_group_id")
    service_name = config.get("service_name", "Решала support")
    
    logger.info(f"handle_client_message: support_group_id={support_group_id}")
    
    if not support_group_id:
        logger.warning("handle_client_message: support_group_id not set!")
        await update.message.reply_text(f"Поддержка {service_name} временно недоступна.")
        return

    user = update.effective_user
    user_id = user.id
    user_name = user.username or user.first_name or str(user_id)
    text = update.message.text or update.message.caption or ""
    has_media = bool(update.message.photo or update.message.video or update.message.document or 
                     update.message.voice or update.message.video_note or update.message.sticker or
                     update.message.audio or update.message.animation)

    # Инициализируем маппинги если нет
    if "support_topic_by_client" not in context.application.bot_data:
        context.application.bot_data["support_topic_by_client"] = {}
    if "support_thread_to_client" not in context.application.bot_data:
        context.application.bot_data["support_thread_to_client"] = {}
    if "support_clients" not in context.application.bot_data:
        context.application.bot_data["support_clients"] = {}
    
    topic_by_client = context.application.bot_data["support_topic_by_client"]
    thread_to_client = context.application.bot_data["support_thread_to_client"]
    support_clients = context.application.bot_data["support_clients"]
    
    # Проверяем существующий топик
    existing = topic_by_client.get(user_id)
    thread_id = existing.get("message_thread_id") if existing else None

    # Создаём тикет если нет
    if not thread_id:
        user_data = await _fetch_user_data(context, user_id)
        balance_data = await _fetch_bedolaga_balance(context, user_id)
        
        is_suspicious = user_data.get("not_found", False)
        context.user_data["is_suspicious"] = is_suspicious
        context.user_data["user_data_raw"] = user_data
        context.user_data["balance_data"] = balance_data
        context.user_data["has_provided_proof"] = False
        context.user_data["user_context"] = _format_user_context(user_data, balance_data, False, config)
        
        # Всегда 💬 при создании (подозрительность определяем внутренне)
        topic_prefix = TOPIC_OPEN  # 💬
        topic_name = f"{topic_prefix} @{user_name}"
        
        try:
            topic = await context.bot.create_forum_topic(
                chat_id=support_group_id,
                name=topic_name[:128],
            )
            thread_id = topic.message_thread_id
            context.user_data["topic_id"] = thread_id
            
            # Сохраняем маппинги
            topic_by_client[user_id] = {
                "chat_id": support_group_id,
                "message_thread_id": thread_id,
                "topic_name": topic_name,
            }
            thread_to_client[(support_group_id, thread_id)] = user_id
            
            # Сохраняем данные клиента для карточки
            user_info = user_data.get("user", {})
            support_clients[user_id] = {
                "user": user_info,
                "subscription": user_data.get("subscription"),
                "hwid_devices": user_data.get("devices", []),
                "bedolaga_user": balance_data,
                "is_suspicious": is_suspicious,
            }
            
            # Красивая карточка профиля
            header = _build_support_header(user, user_info, balance_data, is_suspicious)
            
            # Отправляем карточку в топик
            card_msg = await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=header,
                parse_mode="HTML",
                reply_markup=_build_support_keyboard(user_id, user_info, balance_data, is_suspicious),
            )
            
            # Закрепляем карточку в топике
            try:
                await context.bot.pin_chat_message(
                    chat_id=support_group_id,
                    message_id=card_msg.message_id,
                )
            except Exception as e:
                logger.debug("pin message: %s", e)
            
            # Создаём тикет в БД
            if db is not None:
                db.tickets.insert_one({
                    "client_id": user_id,
                    "client_name": user.first_name or user_name,
                    "client_username": user.username,
                    "topic_id": thread_id,
                    "status": "suspicious" if is_suspicious else "open",
                    "reason": "Пользователь не найден в системе" if is_suspicious else None,
                    "user_data": user_data if not is_suspicious else None,
                    "last_messages": [],
                    "history": [],
                    "attachments": [],
                    "created_at": datetime.now(timezone.utc),
                    "is_removed": False,
                })
                
        except Exception as e:
            logger.error("create topic: %s", e)
            await update.message.reply_text("Ошибка создания тикета. Попробуйте позже.")
            return

    is_suspicious = context.user_data.get("is_suspicious", False)
    has_provided_proof = context.user_data.get("has_provided_proof", False)
    
    # Проверяем получение "доказательства" (скриншот или ссылка)
    proof_received = False
    
    # Проверяем ссылку в тексте
    if text:
        sub_link = _detect_subscription_link(text)
        if sub_link:
            proof_received = True
            if db is not None:
                db.tickets.update_one(
                    {"topic_id": thread_id},
                    {"$push": {"attachments": {"type": "subscription_link", "value": sub_link, "added_at": datetime.now(timezone.utc).isoformat()}}}
                )
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"📎 <b>Получена ссылка подписки:</b>\n<code>{sub_link}</code>",
                parse_mode="HTML",
            )
    
    # Проверяем фото/скриншот
    if update.message.photo:
        proof_received = True
        if db is not None:
            db.tickets.update_one(
                {"topic_id": thread_id},
                {"$push": {"attachments": {"type": "photo", "file_id": update.message.photo[-1].file_id, "added_at": datetime.now(timezone.utc).isoformat()}}}
            )
        if is_suspicious and not has_provided_proof:
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text="📷 <b>Получен скриншот от подозрительного пользователя</b>",
                parse_mode="HTML",
            )
    
    # Обновляем флаг если получили доказательство
    if is_suspicious and proof_received and not has_provided_proof:
        context.user_data["has_provided_proof"] = True
        has_provided_proof = True
        # Обновляем контекст для AI
        user_data = context.user_data.get("user_data_raw", {})
        balance_data = context.user_data.get("balance_data", {})
        context.user_data["user_context"] = _format_user_context(user_data, balance_data, True, config)
        
        # Переименовываем топик на 🚨 для подозрительных
        await _rename_topic(context.bot, support_group_id, thread_id, TOPIC_SUSPICIOUS, f"@{user_name}")
        await context.bot.send_message(
            chat_id=support_group_id,
            message_thread_id=thread_id,
            text=f"🚨 <b>ВНИМАНИЕ!</b> Пользователь @{user_name} не найден в Remnawave, но предоставил скриншот/ссылку.\nТребуется проверка менеджером.",
            parse_mode="HTML",
        )
        if db is not None:
            db.tickets.update_one(
                {"topic_id": thread_id}, 
                {"$set": {"status": "suspicious", "reason": "Пользователь не найден в системе", "escalated_at": datetime.now(timezone.utc)}}
            )

    # Пересылаем в группу поддержки
    media_type, file_id = await _forward_media_to_support(update, context, support_group_id, thread_id, user_name)

    # AI ответ (только если есть текст или это подозрительный после скриншота)
    should_reply = text.strip() or (is_suspicious and has_provided_proof and proof_received)
    
    if should_reply:
        ai_message = text if text.strip() else "[Пользователь прислал скриншот]"
        ai_reply = await _get_ai_reply(context, ai_message, user_id, user_name)
        
        if ai_reply:
            if _should_escalate(ai_reply):
                await update.message.reply_text(ai_reply, reply_markup=_client_keyboard(is_suspicious))
                if not is_suspicious:
                    await _rename_topic(context.bot, support_group_id, thread_id, TOPIC_ESCALATED, f"@{user_name}")
                await context.bot.send_message(
                    chat_id=support_group_id,
                    message_thread_id=thread_id,
                    text=f"🔥 <b>Эскалация</b>: AI не смог ответить.\nAI: {ai_reply[:300]}",
                    parse_mode="HTML",
                )
                if db is not None and not is_suspicious:
                    db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "escalated", "escalated_at": datetime.now(timezone.utc)}})
            else:
                await update.message.reply_text(ai_reply, reply_markup=_client_keyboard(is_suspicious))
                await context.bot.send_message(
                    chat_id=support_group_id,
                    message_thread_id=thread_id,
                    text=f"🤖 AI:\n{ai_reply[:3000]}",
                )
        else:
            await update.message.reply_text(
                "Ваше сообщение принято. Ожидайте ответа менеджера.",
                reply_markup=_client_keyboard(is_suspicious),
            )
    elif has_media and not text:
        # Только медиа без текста — подтверждаем получение
        await update.message.reply_text(
            "Получил ваш файл. Чем могу помочь?",
            reply_markup=_client_keyboard(is_suspicious),
        )


async def handle_support_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка сообщения от менеджера в топике группы поддержки.
    Пересылает ответ клиенту в ЛС бота.
    """
    if not update.message or not update.message.message_thread_id:
        return

    thread_id = update.message.message_thread_id
    text = update.message.text or update.message.caption or ""
    sender = update.effective_user
    chat_id = update.effective_chat.id
    
    # Проверяем доступ менеджера
    if not _check_access(sender.id, context):
        return
    
    # Игнорируем сообщения от ботов
    if getattr(sender, "is_bot", False):
        return
    
    db = _get_db(context)
    config = _get_config(context)
    support_group_id = config.get("support_group_id")
    
    # Проверяем что это сообщение в группе поддержки
    if chat_id != support_group_id:
        return
    
    # Сначала пробуем найти клиента через маппинг (быстрее)
    thread_to_client = context.application.bot_data.get("support_thread_to_client") or {}
    client_id = thread_to_client.get((chat_id, thread_id))
    
    # Если нет в маппинге — ищем в БД
    if not client_id and db:
        ticket = db.tickets.find_one({"topic_id": thread_id, "is_removed": {"$ne": True}})
        if ticket:
            client_id = ticket.get("client_id")
            # Восстанавливаем маппинг
            if client_id:
                if "support_thread_to_client" not in context.application.bot_data:
                    context.application.bot_data["support_thread_to_client"] = {}
                context.application.bot_data["support_thread_to_client"][(chat_id, thread_id)] = client_id
    
    if not client_id:
        logger.debug(f"Клиент для topic_id={thread_id} не найден")
        return
    
    # Определяем тип контента
    msg = update.message
    manager_name = sender.first_name or "Поддержка"
    prefix = f"💬 <b>Поддержка</b> ({manager_name}):"
    
    sent = False
    error_msg = None
    
    try:
        if msg.photo:
            caption = f"{prefix}\n\n{text}" if text else prefix
            await context.bot.send_photo(
                chat_id=client_id,
                photo=msg.photo[-1].file_id,
                caption=caption,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.video:
            caption = f"{prefix}\n\n{text}" if text else prefix
            await context.bot.send_video(
                chat_id=client_id,
                video=msg.video.file_id,
                caption=caption,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.document:
            caption = f"{prefix}\n\n{text}" if text else prefix
            await context.bot.send_document(
                chat_id=client_id,
                document=msg.document.file_id,
                caption=caption,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.voice:
            await context.bot.send_voice(
                chat_id=client_id,
                voice=msg.voice.file_id,
                caption=prefix,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.video_note:
            await context.bot.send_video_note(
                chat_id=client_id,
                video_note=msg.video_note.file_id,
            )
            await context.bot.send_message(
                chat_id=client_id,
                text=prefix,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.sticker:
            await context.bot.send_sticker(
                chat_id=client_id,
                sticker=msg.sticker.file_id,
            )
            await context.bot.send_message(
                chat_id=client_id,
                text=prefix,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.audio:
            caption = f"{prefix}\n\n{text}" if text else prefix
            await context.bot.send_audio(
                chat_id=client_id,
                audio=msg.audio.file_id,
                caption=caption,
                parse_mode="HTML",
            )
            sent = True
            
        elif msg.animation:
            caption = f"{prefix}\n\n{text}" if text else prefix
            await context.bot.send_animation(
                chat_id=client_id,
                animation=msg.animation.file_id,
                caption=caption,
                parse_mode="HTML",
            )
            sent = True
            
        elif text:
            # Просто текст
            await context.bot.send_message(
                chat_id=client_id,
                text=f"{prefix}\n\n{text}",
                parse_mode="HTML",
            )
            sent = True
            
    except Exception as e:
        logger.error(f"Ошибка пересылки сообщения клиенту {client_id}: {e}")
        # Уведомляем менеджера об ошибке
        try:
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"⚠️ Не удалось отправить сообщение клиенту: {str(e)[:100]}",
            )
        except:
            pass
        return
    
    # Сохраняем ответ менеджера в историю тикета
    if sent and db:
        reply_record = {
            "role": "manager",
            "name": manager_name,
            "content": text or "[медиафайл]",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        db.tickets.update_one(
            {"topic_id": thread_id},
            {
                "$push": {
                    "last_messages": {"$each": [reply_record], "$slice": -20},
                    "history": reply_record
                },
                "$set": {"last_reply_at": datetime.now(timezone.utc)}
            }
        )
        
        # Визуальное подтверждение — реакция на сообщение
        try:
            await msg.set_reaction(reaction="👍")
        except Exception:
            pass  # Реакции могут быть отключены


async def check_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка баланса и истории пополнений через Bedolaga."""
    query = update.callback_query
    await query.answer("Проверяю баланс...")
    
    user_id = query.from_user.id
    
    # Получаем баланс и историю
    balance_data = await _fetch_bedolaga_balance(context, user_id)
    deposits = await _fetch_bedolaga_deposits(context, user_id)
    
    if not balance_data:
        await query.message.reply_text("❌ Bedolaga API не настроен или недоступен.")
        return
    
    if balance_data.get("balance") is None:
        await query.message.reply_text("💰 Баланс не найден. Возможно, вы ещё не пополняли.")
        return
    
    # Формируем сообщение
    text_parts = [
        f"💰 <b>Ваш баланс:</b> {balance_data.get('balance', 0)} {balance_data.get('currency', 'RUB')}"
    ]
    
    # Добавляем историю пополнений
    if deposits:
        text_parts.append("\n📋 <b>История пополнений:</b>")
        for i, d in enumerate(deposits[:5]):  # Показываем последние 5
            amount = d.get('amount', 0)
            currency = d.get('currency', 'RUB')
            date = d.get('created_at') or d.get('date', '')
            method = d.get('method', '')
            
            if date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    date_str = dt.strftime('%d.%m.%Y %H:%M')
                except:
                    date_str = date[:10]
            else:
                date_str = ''
            
            line = f"• <b>+{amount} {currency}</b>"
            if date_str:
                line += f" — {date_str}"
            if method:
                line += f" ({method})"
            
            text_parts.append(line)
        
        if len(deposits) > 5:
            text_parts.append(f"\n<i>...и ещё {len(deposits) - 5} пополнений</i>")
    else:
        text_parts.append("\n<i>История пополнений пуста</i>")
    
    await query.message.reply_text(
        "\n".join(text_parts),
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════
#                    ПОДТВЕРЖДЕНИЯ ДЛЯ КЛИЕНТОВ
# ═══════════════════════════════════════════════════════════════════════════

def _confirm_client_keyboard(action: str):
    """Клавиатура подтверждения для клиентов."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=action),
            InlineKeyboardButton("❌ Нет", callback_data="cancel_client_action"),
        ]
    ])


async def ask_call_manager_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос подтверждения вызова менеджера."""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "🔥 <b>Вызов менеджера</b>\n\nВы уверены, что хотите вызвать менеджера?",
        parse_mode="HTML",
        reply_markup=_confirm_client_keyboard("call_manager")
    )


async def ask_close_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос подтверждения закрытия тикета."""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "✅ <b>Закрытие тикета</b>\n\nВы уверены, что хотите закрыть тикет?\nЕсли возникнут новые вопросы, просто напишите снова.",
        parse_mode="HTML",
        reply_markup=_confirm_client_keyboard("client_close_ticket")
    )


async def cancel_client_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия клиентом."""
    query = update.callback_query
    await query.answer("Действие отменено")
    await query.edit_message_text("❌ Действие отменено.")


async def call_manager_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Клиент вызывает менеджера."""
    query = update.callback_query
    await query.answer("Менеджер вызван!")

    config = _get_config(context)
    db = _get_db(context)
    support_group_id = config.get("support_group_id")
    thread_id = context.user_data.get("topic_id")

    if support_group_id and thread_id:
        user_name = query.from_user.username or query.from_user.first_name or str(query.from_user.id)
        
        # Всегда переименовываем на 🔥 при вызове менеджера
        await _rename_topic(context.bot, support_group_id, thread_id, TOPIC_ESCALATED, f"@{user_name}")
        
        await context.bot.send_message(
            chat_id=support_group_id,
            message_thread_id=thread_id,
            text=f"🔥 <b>Клиент @{user_name} вызывает менеджера!</b>",
            parse_mode="HTML",
        )
        
        if db is not None:
            db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "escalated", "escalated_at": datetime.now(timezone.utc)}})

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Менеджер подключается к чату. Ожидайте.")


async def client_close_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Клиент закрывает тикет."""
    query = update.callback_query
    await query.answer("Тикет закрыт.")

    config = _get_config(context)
    db = _get_db(context)
    support_group_id = config.get("support_group_id")
    thread_id = context.user_data.get("topic_id")
    is_suspicious = context.user_data.get("is_suspicious", False)
    user_id = query.from_user.id

    if support_group_id and thread_id:
        user_name = query.from_user.username or query.from_user.first_name or str(user_id)
        
        # Всегда переименовываем на ✅ при закрытии
        await _rename_topic(context.bot, support_group_id, thread_id, TOPIC_CLOSED, f"@{user_name}")
        
        if is_suspicious:
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"✅ Клиент @{user_name} закрыл чат.\n\n⚠️ <b>Тикет остаётся для проверки менеджером!</b>",
                parse_mode="HTML",
            )
            if db is not None:
                db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}})
        else:
            try:
                await context.bot.close_forum_topic(chat_id=support_group_id, message_thread_id=thread_id)
            except Exception as e:
                logger.warning("close topic: %s", e)
            await context.bot.send_message(
                chat_id=support_group_id,
                message_thread_id=thread_id,
                text=f"✅ Тикет закрыт клиентом @{user_name}.",
            )
            if db is not None:
                db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc), "is_removed": True}})

    # Очищаем маппинги
    topic_by_client = context.application.bot_data.get("support_topic_by_client", {})
    thread_to_client = context.application.bot_data.get("support_thread_to_client", {})
    topic_by_client.pop(user_id, None)
    thread_to_client.pop((support_group_id, thread_id), None)
    
    _clear_conversation(context)
    context.user_data.pop("topic_id", None)
    
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Тикет закрыт. Спасибо за обращение! Если нужна помощь — напишите снова.")


async def close_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Менеджер закрывает тикет."""
    query = update.callback_query
    data = query.data or ""
    
    # Поддержка обоих форматов: close_ticket:thread_id и close_ticket:client_id
    ticket_id = data.replace("close_ticket:", "")

    await query.answer("Тикет закрыт.")

    config = _get_config(context)
    db = _get_db(context)
    support_group_id = config.get("support_group_id")

    thread_id = None
    client_id = None
    
    if support_group_id and ticket_id:
        try:
            parsed_id = int(ticket_id)
            
            # Определяем что это — thread_id или client_id
            # client_id обычно больше 1000000, thread_id меньше
            if parsed_id > 1000000:
                # Это client_id — ищем thread_id
                client_id = parsed_id
                topic_by_client = context.application.bot_data.get("support_topic_by_client", {})
                topic_data = topic_by_client.get(client_id)
                if topic_data:
                    thread_id = topic_data.get("message_thread_id")
                # Также ищем в БД
                if not thread_id and db:
                    ticket = db.tickets.find_one({"client_id": client_id, "is_removed": {"$ne": True}})
                    if ticket:
                        thread_id = ticket.get("topic_id")
            else:
                thread_id = parsed_id
                # Ищем client_id по thread_id
                thread_to_client = context.application.bot_data.get("support_thread_to_client", {})
                client_id = thread_to_client.get((support_group_id, thread_id))
                if not client_id and db:
                    ticket = db.tickets.find_one({"topic_id": thread_id})
                    if ticket:
                        client_id = ticket.get("client_id")
            
            if thread_id:
                await _rename_topic(context.bot, support_group_id, thread_id, TOPIC_CLOSED)
                try:
                    await context.bot.close_forum_topic(chat_id=support_group_id, message_thread_id=thread_id)
                except Exception as e:
                    logger.warning("close_forum_topic: %s", e)
                
                if db is not None:
                    db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}})
            
            # Уведомляем клиента
            if client_id:
                try:
                    await context.bot.send_message(
                        chat_id=client_id,
                        text="✅ Тикет поддержки закрыт.\n\nЕсли нужна помощь — напишите снова.",
                    )
                except Exception as e:
                    logger.debug("notify client: %s", e)
            
            # Очищаем маппинги
            if client_id:
                topic_by_client = context.application.bot_data.get("support_topic_by_client", {})
                topic_by_client.pop(client_id, None)
            if thread_id:
                thread_to_client = context.application.bot_data.get("support_thread_to_client", {})
                thread_to_client.pop((support_group_id, thread_id), None)
                
        except Exception as e:
            logger.warning("manager close ticket: %s", e)

    await query.edit_message_reply_markup(reply_markup=None)


async def remove_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Менеджер убирает тикет."""
    query = update.callback_query
    data = query.data or ""
    ticket_id = data.replace("remove_ticket:", "")

    await query.answer("Тикет удалён.")

    db = _get_db(context)
    config = _get_config(context)
    support_group_id = config.get("support_group_id")

    if db is not None and ticket_id:
        try:
            thread_id = int(ticket_id)
            db.tickets.update_one({"topic_id": thread_id}, {"$set": {"is_removed": True, "removed_at": datetime.now(timezone.utc)}})
            
            try:
                await context.bot.close_forum_topic(chat_id=support_group_id, message_thread_id=thread_id)
            except:
                pass
        except Exception as e:
            logger.warning("remove ticket: %s", e)

    await query.edit_message_reply_markup(reply_markup=None)


async def support_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение секций в карточке клиента (sup:client_id:section)."""
    query = update.callback_query
    data = query.data or ""
    
    if not data.startswith("sup:") or data.startswith("sup_act:"):
        return
    
    # Проверяем доступ
    if not _check_access(query.from_user.id, context):
        await query.answer("Доступ запрещён.", show_alert=True)
        return
    
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    
    try:
        client_id = int(parts[1])
        section = parts[2]
    except ValueError:
        await query.answer()
        return
    
    await query.answer(f"Секция: {section}")
    
    # Получаем данные клиента
    support_clients = context.application.bot_data.get("support_clients", {})
    client_data = support_clients.get(client_id, {})
    
    user_info = client_data.get("user", {})
    balance_data = client_data.get("bedolaga_user", {})
    is_suspicious = client_data.get("is_suspicious", False)
    
    # Создаём фейковый user объект для _build_support_header
    class FakeUser:
        def __init__(self, cid, uinfo):
            self.id = cid
            self.username = uinfo.get("username") if uinfo else None
            self.first_name = uinfo.get("username") or str(cid)
    
    fake_user = FakeUser(client_id, user_info)
    
    # Обновляем сообщение с новой секцией
    new_text = _build_support_header(fake_user, user_info, balance_data, is_suspicious, section)
    new_keyboard = _build_support_keyboard(client_id, user_info, balance_data, is_suspicious, section)
    
    try:
        await query.edit_message_text(
            text=new_text,
            parse_mode="HTML",
            reply_markup=new_keyboard,
        )
    except Exception as e:
        logger.debug(f"support_nav_callback edit error: {e}")


async def support_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий менеджера из карточки клиента (sup_act:client_id:action)."""
    query = update.callback_query
    data = query.data or ""
    
    if not data.startswith("sup_act:"):
        return
    
    # Проверяем доступ
    if not _check_access(query.from_user.id, context):
        await query.answer("Доступ запрещён.", show_alert=True)
        return
    
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    
    try:
        client_id = int(parts[1])
        action = parts[2]
    except ValueError:
        await query.answer()
        return
    
    db = _get_db(context)
    config = _get_config(context)
    support_clients = context.application.bot_data.get("support_clients", {})
    client_data = support_clients.get(client_id, {})
    
    user_info = client_data.get("user", {})
    user_uuid = user_info.get("uuid") if user_info else None
    
    # Действия не требующие user_uuid
    if action == "stop_ai":
        if "support_client_wants_manager" not in context.application.bot_data:
            context.application.bot_data["support_client_wants_manager"] = set()
        context.application.bot_data["support_client_wants_manager"].add(client_id)
        await query.answer("AI остановлен. Отвечайте в чате сами.")
        return
    
    if action == "start_ai":
        want_mgr = context.application.bot_data.get("support_client_wants_manager")
        if isinstance(want_mgr, set):
            want_mgr.discard(client_id)
        await query.answer("AI включён снова.")
        return
    
    if action == "bedolaga_tx":
        await query.answer("Загрузка транзакций...")
        bedolaga_user = client_data.get("bedolaga_user", {})
        bedolaga_id = bedolaga_user.get("id") if bedolaga_user else None
        
        if not bedolaga_id:
            # Пробуем получить заново
            balance_data = await _fetch_bedolaga_balance(context, client_id)
            bedolaga_id = balance_data.get("id") if balance_data else None
        
        if not bedolaga_id:
            await query.message.reply_text("Нет данных Bedolaga для этого клиента.")
            return
        
        transactions = await _fetch_bedolaga_transactions(context, int(bedolaga_id))
        
        if not transactions:
            await query.message.reply_text("📜 <b>Транзакции</b>\n\nНет транзакций.", parse_mode="HTML")
            return
        
        lines = ["📜 <b>Транзакции (Bedolaga)</b>\n"]
        for t in transactions[:15]:
            amount = t.get("amount_rubles") or (t.get("amount_kopeks", 0) / 100)
            typ = t.get("type") or "—"
            desc = (t.get("description") or "—")[:50]
            created = (t.get("created_at") or "—")[:19].replace("T", " ")
            lines.append(f"• {created} · {amount:.2f} ₽ · {typ}\n  {desc}")
        
        await query.message.reply_text("\n".join(lines), parse_mode="HTML")
        return
    
    if action == "check_balance":
        await query.answer("Проверка баланса...")
        balance_data = await _fetch_bedolaga_balance(context, client_id)
        
        if balance_data and balance_data.get("balance") is not None:
            balance = balance_data.get("balance", 0)
            await query.message.reply_text(
                f"💰 <b>Баланс Bedolaga</b>\n\n"
                f"Telegram ID: <code>{client_id}</code>\n"
                f"Баланс: <b>{balance:.2f} ₽</b>",
                parse_mode="HTML"
            )
        else:
            await query.message.reply_text("❌ Не удалось получить баланс. Проверьте настройки Bedolaga API.")
        return
    
    # Действия требующие user_uuid
    if not user_uuid:
        await query.answer("Пользователь не найден в Remnawave.", show_alert=True)
        return
    
    api_url = config.get("remnawave_api_url", "")
    api_token = config.get("remnawave_api_token", "")
    
    if not api_url or not api_token:
        await query.answer("Remnawave API не настроен.", show_alert=True)
        return
    
    result_msg = ""
    
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            headers = {"Authorization": f"Bearer {api_token}"}
            
            if action == "reset_traffic":
                await query.answer("Сброс трафика...")
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/reset-traffic", headers=headers)
                result_msg = "✅ Трафик сброшен." if r.status_code == 200 else f"❌ Ошибка: {r.status_code}"
                
            elif action == "revoke_sub":
                await query.answer("Перевыпуск подписки...")
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/revoke", json={}, headers=headers)
                result_msg = "✅ Подписка перевыпущена." if r.status_code == 200 else f"❌ Ошибка: {r.status_code}"
                
            elif action == "disable":
                await query.answer("Блокировка...")
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/disable", json={}, headers=headers)
                result_msg = "🔒 Пользователь заблокирован." if r.status_code == 200 else f"❌ Ошибка: {r.status_code}"
                
            elif action == "enable":
                await query.answer("Разблокировка...")
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/enable", json={}, headers=headers)
                result_msg = "🔓 Пользователь разблокирован." if r.status_code == 200 else f"❌ Ошибка: {r.status_code}"
                
            elif action == "hwid_all":
                await query.answer("Удаление устройств...")
                r = await http.post(f"{api_url}/api/hwid/devices/delete-all", json={"userUuid": user_uuid}, headers=headers)
                result_msg = "🗑 Все устройства удалены." if r.status_code == 200 else f"❌ Ошибка: {r.status_code}"
            
            else:
                await query.answer()
                return
        
        if result_msg:
            await query.message.reply_text(result_msg)
            
    except Exception as e:
        logger.error(f"support_action error: {e}")
        await query.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")


async def dispatch_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распределение входящих сообщений."""
    if not update.message:
        return

    user_id = update.effective_user.id
    logger.info(f"dispatch_message: user_id={user_id}, text={update.message.text[:50] if update.message.text else '[media]'}")

    if _check_access(user_id, context):
        logger.info(f"dispatch_message: user {user_id} is manager, calling handle_message")
        from bot.handlers.search import handle_message
        handled = await handle_message(update, context)
        if handled:
            return

    config = _get_config(context)
    if config.get("support_group_id"):
        logger.info(f"dispatch_message: user {user_id} is client, calling handle_client_message")
        await handle_client_message(update, context)
    else:
        logger.warning("dispatch_message: support_group_id not configured!")

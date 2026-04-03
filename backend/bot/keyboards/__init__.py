from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from utils.db_config import get_settings

def client_keyboard(is_suspicious=False):
    buttons = [
        [
            InlineKeyboardButton("🔥 Вызвать менеджера", callback_data="ask_call_manager"),
            InlineKeyboardButton("✅ Закрыть тикет", callback_data="ask_close_ticket"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def confirm_client_keyboard(action: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=action),
            InlineKeyboardButton("❌ Нет", callback_data="cancel_client_action"),
        ]
    ])

def manager_keyboard(ticket_id="", is_suspicious=False):
    buttons = [[InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_ticket:{ticket_id}")]]
    if is_suspicious:
        buttons.append([InlineKeyboardButton("🗑 Убрать тикет", callback_data=f"remove_ticket:{ticket_id}")])
    return InlineKeyboardMarkup(buttons)

def build_support_keyboard(client_id, user_info=None, balance_data=None, is_suspicious=False, section="profile"):
    """
    Клавиатура в топике поддержки для менеджера.
    Все кнопки управления открывают MiniApp с нужным client_id.
    """
    config = get_settings()
    mini_app_url = config.get("miniapp_url", "") or (f"https://{config.get('mini_app_domain', '')}" if config.get('mini_app_domain') else "")
    
    rows = []
    
    # Навигационные секции — теперь открывают MiniApp с параметром
    sections = [
        ("👤 Профиль", "profile"),
        ("📊 Трафик", "traffic"),
        ("📅 Даты", "dates"),
        ("🔗 Подписка", "subscription"),
        ("📱 Устройства", "hwid"),
        ("💰 Баланс", "balance"),
    ]
    
    if mini_app_url and mini_app_url.startswith("https://"):
        # Первая строка — открыть MiniApp на карточке пользователя
        miniapp_client_url = f"{mini_app_url.rstrip('/')}/?client_id={client_id}"
        try:
            rows.append([
                InlineKeyboardButton(
                    "📱 Открыть карточку пользователя",
                    web_app=WebAppInfo(url=miniapp_client_url)
                )
            ])
        except Exception:
            rows.append([
                InlineKeyboardButton("📱 Открыть карточку", url=miniapp_client_url)
            ])
        
        # Строка секций как URL-кнопки в MiniApp
        nav_row = []
        for label, sec in sections[:3]:
            sec_url = f"{mini_app_url.rstrip('/')}/?client_id={client_id}&section={sec}"
            try:
                nav_row.append(InlineKeyboardButton(label, web_app=WebAppInfo(url=sec_url)))
            except Exception:
                nav_row.append(InlineKeyboardButton(label, callback_data=f"sup:{client_id}:{sec}"))
        if nav_row:
            rows.append(nav_row)
        
        nav_row2 = []
        for label, sec in sections[3:]:
            sec_url = f"{mini_app_url.rstrip('/')}/?client_id={client_id}&section={sec}"
            try:
                nav_row2.append(InlineKeyboardButton(label, web_app=WebAppInfo(url=sec_url)))
            except Exception:
                nav_row2.append(InlineKeyboardButton(label, callback_data=f"sup:{client_id}:{sec}"))
        if nav_row2:
            rows.append(nav_row2)
    else:
        # Fallback: старые callback кнопки
        sections_all = [
            ("👤 Профиль", "profile"),
            ("📊 Трафик", "traffic"),
            ("📅 Даты", "dates"),
            ("🔗 Подписка", "subscription"),
            ("📱 Устройства", "hwid"),
            ("💰 Баланс", "balance"),
            ("📜 Транзакции", "transactions"),
        ]
        nav_row1, nav_row2, nav_row3 = [], [], []
        for i, (label, sec) in enumerate(sections_all):
            text = f"✓ {label}" if sec == section else label
            btn = InlineKeyboardButton(text, callback_data=f"sup:{client_id}:{sec}")
            if i < 3: nav_row1.append(btn)
            elif i < 5: nav_row2.append(btn)
            else: nav_row3.append(btn)
        if nav_row1: rows.append(nav_row1)
        if nav_row2: rows.append(nav_row2)
        if nav_row3: rows.append(nav_row3)
    
    # Управление AI и тикетом — через callback (работает всегда)
    rows.append([
        InlineKeyboardButton("🤖 AI ВКЛ", callback_data=f"sup_act:{client_id}:start_ai"),
        InlineKeyboardButton("🤖 AI ВЫКЛ", callback_data=f"sup_act:{client_id}:stop_ai"),
        InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_ticket_by_client:{client_id}"),
    ])
    
    return InlineKeyboardMarkup(rows)

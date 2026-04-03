from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def client_keyboard(is_suspicious=False):
    """Клавиатура для клиента (только базовые действия)"""
    buttons = [
        [
            InlineKeyboardButton("🔥 Вызвать менеджера", callback_data="ask_call_manager"),
            InlineKeyboardButton("✅ Закрыть тикет", callback_data="ask_close_ticket"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_client_keyboard(action: str):
    """Клавиатура подтверждения для клиентов."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=action),
            InlineKeyboardButton("❌ Нет", callback_data="cancel_client_action"),
        ]
    ])


def manager_keyboard(ticket_id="", is_suspicious=False):
    """Простая клавиатура менеджера."""
    buttons = [[InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_ticket:{ticket_id}")]]
    if is_suspicious:
        buttons.append([InlineKeyboardButton("🗑 Убрать тикет", callback_data=f"remove_ticket:{ticket_id}")])
    return InlineKeyboardMarkup(buttons)


def build_support_keyboard(client_id, user_info=None, balance_data=None, is_suspicious=False, section="profile"):
    """
    Клавиатура управления клиентом в топике поддержки.

    Если в настройках есть miniapp_url — все кнопки навигации открывают
    MiniApp с параметром ?client_id=<id>&section=<tab>.
    Если url не задан — используем старые callback-кнопки (fallback).
    Кнопки AI и закрытия тикета — всегда callback.
    """
    from utils.db_config import get_settings

    config = get_settings()
    mini_app_url = config.get("miniapp_url", "") or (
        f"https://{config.get('mini_app_domain', '')}" if config.get("mini_app_domain") else ""
    )

    rows = []
    has_webap = bool(mini_app_url and mini_app_url.startswith("https://"))

    if has_webap:
        # ── Главная кнопка — открыть полную карточку пользователя ──
        card_url = f"{mini_app_url.rstrip('/')}/?client_id={client_id}"
        try:
            rows.append([
                InlineKeyboardButton(
                    "📱 Открыть карточку пользователя",
                    web_app=WebAppInfo(url=card_url),
                )
            ])
        except Exception:
            rows.append([InlineKeyboardButton("📱 Карточка пользователя", url=card_url)])

        # ── Навигационные секции через MiniApp ──
        nav_sections = [
            ("👤 Профиль", "profile"),
            ("📊 Трафик", "traffic"),
            ("📅 Даты", "dates"),
            ("🔗 Подписка", "subscription"),
            ("📱 Устройства", "hwid"),
            ("💰 Баланс", "balance"),
        ]
        row1, row2 = [], []
        for i, (label, sec) in enumerate(nav_sections):
            sec_url = f"{mini_app_url.rstrip('/')}/?client_id={client_id}&section={sec}"
            try:
                btn = InlineKeyboardButton(label, web_app=WebAppInfo(url=sec_url))
            except Exception:
                btn = InlineKeyboardButton(label, callback_data=f"sup:{client_id}:{sec}")
            if i < 3:
                row1.append(btn)
            else:
                row2.append(btn)
        if row1:
            rows.append(row1)
        if row2:
            rows.append(row2)

    else:
        # ── Fallback: старые callback-кнопки ──
        sections = [
            ("👤 Профиль", "profile"),
            ("📊 Трафик", "traffic"),
            ("📅 Даты", "dates"),
            ("🔗 Подписка", "subscription"),
            ("📱 Устройства", "hwid"),
            ("💰 Баланс", "balance"),
            ("📜 Транзакции", "transactions"),
        ]
        nav_row1, nav_row2, nav_row3 = [], [], []
        for i, (label, sec) in enumerate(sections):
            text = f"✓ {label}" if sec == section else label
            btn = InlineKeyboardButton(text, callback_data=f"sup:{client_id}:{sec}")
            if i < 3:
                nav_row1.append(btn)
            elif i < 5:
                nav_row2.append(btn)
            else:
                nav_row3.append(btn)
        if nav_row1:
            rows.append(nav_row1)
        if nav_row2:
            rows.append(nav_row2)
        if nav_row3:
            rows.append(nav_row3)

        # Действия (только в fallback-режиме, в MiniApp они есть внутри)
        if user_info and user_info.get("uuid") and not is_suspicious:
            status = user_info.get("status", "").upper()
            is_disabled = status in ("DISABLED", "INACTIVE", "BANNED")

            rows.append([
                InlineKeyboardButton("🔄 Сброс трафика", callback_data=f"sup_act:{client_id}:reset_traffic"),
                InlineKeyboardButton("🔗 Перевыпуск", callback_data=f"sup_act:{client_id}:revoke_sub"),
            ])

            row_lock = []
            if is_disabled:
                row_lock.append(InlineKeyboardButton("🔓 Разблокировать", callback_data=f"sup_act:{client_id}:enable"))
            else:
                row_lock.append(InlineKeyboardButton("🔒 Заблокировать", callback_data=f"sup_act:{client_id}:disable"))
            row_lock.append(InlineKeyboardButton("🗑 Удалить HWID", callback_data=f"sup_act:{client_id}:hwid_del_all"))
            rows.append(row_lock)

    # ── Управление AI и тикетом — всегда callback ──
    rows.append([
        InlineKeyboardButton("🤖 AI ВКЛ", callback_data=f"sup_act:{client_id}:start_ai"),
        InlineKeyboardButton("🤖 AI ВЫКЛ", callback_data=f"sup_act:{client_id}:stop_ai"),
        InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_ticket_by_client:{client_id}"),
    ])

    return InlineKeyboardMarkup(rows)

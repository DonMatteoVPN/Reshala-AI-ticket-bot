"""
Обработчики настроек через inline кнопки — Решала support от DonMatteo
/settings — управление AI провайдерами, базой знаний
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.ai.manager import AIProviderManager

logger = logging.getLogger(__name__)


def _get_config(context):
    return context.application.bot_data.get("_config", {})


def _get_db(context):
    return context.application.bot_data.get("_db")


def _check_access(user_id, context):
    config = _get_config(context)
    return user_id in set(config.get("allowed_manager_ids", []))


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id, context):
        await update.message.reply_text("Нет доступа.")
        return

    await _show_settings_menu(update.message, context)


async def _show_settings_menu(target, context, edit=False):
    db = _get_db(context)
    config = _get_config(context)
    ai_manager = AIProviderManager(db)
    providers = ai_manager.get_providers()
    active = config.get("active_provider", "")
    ai_enabled = config.get("ai_enabled", True)

    lines = ["<b>Настройки AI</b>\n"]
    lines.append(f"AI: {'✅ Включен' if ai_enabled else '❌ Выключен'}")
    lines.append(f"Активный провайдер: <b>{active}</b>\n")

    for p in providers:
        status = "✅" if p.get("enabled") and p.get("api_keys") else "⬜"
        keys = len(p.get("api_keys", []))
        model = p.get("selected_model", "—")
        models_count = len(p.get("models", []))
        lines.append(f"{status} <b>{p['display_name']}</b>: {keys} ключей, модель: {model} ({models_count} доступно)")

    kb_count = db.knowledge_base.count_documents({}) if db else 0
    lines.append(f"\nБаза знаний: {kb_count} статей")

    text = "\n".join(lines)

    buttons = [
        [
            InlineKeyboardButton("🔄 AI Вкл/Выкл", callback_data="cfg:toggle_ai"),
        ],
    ]
    for p in providers:
        name = p["name"]
        buttons.append([
            InlineKeyboardButton(f"{'✅' if p.get('enabled') else '⬜'} {p['display_name']}", callback_data=f"cfg:toggle:{name}"),
            InlineKeyboardButton("🔑 Ключ", callback_data=f"cfg:addkey:{name}"),
            InlineKeyboardButton("🔍 Тест", callback_data=f"cfg:test:{name}"),
        ])
    buttons.append([
        InlineKeyboardButton("📚 База знаний", callback_data="cfg:kb_menu"),
    ])

    markup = InlineKeyboardMarkup(buttons)

    if edit and hasattr(target, 'edit_text'):
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await target.reply_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _check_access(query.from_user.id, context):
        await query.answer("Нет доступа.", show_alert=True)
        return

    data = query.data
    db = _get_db(context)
    config = _get_config(context)
    ai_manager = AIProviderManager(db)

    if data == "cfg:toggle_ai":
        new_val = not config.get("ai_enabled", True)
        db.settings.update_one({}, {"$set": {"ai_enabled": new_val}})
        context.application.bot_data["_config"]["ai_enabled"] = new_val
        await query.answer(f"AI {'включен' if new_val else 'выключен'}")
        await _show_settings_menu(query.message, context, edit=True)

    elif data.startswith("cfg:toggle:"):
        name = data.split(":", 2)[2]
        provider = ai_manager.get_provider(name)
        if provider:
            new_val = not provider.get("enabled", False)
            ai_manager.set_enabled(name, new_val)
            await query.answer(f"{provider['display_name']} {'включен' if new_val else 'выключен'}")
        await _show_settings_menu(query.message, context, edit=True)

    elif data.startswith("cfg:addkey:"):
        name = data.split(":", 2)[2]
        provider = ai_manager.get_provider(name)
        display = provider["display_name"] if provider else name
        context.user_data["awaiting_key_for"] = name
        await query.answer()
        await query.message.reply_text(
            f"Отправьте API ключ для <b>{display}</b>:",
            parse_mode="HTML",
        )

    elif data.startswith("cfg:test:"):
        name = data.split(":", 2)[2]
        await query.answer("Тестирование...")
        result = ai_manager.test_connection(name)
        if result.get("ok"):
            count = result.get("count", len(result.get("models", [])))
            if result.get("models"):
                db.ai_providers.update_one({"name": name}, {"$set": {"models": result["models"]}})
                if not ai_manager.get_provider(name).get("selected_model"):
                    db.ai_providers.update_one({"name": name}, {"$set": {"selected_model": result["models"][0]}})
            await query.message.reply_text(f"✅ {name}: Соединение есть! Доступно моделей: {count}")
        else:
            await query.message.reply_text(f"❌ {name}: {result.get('error', 'Ошибка')}")
        await _show_settings_menu(query.message, context)

    elif data.startswith("cfg:setactive:"):
        name = data.split(":", 2)[2]
        ai_manager.set_active_provider(name)
        context.application.bot_data["_config"]["active_provider"] = name
        await query.answer(f"Активный: {name}")
        await _show_settings_menu(query.message, context, edit=True)

    elif data == "cfg:kb_menu":
        await query.answer()
        articles = list(db.knowledge_base.find({}).sort("updated_at", -1).limit(10))
        lines = ["<b>База знаний AI</b>\n"]
        if articles:
            for i, a in enumerate(articles, 1):
                lines.append(f"{i}. <b>{a.get('title', '')}</b> [{a.get('category', 'general')}]")
        else:
            lines.append("Пусто. Добавьте статьи через Mini App или командой.")
        lines.append("\nДля добавления статьи используйте Mini App → База знаний")

        buttons = [[InlineKeyboardButton("◀️ Назад", callback_data="cfg:back")]]
        await query.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "cfg:back":
        await query.answer()
        await _show_settings_menu(query.message, context, edit=True)

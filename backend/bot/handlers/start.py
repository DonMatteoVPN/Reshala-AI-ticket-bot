"""
Обработчики /start и /help — Решала support от DonMatteo
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp, MenuButtonCommands
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _get_config(context):
    return context.application.bot_data.get("_config", {})


def _check_access(user_id, context):
    config = _get_config(context)
    allowed = set(config.get("allowed_manager_ids", []))
    return user_id in allowed


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = _get_config(context)
    service_name = config.get("service_name", "Решала support")
    mini_app_domain = config.get("mini_app_domain", "")
    mini_app_url = f"https://{mini_app_domain}" if mini_app_domain else ""

    if not _check_access(user_id, context):
        try:
            await context.bot.set_chat_menu_button(
                chat_id=update.effective_chat.id,
                menu_button=MenuButtonCommands(),
            )
        except Exception:
            pass
        await update.message.reply_text(
            f"Здравствуйте! Это поддержка {service_name}.\n\n"
            "Напишите ваше сообщение — менеджер ответит здесь в боте."
        )
        return

    text = (
        f"<b>Решала support от DonMatteo</b>\n\n"
        f"Сервис: {service_name}\n\n"
        "Отправьте Telegram ID или username пользователя для поиска.\n\n"
        "/settings — Настройки AI провайдеров\n"
        "/help — Справка"
    )
    reply_markup = None
    if mini_app_url:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("Открыть Mini App", web_app=WebAppInfo(url=mini_app_url))
        ]])
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

    if mini_app_url:
        try:
            await context.bot.set_chat_menu_button(
                chat_id=update.effective_chat.id,
                menu_button=MenuButtonWebApp(text="Mini App", web_app=WebAppInfo(url=mini_app_url)),
            )
        except Exception:
            pass


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _check_access(user_id, context):
        await update.message.reply_text("Напишите ваше сообщение — менеджер ответит здесь.")
        return

    text = (
        "<b>Справка — Решала support от DonMatteo</b>\n\n"
        "<b>Поиск:</b> Отправьте Telegram ID или username\n\n"
        "<b>Команды:</b>\n"
        "/start — Начать\n"
        "/help — Справка\n"
        "/settings — Настройки AI\n\n"
        "<b>AI Система:</b>\n"
        "Поддерживаемые провайдеры: Groq, OpenAI, Anthropic, Google Gemini, OpenRouter\n"
        "Автоматическое переключение ключей при исчерпании лимитов\n"
        "Настройка через /settings или Mini App"
    )
    await update.message.reply_text(text, parse_mode='HTML')

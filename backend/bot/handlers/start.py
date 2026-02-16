"""
Обработчики /start и /help — Решала support от DonMatteo
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp, MenuButtonCommands
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


from utils.db_config import get_settings

def _check_access(user_id):
    config = get_settings()
    allowed = set(config.get("allowed_manager_ids", []))
    return user_id in allowed


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = get_settings()
    service_name = config.get("service_name", "Решала support")
    mini_app_url = config.get("miniapp_url", "")
    allowed_managers = config.get("allowed_manager_ids", [])
    
    logger.info(f"Start called by user_id={user_id}. Allowed managers: {allowed_managers}")

    # Fallback to domain if url is missing
    if not mini_app_url and config.get("mini_app_domain"):
        mini_app_url = f"https://{config.get('mini_app_domain')}"

    is_manager = user_id in set(allowed_managers)

    if not is_manager:
        # Обычный пользователь - меню по умолчанию
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

    # Менеджер
    manager_text = (
        f"<b>Решала support от DonMatteo</b>\n\n"
        f"Сервис: {service_name}\n\n"
        "Отправьте Telegram ID или username пользователя для поиска.\n\n"
        "💡 <b>Все настройки теперь доступны только в Mini App.</b>\n"
    )
    
    if mini_app_url:
        # Выводим и гиперссылку, и чистый текст для надежности
        manager_text += f"\n🔗 <a href='{mini_app_url}'>Открыть Mini App</a>"
        manager_text += f"\n<code>{mini_app_url}</code>\n"
    
    manager_text += "\n/help — Справка"
    
    buttons = []
    if mini_app_url:
        logger.info(f"Checking URL for buttons: {mini_app_url}")
        
        # Telegram ЗАПРЕЩАЕТ localhost и 127.0.0.1 в кнопках (Error: wrong http url)
        is_local = "localhost" in mini_app_url or "127.0.0.1" in mini_app_url
        
        if not is_local:
            if mini_app_url.startswith("https://"):
                buttons.append([InlineKeyboardButton("📱 Открыть Dashboard", web_app=WebAppInfo(url=mini_app_url))])
                
                try:
                    await context.bot.set_chat_menu_button(
                        chat_id=update.effective_chat.id,
                        menu_button=MenuButtonWebApp(text="Dashboard", web_app=WebAppInfo(url=mini_app_url)),
                    )
                except Exception as e:
                    logger.warning(f"Failed to set menu button: {e}")
            else:
                # Обычная ссылка (не https, но не локальная)
                buttons.append([InlineKeyboardButton("📱 Открыть Dashboard (Browser)", url=mini_app_url)])
        else:
            logger.info("URL is local (localhost). Skipping buttons to avoid Telegram API error. Use text link.")
            # Для локального запуска убираем кнопку меню
            try:
                await context.bot.set_chat_menu_button(
                    chat_id=update.effective_chat.id,
                    menu_button=MenuButtonCommands(),
                )
            except Exception:
                pass
    else:
        logger.warning(f"No mini_app_url found for manager {user_id}")
        # Если URL нет, убираем кнопку
        try:
            await context.bot.set_chat_menu_button(
                chat_id=update.effective_chat.id,
                menu_button=MenuButtonCommands(),
            )
        except Exception:
            pass

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text(manager_text, parse_mode='HTML', reply_markup=reply_markup)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = get_settings()

    if not _check_access(user_id):
        await update.message.reply_text("Напишите ваше сообщение — менеджер ответит здесь.")
        return

    mini_app_url = config.get("miniapp_url") or (f"https://{config.get('mini_app_domain')}" if config.get("mini_app_domain") else "")

    text = (
        "<b>Справка — Решала support от DonMatteo</b>\n\n"
        "<b>Поиск:</b> Отправьте Telegram ID или username\n\n"
        "<b>Команды:</b>\n"
        "/start — Начать\n"
        "/help — Справка\n\n"
        "⚙️ <b>Настройка:</b>\n"
        "Все настройки AI-провайдеров, моделей и системных промптов перенесены в <b>Mini App</b>.\n"
    )

    if mini_app_url:
        text += f"\n🔗 <a href='{mini_app_url}'>Открыть Dashboard</a>\n"
        text += f"<code>{mini_app_url}</code>\n"
    else:
        text += "\nИспользуйте кнопку «Открыть Dashboard»."
    
    buttons = []
    if mini_app_url:
        is_local = "localhost" in mini_app_url or "127.0.0.1" in mini_app_url
        if not is_local:
            if mini_app_url.startswith("https://"):
                buttons.append([InlineKeyboardButton("📱 Открыть Dashboard", web_app=WebAppInfo(url=mini_app_url))])
            else:
                buttons.append([InlineKeyboardButton("📱 Открыть Dashboard (Browser)", url=mini_app_url)])
    
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

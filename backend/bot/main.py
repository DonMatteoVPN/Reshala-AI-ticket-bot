#!/usr/bin/env python3
"""
Решала support от DonMatteo — модульный Telegram бот
Точка входа: запуск бота с конфигурацией из MongoDB
"""
import os
import sys
import logging
import asyncio
from pymongo import MongoClient
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, PicklePersistence
)

from utils.db_config import get_db, get_settings
from utils.support_common import get_support_chat_ids


from bot.handlers.start import start_handler, help_handler
from bot.handlers.search import handle_message
from bot.handlers.support import (
    handle_client_message, handle_support_group_message,
    call_manager_callback, client_close_ticket_callback,
    close_ticket_callback, dispatch_message, check_balance_callback,
    remove_ticket_callback, ask_call_manager_callback, ask_close_ticket_callback,
    cancel_client_action_callback, support_action_callback, support_nav_callback
)
from bot.handlers.settings import settings_command, settings_callback
from bot.handlers.actions import (
    action_callback, button_callback, support_card_callback, 
    squad_assign_callback, confirm_action_callback, cancel_action_callback
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)








async def post_init(application: Application) -> None:
    from telegram import MenuButtonCommands, MenuButtonWebApp, WebAppInfo
    
    # Загружаем конфиг из MongoDB
    config = get_settings()
    miniapp_url = config.get("miniapp_url") if config else None

    try:
        # По умолчанию у всех обычное меню
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception as e:
        logger.warning("post_init set_chat_menu_button: %s", e)
    
    # Загружаем конфиг из MongoDB и сохраняем в bot_data
    # НЕ сохраняем db — он не сериализуется!
    config = get_settings()
    if config:
        application.bot_data["_config"] = config
        logger.info(f"post_init: Loaded config, support_group_id={config.get('support_group_id')}")


def main():
    config = get_settings()
    if not config:
        logger.error("Нет настроек в MongoDB. Настройте через Mini App.")
        sys.exit(1)

    bot_token = config.get("bot_token", "")
    if not bot_token:
        logger.error("BOT_TOKEN не установлен. Настройте через Mini App -> Настройки.")
        sys.exit(1)

    support_group_id = config.get("support_group_id")

    persistence_path = os.getenv("PERSISTENCE_PATH", "/data/bot_state.pickle")
    try:
        persistence = PicklePersistence(filepath=persistence_path)
    except Exception:
        persistence = None

    builder = Application.builder().token(bot_token).post_init(post_init)
    if persistence:
        builder = builder.persistence(persistence)
    application = builder.build()

    # Конфиг загружается в post_init, но также устанавливаем здесь для регистрации handlers
    # НЕ сохраняем db в bot_data — он не сериализуется!
    application.bot_data["_config"] = config

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CallbackQueryHandler(support_action_callback, pattern="^sup_act:"))
    application.add_handler(CallbackQueryHandler(support_nav_callback, pattern="^sup:"))
    application.add_handler(CallbackQueryHandler(support_card_callback, pattern="^sup"))
    application.add_handler(CallbackQueryHandler(close_ticket_callback, pattern="^close_ticket:"))
    application.add_handler(CallbackQueryHandler(remove_ticket_callback, pattern="^remove_ticket:"))
    application.add_handler(CallbackQueryHandler(call_manager_callback, pattern="^call_manager$"))
    application.add_handler(CallbackQueryHandler(client_close_ticket_callback, pattern="^client_close_ticket$"))
    application.add_handler(CallbackQueryHandler(ask_call_manager_callback, pattern="^ask_call_manager$"))
    application.add_handler(CallbackQueryHandler(ask_close_ticket_callback, pattern="^ask_close_ticket$"))
    application.add_handler(CallbackQueryHandler(cancel_client_action_callback, pattern="^cancel_client_action$"))
    application.add_handler(CallbackQueryHandler(check_balance_callback, pattern="^check_balance$"))
    application.add_handler(CallbackQueryHandler(squad_assign_callback, pattern="^squad"))
    application.add_handler(CallbackQueryHandler(confirm_action_callback, pattern="^confirm:"))
    application.add_handler(CallbackQueryHandler(cancel_action_callback, pattern="^cancel_action$"))
    application.add_handler(CallbackQueryHandler(action_callback, pattern="^(act:|hwid_del:)"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^s:"))

    support_content = (
        filters.TEXT | filters.PHOTO | filters.Document.ALL
        | filters.VIDEO | filters.VOICE | filters.AUDIO
        | filters.VIDEO_NOTE | filters.Sticker.ALL | filters.ANIMATION
    ) & ~filters.COMMAND

    # Сообщения от менеджера в группе поддержки
    if support_group_id:
        chat_ids = get_support_chat_ids(support_group_id)
        logger.info(f"Registered support group handler for chat_ids: {chat_ids}")
        application.add_handler(MessageHandler(
            support_content & filters.Chat(chat_ids),
            handle_support_group_message,
        ))

    # Все остальные сообщения (личные чаты) — dispatch_message
    logger.info("Registered dispatch_message handler for private chats")
    application.add_handler(MessageHandler(support_content, dispatch_message))

    logger.info("Решала support от DonMatteo — бот запущен")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

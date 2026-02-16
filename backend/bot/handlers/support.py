import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.db_config import get_settings
from utils.support_common import check_access
from bot.handlers.support_client import (
    handle_client_message,
    call_manager_callback,
    client_close_ticket_callback,
    ask_call_manager_callback,
    ask_close_ticket_callback,
    cancel_client_action_callback,
    check_balance_callback
)
from bot.handlers.support_manager import (
    handle_support_group_message,
    close_ticket_callback,
    remove_ticket_callback,
    support_nav_callback,
    support_action_callback
)

logger = logging.getLogger(__name__)

async def dispatch_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Распределение входящих сообщений."""
    if not update.message:
        return

    user_id = update.effective_user.id
    
    # Check if user is manager
    if check_access(user_id):
        # Lazy import to avoid circular dependency
        from bot.handlers.search import handle_message
        handled = await handle_message(update, context)
        if handled:
            return

    config = get_settings()
    if config.get("support_group_id"):
        await handle_client_message(update, context)
    else:
        logger.warning("dispatch_message: support_group_id not configured!")

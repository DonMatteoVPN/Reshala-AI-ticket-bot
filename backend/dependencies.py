from fastapi import Depends
from utils.db_config import get_db, get_bot_token, get_support_group_id
from services.telegram_service import TelegramService
from services.ticket_service import TicketService

async def get_database():
    """Dependency for database connection."""
    db = get_db()
    if db is None:
        raise Exception("Database connection failed")
    yield db

async def get_telegram_service():
    """Dependency for TelegramService."""
    token = get_bot_token()
    if not token:
        # We can return None or raise error. 
        # If token is missing, Telegram features won't work.
        # Ideally return None so we can handle it gracefully in Service
        return None
    return TelegramService(token)

async def get_ticket_service(
    db = Depends(get_database),
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Dependency for TicketService."""
    support_group_id = get_support_group_id()
    return TicketService(db, telegram_service, support_group_id)

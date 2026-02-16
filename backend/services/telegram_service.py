import logging
import telegram
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, bot_token: str = None, bot: telegram.Bot = None):
        """
        Инициализация TelegramService.
        Можно передать либо bot_token (создастся новый бот), либо существующий bot.
        """
        if bot:
            self.bot = bot
        elif bot_token:
            self.bot = telegram.Bot(token=bot_token)
        else:
            raise ValueError("Необходимо передать либо bot_token, либо bot")

    async def create_forum_topic(self, chat_id: int, name: str) -> int:
        """Creates a forum topic and returns its message_thread_id."""
        try:
            topic = await self.bot.create_forum_topic(chat_id=chat_id, name=name)
            return topic.message_thread_id
        except TelegramError as e:
            logger.error(f"Failed to create forum topic: {e}")
            raise e

    async def close_forum_topic(self, chat_id: int, message_thread_id: int):
        """Closes a forum topic."""
        try:
            await self.bot.close_forum_topic(chat_id=chat_id, message_thread_id=message_thread_id)
        except TelegramError as e:
            logger.warning(f"Failed to close forum topic {message_thread_id}: {e}")

    async def edit_forum_topic(self, chat_id: int, message_thread_id: int, name: str):
        """Renames a forum topic."""
        try:
            await self.bot.edit_forum_topic(chat_id=chat_id, message_thread_id=message_thread_id, name=name)
        except TelegramError as e:
            logger.warning(f"Failed to edit forum topic {message_thread_id}: {e}")

    async def send_message(self, chat_id: int, text: str, message_thread_id: int = None, parse_mode="HTML"):
        """Sends a text message."""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                message_thread_id=message_thread_id,
                parse_mode=parse_mode
            )
        except TelegramError as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            # Don't raise, just log, to prevent breaking flows
    
    async def send_photo(self, chat_id: int, photo: str, caption: str = None, message_thread_id: int = None, parse_mode="HTML"):
        try:
            await self.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                message_thread_id=message_thread_id,
                parse_mode=parse_mode
            )
        except TelegramError as e:
             logger.error(f"Failed to send photo to {chat_id}: {e}")

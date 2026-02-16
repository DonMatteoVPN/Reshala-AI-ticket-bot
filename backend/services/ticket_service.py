import logging
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from pymongo.database import Database

from services.telegram_service import TelegramService
from utils.support_common import get_topic_name, build_support_header, TOPIC_CLOSED

logger = logging.getLogger(__name__)

class TicketService:
    def __init__(self, db: Database, telegram_service: Optional[TelegramService] = None, support_group_id: Optional[int] = None):
        self.db = db
        self.telegram_service = telegram_service
        self.support_group_id = support_group_id

    async def create_ticket(self, client_id: int, client_name: str, client_username: str, 
                          user_data: dict, reason: str = None, last_messages: list = None,
                          is_suspicious: bool = False) -> dict:
        """Creates a new ticket and optionally a Telegram forum topic."""
        
        # Check if active ticket exists?
        # For now, following existing logic: just create.
        
        status = "suspicious" if is_suspicious else "open"
        
        ticket = {
            "client_id": client_id,
            "client_name": client_name,
            "client_username": client_username,
            "status": status,
            "reason": reason,
            "messages": [],
            "last_messages": last_messages or [],
            "user_data": user_data,
            "attachments": [],
            "created_at": datetime.now(timezone.utc),
            "escalated_at": None,
            "is_removed": False,
        }

        topic_id = None
        if self.telegram_service and self.support_group_id:
             try:
                # 1. Create topic
                topic_name = get_topic_name(client_username, status)
                topic_id = await self.telegram_service.create_forum_topic(
                    chat_id=self.support_group_id,
                    name=topic_name
                )
                ticket["topic_id"] = topic_id

                # 2. Send header
                user_info = user_data.get("user", {}) if user_data else {}
                balance_data = user_data.get("bedolaga_user") if user_data else {}
                header_text = build_support_header(user_info, balance_data, is_suspicious)
                
                await self.telegram_service.send_message(
                    chat_id=self.support_group_id,
                    message_thread_id=topic_id,
                    text=header_text
                )
                
                # 3. Pin message? (TelegramService logic needs expansion or direct bot usage if needed, but for now simple send)
                # Note: helper 'send_message' returns None currently in my impl, need to update if I want to pin.
             except Exception as e:
                logger.error(f"Error creating telegram topic: {e}")

        result = self.db.tickets.insert_one(ticket)
        return {
            "ticket_id": str(result.inserted_id),
            "status": status,
            "topic_id": topic_id
        }

    async def get_active_tickets(self, manager_id: int = None) -> List[dict]:
        """Get all active tickets (escalated + suspicious)"""
        tickets = list(self.db.tickets.find(
            {
                "status": {"$in": ["escalated", "suspicious"]},
                "is_removed": {"$ne": True}
            }
        ).sort([("status", 1), ("created_at", -1)]).limit(100))
        
        order = {"suspicious": 0, "escalated": 1}
        tickets.sort(key=lambda t: order.get(t.get("status"), 3))
        return tickets

    async def get_escalated_tickets(self, limit: int = 50) -> List[dict]:
        """Get escalated tickets"""
        return list(self.db.tickets.find(
            {"status": "escalated", "is_removed": {"$ne": True}}
        ).sort("escalated_at", -1).limit(limit))

    async def get_suspicious_tickets(self, limit: int = 50) -> List[dict]:
        """Get suspicious tickets"""
        return list(self.db.tickets.find(
            {"status": "suspicious", "is_removed": {"$ne": True}}
        ).sort("created_at", -1).limit(limit))

    async def get_ticket(self, ticket_id: str) -> Optional[dict]:
        """Get ticket by ID"""
        if not ObjectId.is_valid(ticket_id):
            return None
        return self.db.tickets.find_one({"_id": ObjectId(ticket_id)})

    async def remove_ticket(self, ticket_id: str) -> bool:
        """Remove ticket"""
        if not ObjectId.is_valid(ticket_id):
            return False
        result = self.db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": {"is_removed": True, "removed_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def escalate_ticket(self, ticket_id: str, reason: str = None, user_data: dict = None, last_messages: list = None):
        """Escalate ticket to manager"""
        update_data = {
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc)
        }
        if reason: update_data["reason"] = reason
        if user_data: update_data["user_data"] = user_data
        if last_messages: update_data["last_messages"] = last_messages

        result = self.db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def mark_suspicious(self, ticket_id: str, reason: str = None):
        """Mark ticket as suspicious"""
        update_data = {
            "status": "suspicious",
            "escalated_at": datetime.now(timezone.utc)
        }
        if reason: update_data["reason"] = reason
        
        result = self.db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def add_attachment(self, ticket_id: str, att_type: str, value: str, url: str = None):
        """Add attachment to ticket"""
        attachment = {
            "type": att_type,
            "value": value,
            "url": url,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        result = self.db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$push": {"attachments": attachment}}
        )
        return result.modified_count > 0

    async def reply_to_ticket(self, ticket_id: str, message: str, manager_name: str) -> dict:
        """Reply to ticket from manager"""
        ticket = self.db.tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            return {"ok": False, "error": "ticket_not_found"}

        client_id = ticket.get("client_id")
        topic_id = ticket.get("topic_id")
        
        if not client_id:
             return {"ok": False, "error": "No client_id in ticket"}

        telegram_sent = False
        telegram_error = None

        if self.telegram_service:
            # 1. Send to client
            text_client = f"💬 <b>Поддержка</b> ({manager_name}):\n\n{message}"
            try:
                await self.telegram_service.send_message(chat_id=client_id, text=text_client)
                telegram_sent = True
            except Exception as e:
                telegram_error = str(e)

            # 2. Send to support group
            if self.support_group_id and topic_id:
                text_group = f"👨‍💼 <b>{manager_name}:</b>\n\n{message}"
                await self.telegram_service.send_message(
                    chat_id=self.support_group_id,
                    text=text_group,
                    message_thread_id=topic_id
                )

        # Update DB
        reply_record = {
            "role": "manager",
            "name": manager_name,
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sent_to_telegram": telegram_sent
        }
        
        last_messages = ticket.get("last_messages", [])
        last_messages.append(reply_record)
        if len(last_messages) > 20: last_messages = last_messages[-20:]
        
        self.db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "last_messages": last_messages,
                    "last_reply_at": datetime.now(timezone.utc)
                },
                "$push": {"history": reply_record}
            }
        )
        
        if telegram_sent:
            return {"ok": True, "message": "Reply sent"}
        else:
            return {"ok": False, "error": telegram_error or "Telegram service unavailable", "saved": True}

    async def close_ticket(self, ticket_id: str, user_id: int, is_manager: bool = False):
        """Close ticket."""
        # Using the logic I previously wrote but adapted to instance
        query = {}
        if ObjectId.is_valid(ticket_id):
            query = {"_id": ObjectId(ticket_id)}
        elif str(ticket_id).isdigit():
            tid = int(ticket_id)
            if tid > 1000000:
                query = {"client_id": tid, "is_removed": {"$ne": True}, "status": {"$ne": "closed"}}
            else:
                query = {"topic_id": tid}
        else:
            return {"ok": False, "error": "Invalid ticket_id"}

        ticket = self.db.tickets.find_one(query)
        if not ticket:
            return {"ok": False, "error": "Ticket not found"}

        thread_id = ticket.get("topic_id")
        client_id = ticket.get("client_id")
        client_username = ticket.get("client_username") or ticket.get("client_name") or ""
        current_status = ticket.get("status")

        if current_status == "closed":
             return {"ok": True, "message": "Already closed"}

        # Определяем статус тикета для правильного эмодзи
        is_suspicious = ticket.get("status") == "suspicious"
        
        # Менеджер всегда меняет на ✅, клиент сохраняет текущий статус
        if is_manager:
            final_status = "closed"
        else:
            # Клиент закрывает: подозрительный остается подозрительным
            final_status = "suspicious" if is_suspicious else "closed"
        
        if self.telegram_service and self.support_group_id and thread_id:
            try:
                # Порядок операций: сообщение → переименование → закрытие
                # 1. Отправляем сообщение о закрытии
                closer = "менеджером" if is_manager else "клиентом"
                await self.telegram_service.send_message(
                    self.support_group_id, 
                    f"✅ <b>Тикет закрыт {closer}.</b>", 
                    thread_id
                )
                
                # 2. Переименовываем тему с правильным эмодзи
                new_name = get_topic_name(client_username, final_status)
                logger.info(f"[CLOSE_TICKET] Renaming topic {thread_id} to: {new_name} (status={final_status})")
                await self.telegram_service.edit_forum_topic(self.support_group_id, thread_id, new_name)
                
                # 3. Закрываем тему
                await self.telegram_service.close_forum_topic(self.support_group_id, thread_id)
                
                # Notify client
                if is_manager and client_id:
                    await self.telegram_service.send_message(client_id, "✅ Тикет поддержки закрыт менеджером.\n\nЕсли нужна помощь — напишите снова.")
            except Exception as e:
                logger.error(f"Telegram error in close_ticket: {e}")
        
        # Удаляем тикет из БД (кроме подозрительных, закрытых клиентом)
        if is_manager or not is_suspicious:
            # Менеджер всегда удаляет, клиент удаляет только обычные тикеты
            logger.info(f"[CLOSE_TICKET] Deleting ticket {ticket['_id']} from DB")
            self.db.tickets.delete_one({"_id": ticket["_id"]})
        else:
            # Подозрительный тикет, закрытый клиентом - оставляем в БД
            logger.info(f"[CLOSE_TICKET] Keeping suspicious ticket {ticket['_id']} in DB")
            self.db.tickets.update_one(
                {"_id": ticket["_id"]}, 
                {"$set": {"status": "suspicious", "closed_at": datetime.now(timezone.utc)}}
            )

        return {"ok": True, "message": "Ticket closed", "client_id": client_id, "topic_id": thread_id}

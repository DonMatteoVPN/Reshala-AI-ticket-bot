"""
Tickets Router — управление тикетами поддержки

Статусы:
  💬 open — Новый тикет
  🔥 escalated — Эскалация (клиент вызвал менеджера / AI не знает ответа)
  🚨 suspicious — Подозрительный (пользователь не найден в системе)
  ✅ closed — Закрыт
"""
from fastapi import APIRouter, Body
from pymongo import MongoClient
from datetime import datetime, timezone
from bson import ObjectId
import requests
import os

router = APIRouter()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reshala_support")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def _get_bot_token():
    """Получить токен бота из настроек"""
    config = db.settings.find_one({}, {"_id": 0}) or {}
    return config.get("bot_token") or ""


def _get_support_group():
    """Получить ID группы поддержки из настроек"""
    config = db.settings.find_one({}, {"_id": 0}) or {}
    return config.get("support_group_id")


def serialize_ticket(ticket):
    """Convert MongoDB document to JSON-serializable dict"""
    if not ticket:
        return None
    return {
        "id": str(ticket.get("_id", "")),
        "client_id": ticket.get("client_id"),
        "client_name": ticket.get("client_name"),
        "client_username": ticket.get("client_username"),
        "topic_id": ticket.get("topic_id"),
        "status": ticket.get("status", "open"),
        "reason": ticket.get("reason"),
        "escalated_at": ticket.get("escalated_at").isoformat() if ticket.get("escalated_at") else None,
        "created_at": ticket.get("created_at").isoformat() if ticket.get("created_at") else None,
        "closed_at": ticket.get("closed_at").isoformat() if ticket.get("closed_at") else None,
        "last_messages": ticket.get("last_messages", []),
        "history": ticket.get("history", []),
        "user_data": ticket.get("user_data"),
        "attachments": ticket.get("attachments", []),
        "is_removed": ticket.get("is_removed", False),
    }


@router.get("/escalated")
def get_escalated_tickets():
    """Get escalated (🔥) tickets only"""
    tickets = list(db.tickets.find(
        {"status": "escalated", "is_removed": {"$ne": True}},
        {"_id": 1, "client_id": 1, "client_name": 1, "client_username": 1, 
         "status": 1, "reason": 1, "escalated_at": 1, "created_at": 1, 
         "last_messages": 1, "user_data": 1, "attachments": 1}
    ).sort("escalated_at", -1).limit(50))
    
    return {"tickets": [serialize_ticket(t) for t in tickets]}


@router.get("/active")
def get_active_tickets():
    """Get all active tickets (escalated + suspicious + open) — без закрытых!"""
    tickets = list(db.tickets.find(
        {
            "status": {"$in": ["open", "escalated", "suspicious"]},  # БЕЗ closed!
            "is_removed": {"$ne": True}
        },
        {"_id": 1, "client_id": 1, "client_name": 1, "client_username": 1, "topic_id": 1,
         "status": 1, "reason": 1, "escalated_at": 1, "created_at": 1,
         "last_messages": 1, "history": 1, "user_data": 1, "attachments": 1}
    ).sort([("status", 1), ("created_at", -1)]).limit(100))
    
    # Сортировка: suspicious первые, потом escalated, потом open
    order = {"suspicious": 0, "escalated": 1, "open": 2}
    tickets.sort(key=lambda t: order.get(t.get("status"), 3))
    
    return {"tickets": [serialize_ticket(t) for t in tickets]}


@router.get("/suspicious")
def get_suspicious_tickets():
    """Get suspicious (🚨) tickets — users not found in system"""
    tickets = list(db.tickets.find(
        {"status": "suspicious", "is_removed": {"$ne": True}},
        {"_id": 1, "client_id": 1, "client_name": 1, "client_username": 1, 
         "status": 1, "reason": 1, "created_at": 1, "last_messages": 1, "attachments": 1}
    ).sort("created_at", -1).limit(50))
    
    return {"tickets": [serialize_ticket(t) for t in tickets]}


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str):
    """Get single ticket by ID"""
    try:
        ticket = db.tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            return {"ok": False, "error": "ticket_not_found"}
        return {"ok": True, "ticket": serialize_ticket(ticket)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/{ticket_id}/reply")
def reply_to_ticket(ticket_id: str, data: dict = Body(...)):
    """Отправить ответ менеджера клиенту через Telegram"""
    message = data.get("message", "").strip()
    manager_name = data.get("manager_name", "Менеджер")
    
    if not message:
        return {"ok": False, "error": "message_required"}
    
    try:
        ticket = db.tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            return {"ok": False, "error": "ticket_not_found"}
        
        client_id = ticket.get("client_id")
        topic_id = ticket.get("topic_id")
        
        if not client_id:
            return {"ok": False, "error": "Нет user_id в тикете"}
        
        # Получаем BOT_TOKEN из настроек
        bot_token = _get_bot_token()
        support_group_id = _get_support_group()
        
        if not bot_token:
            return {"ok": False, "error": "BOT_TOKEN не настроен в настройках"}
        
        # Формируем сообщение для клиента
        text = f"💬 <b>Поддержка</b> ({manager_name}):\n\n{message}"
        
        telegram_sent = False
        telegram_error = None
        
        # 1. Отправляем клиенту в ЛС
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": client_id,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            if r.status_code == 200:
                telegram_sent = True
            else:
                telegram_error = f"Telegram API: {r.status_code} - {r.text}"
        except Exception as e:
            telegram_error = str(e)
        
        # 2. Отправляем в топик группы поддержки (если есть)
        if support_group_id and topic_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": support_group_id,
                        "message_thread_id": topic_id,
                        "text": f"👨‍💼 <b>{manager_name}:</b>\n\n{message}",
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )
            except:
                pass  # Не критично если не отправилось в топик
        
        # Сохраняем ответ в историю тикета
        reply_record = {
            "role": "manager",
            "name": manager_name,
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sent_to_telegram": telegram_sent
        }
        
        last_messages = ticket.get("last_messages", [])
        last_messages.append(reply_record)
        if len(last_messages) > 20:
            last_messages = last_messages[-20:]
        
        db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "last_messages": last_messages,
                    "last_reply_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "history": reply_record
                }
            }
        )
        
        if telegram_sent:
            return {"ok": True, "message": "Ответ отправлен клиенту в Telegram"}
        else:
            return {"ok": False, "error": telegram_error or "Не удалось отправить в Telegram", "saved": True}
            
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/{ticket_id}/close")
def close_ticket(ticket_id: str):
    """Close ticket (✅) — переименовывает топик и закрывает его"""
    try:
        ticket = db.tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            return {"ok": False, "error": "ticket_not_found"}
        
        topic_id = ticket.get("topic_id")
        client_username = ticket.get("client_username") or ticket.get("client_name") or ""
        
        # Обновляем статус в БД
        db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Переименовываем и закрываем топик в Telegram
        bot_token = _get_bot_token()
        support_group_id = _get_support_group()
        
        if bot_token and support_group_id and topic_id:
            # Переименовываем топик на ✅
            new_name = f"✅ @{client_username}".strip()[:128] if client_username else "✅ Закрыт"
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/editForumTopic",
                    json={
                        "chat_id": support_group_id,
                        "message_thread_id": topic_id,
                        "name": new_name
                    },
                    timeout=10
                )
            except:
                pass
            
            # Закрываем топик
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/closeForumTopic",
                    json={
                        "chat_id": support_group_id,
                        "message_thread_id": topic_id
                    },
                    timeout=10
                )
            except:
                pass
            
            # Отправляем сообщение в топик
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": support_group_id,
                        "message_thread_id": topic_id,
                        "text": "✅ Тикет закрыт менеджером через Mini App."
                    },
                    timeout=10
                )
            except:
                pass
        
        return {"ok": True, "message": "Тикет закрыт"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/{ticket_id}/remove")
def remove_ticket(ticket_id: str):
    """Remove ticket from list (for suspicious/closed tickets)"""
    try:
        result = db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": {"is_removed": True, "removed_at": datetime.now(timezone.utc)}}
        )
        if result.modified_count == 0:
            return {"ok": False, "error": "ticket_not_found"}
        return {"ok": True, "message": "Тикет удалён из списка"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/create")
def create_ticket(data: dict = Body(...)):
    """Create new ticket"""
    client_id = data.get("client_id")
    if not client_id:
        return {"ok": False, "error": "client_id_required"}
    
    # Определяем статус: suspicious если нет user_data
    user_data = data.get("user_data")
    is_suspicious = data.get("is_suspicious", False) or not user_data or not user_data.get("user")
    
    ticket = {
        "client_id": client_id,
        "client_name": data.get("client_name"),
        "client_username": data.get("client_username"),
        "status": "suspicious" if is_suspicious else "open",
        "reason": data.get("reason"),
        "messages": [],
        "last_messages": data.get("last_messages", []),
        "user_data": user_data,
        "attachments": data.get("attachments", []),
        "created_at": datetime.now(timezone.utc),
        "escalated_at": None,
        "is_removed": False,
    }
    
    result = db.tickets.insert_one(ticket)
    return {"ok": True, "ticket_id": str(result.inserted_id), "status": ticket["status"]}


@router.post("/{ticket_id}/escalate")
def escalate_ticket(ticket_id: str, data: dict = Body(...)):
    """Escalate ticket to manager (🔥)"""
    try:
        result = db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "escalated",
                    "reason": data.get("reason", "Пользователь запросил менеджера"),
                    "escalated_at": datetime.now(timezone.utc),
                    "last_messages": data.get("last_messages", []),
                    "user_data": data.get("user_data"),
                }
            }
        )
        if result.modified_count == 0:
            return {"ok": False, "error": "ticket_not_found"}
        return {"ok": True, "message": "Тикет эскалирован"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/{ticket_id}/mark-suspicious")
def mark_suspicious(ticket_id: str, data: dict = Body(...)):
    """Mark ticket as suspicious (🚨) — user not found in system"""
    try:
        result = db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "suspicious",
                    "reason": data.get("reason", "Пользователь не найден в системе"),
                    "escalated_at": datetime.now(timezone.utc),
                }
            }
        )
        if result.modified_count == 0:
            return {"ok": False, "error": "ticket_not_found"}
        return {"ok": True, "message": "Тикет помечен как подозрительный"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/{ticket_id}/add-attachment")
def add_attachment(ticket_id: str, data: dict = Body(...)):
    """Add attachment (screenshot, subscription link) to ticket"""
    att_type = data.get("type")  # photo, subscription_link, document
    value = data.get("value") or data.get("url")
    
    if not att_type or not value:
        return {"ok": False, "error": "type and value required"}
    
    try:
        attachment = {
            "type": att_type,
            "value": value,
            "url": data.get("url"),
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        
        db.tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$push": {"attachments": attachment}}
        )
        
        return {"ok": True, "message": "Вложение добавлено"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

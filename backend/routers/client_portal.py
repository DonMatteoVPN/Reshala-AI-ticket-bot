"""
Client Portal Router — API для пользовательского портала
Позволяет пользователям видеть свои тикеты, историю переписки и данные профиля.
Авторизация через Telegram initData ИЛИ через magic-link токен.
"""
from fastapi import APIRouter, Body, Header, HTTPException, Query
from typing import Optional
import logging
import os
import hmac
import hashlib
import json
import time
import secrets
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
    DB_NAME = os.environ.get("DB_NAME", "reshala_support")
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]

def verify_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """Верификация Telegram WebApp initData"""
    try:
        params = {}
        for part in init_data.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
        
        received_hash = params.pop("hash", "")
        data_check_string = "\n".join(sorted(f"{k}={v}" for k, v in params.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(received_hash, expected_hash):
            return None
        
        user_str = params.get("user", "{}")
        from urllib.parse import unquote
        user = json.loads(unquote(user_str))
        return user
    except Exception as e:
        logger.warning(f"verify_telegram_init_data error: {e}")
        return None

def get_client_id_from_request(
    x_telegram_init_data: Optional[str] = None,
    x_client_token: Optional[str] = None
) -> Optional[int]:
    """Получить client_id из заголовков (Telegram initData или magic token)"""
    db = get_db()
    bot_token = os.environ.get("BOT_TOKEN", "")
    
    # 1. Telegram initData
    if x_telegram_init_data:
        skip_auth = os.environ.get("SKIP_AUTH", "false").lower() == "true"
        if skip_auth:
            # Dev mode: парсим без верификации
            try:
                for part in x_telegram_init_data.split("&"):
                    if part.startswith("user="):
                        from urllib.parse import unquote
                        user = json.loads(unquote(part[5:]))
                        return user.get("id")
            except:
                pass
        else:
            user = verify_telegram_init_data(x_telegram_init_data, bot_token)
            if user:
                return user.get("id")
    
    # 2. Magic token
    if x_client_token:
        token_doc = db.client_tokens.find_one({
            "token": x_client_token,
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        if token_doc:
            return token_doc.get("client_id")
    
    return None

def serialize_ticket_for_client(ticket: dict) -> dict:
    """Сериализация тикета для клиента (без внутренних данных)"""
    return {
        "id": str(ticket.get("_id", "")),
        "status": ticket.get("status", "open"),
        "reason": ticket.get("reason"),
        "created_at": ticket.get("created_at").isoformat() if ticket.get("created_at") else None,
        "closed_at": ticket.get("closed_at").isoformat() if ticket.get("closed_at") else None,
        "escalated_at": ticket.get("escalated_at").isoformat() if ticket.get("escalated_at") else None,
        "history": ticket.get("history", []),
        "last_messages": ticket.get("last_messages", []),
        "attachments": ticket.get("attachments", []),
        "ai_disabled": ticket.get("ai_disabled", False),
    }


@router.post("/auth/generate-link")
async def generate_magic_link(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None)
):
    """Генерация magic-link токена для входа без Telegram"""
    client_id = get_client_id_from_request(x_telegram_init_data, x_client_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    db.client_tokens.replace_one(
        {"client_id": client_id},
        {"client_id": client_id, "token": token, "expires_at": expires_at, "created_at": datetime.now(timezone.utc)},
        upsert=True
    )
    
    config = db.settings.find_one({}, {"_id": 0}) or {}
    mini_app_url = config.get("miniapp_url") or f"https://{config.get('mini_app_domain', '')}"
    
    return {
        "ok": True,
        "token": token,
        "link": f"{mini_app_url.rstrip('/')}/client?token={token}",
        "expires_at": expires_at.isoformat()
    }


@router.get("/profile")
async def get_client_profile(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """Получить профиль пользователя (Remnawave + Bedolaga)"""
    # Поддерживаем token через query param тоже
    effective_token = x_client_token or token
    client_id = get_client_id_from_request(x_telegram_init_data, effective_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    config = db.settings.find_one({}, {"_id": 0}) or {}
    api_url = (config.get("remnawave_api_url") or "").rstrip("/")
    api_token = config.get("remnawave_api_token") or ""
    bedolaga_url = config.get("bedolaga_api_url") or os.environ.get("BEDOLAGA_API_URL", "")
    bedolaga_token = config.get("bedolaga_api_token") or os.environ.get("BEDOLAGA_API_TOKEN", "")
    
    result = {"client_id": client_id, "remnawave": None, "bedolaga": None}
    
    import httpx
    if api_url and api_token:
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                headers = {"Authorization": f"Bearer {api_token}"}
                r = await http.get(f"{api_url}/api/users/by-telegram-id/{client_id}", headers=headers)
                if r.status_code == 200:
                    raw = r.json().get("response")
                    if isinstance(raw, list):
                        user = raw[0] if raw else None
                    elif isinstance(raw, dict) and raw.get("uuid"):
                        user = raw
                    else:
                        user = None
                    
                    if user:
                        uuid = user.get("uuid", "")
                        result["remnawave"] = {"user": user}
                        
                        # Подписка
                        try:
                            r2 = await http.get(f"{api_url}/api/subscriptions/by-uuid/{uuid}", headers=headers)
                            if r2.status_code == 200:
                                result["remnawave"]["subscription"] = r2.json().get("response")
                        except: pass
                        
                        # HWID
                        try:
                            r3 = await http.get(f"{api_url}/api/hwid/devices/{uuid}", headers=headers)
                            if r3.status_code == 200:
                                hwid_raw = r3.json().get("response", {})
                                result["remnawave"]["devices"] = hwid_raw.get("devices", []) if isinstance(hwid_raw, dict) else []
                        except: pass
                    else:
                        result["remnawave"] = {"not_found": True}
        except Exception as e:
            result["remnawave"] = {"error": str(e)}
    
    # Bedolaga
    if bedolaga_url and bedolaga_token:
        try:
            async with httpx.AsyncClient(timeout=8) as http:
                headers = {"Authorization": f"Bearer {bedolaga_token}"}
                r = await http.get(f"{bedolaga_url.rstrip('/')}/api/users/by-telegram-id/{client_id}", headers=headers)
                if r.status_code == 200:
                    result["bedolaga"] = r.json()
        except Exception as e:
            result["bedolaga"] = {"error": str(e)}
    
    return {"ok": True, **result}


@router.get("/tickets")
async def get_client_tickets(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """Получить список тикетов пользователя"""
    effective_token = x_client_token or token
    client_id = get_client_id_from_request(x_telegram_init_data, effective_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    tickets = list(db.tickets.find(
        {"client_id": client_id},
        sort=[("created_at", -1)],
        limit=20
    ))
    
    return {"ok": True, "tickets": [serialize_ticket_for_client(t) for t in tickets]}


@router.get("/tickets/active")
async def get_client_active_ticket(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """Получить активный тикет пользователя"""
    effective_token = x_client_token or token
    client_id = get_client_id_from_request(x_telegram_init_data, effective_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    ticket = db.tickets.find_one(
        {"client_id": client_id, "is_removed": {"$ne": True}, "status": {"$ne": "closed"}},
        sort=[("created_at", -1)]
    )
    
    if not ticket:
        return {"ok": True, "ticket": None}
    
    return {"ok": True, "ticket": serialize_ticket_for_client(ticket)}


@router.post("/tickets/message")
async def send_client_message(
    data: dict = Body(...),
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """Отправить сообщение от клиента через портал (не через Telegram бот)"""
    effective_token = x_client_token or token
    client_id = get_client_id_from_request(x_telegram_init_data, effective_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    message = (data.get("message") or "").strip()
    if not message:
        return {"ok": False, "error": "message_required"}
    
    db = get_db()
    
    # Находим активный тикет
    ticket = db.tickets.find_one(
        {"client_id": client_id, "is_removed": {"$ne": True}, "status": {"$ne": "closed"}},
        sort=[("created_at", -1)]
    )
    
    msg_record = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "via": "portal"
    }
    
    if ticket:
        db.tickets.update_one(
            {"_id": ticket["_id"]},
            {
                "$push": {"history": msg_record},
                "$set": {"last_user_message_at": datetime.now(timezone.utc)}
            }
        )
        ticket_id = str(ticket["_id"])
    else:
        # Создаём новый тикет
        new_ticket = {
            "client_id": client_id,
            "client_name": data.get("client_name", f"User {client_id}"),
            "client_username": data.get("client_username", ""),
            "status": "open",
            "reason": "Обращение через портал",
            "history": [msg_record],
            "last_messages": [msg_record],
            "attachments": [],
            "created_at": datetime.now(timezone.utc),
            "is_removed": False,
        }
        result = db.tickets.insert_one(new_ticket)
        ticket_id = str(result.inserted_id)
    
    # Пересылаем в группу поддержки (если есть бот)
    config = db.settings.find_one({}, {"_id": 0}) or {}
    support_group_id = config.get("support_group_id")
    
    return {"ok": True, "ticket_id": ticket_id, "message": "Сообщение отправлено"}


@router.get("/tickets/{ticket_id}/history")  
async def get_ticket_history(
    ticket_id: str,
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """Получить полную историю конкретного тикета"""
    effective_token = x_client_token or token
    client_id = get_client_id_from_request(x_telegram_init_data, effective_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(status_code=400, detail="Invalid ticket_id")
    
    ticket = db.tickets.find_one({"_id": ObjectId(ticket_id), "client_id": client_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    return {"ok": True, "history": ticket.get("history", []), "status": ticket.get("status")}

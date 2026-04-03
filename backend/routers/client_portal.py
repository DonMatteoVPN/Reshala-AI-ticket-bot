"""
Client Portal Router — API для клиентского самообслуживания.

Позволяет пользователям через браузер или Telegram Mini App:
  - Видеть свой профиль (Remnawave + Bedolaga)
  - Читать историю тикетов и переписку
  - Отправлять сообщения в поддержку
  - Генерировать magic-link для входа без Telegram

Авторизация поддерживается двумя способами:
  1. Telegram WebApp initData (заголовок X-Telegram-Init-Data)
  2. Magic-link токен (заголовок X-Client-Token или query-параметр ?token=)
"""
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import unquote

import httpx
from bson import ObjectId
from fastapi import APIRouter, Body, Header, HTTPException, Query
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────

def _get_db():
    """Возвращает pymongo Database (синхронно, для простоты)."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
    db_name = os.environ.get("DB_NAME", "reshala_support")
    return MongoClient(mongo_url)[db_name]


def _verify_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """
    Верифицирует Telegram WebApp initData через HMAC-SHA256.
    Возвращает объект user или None при ошибке.
    """
    try:
        params: dict[str, str] = {}
        for part in init_data.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v

        received_hash = params.pop("hash", "")
        data_check = "\n".join(sorted(f"{k}={v}" for k, v in params.items()))

        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(received_hash, expected):
            return None

        user_str = params.get("user", "{}")
        return json.loads(unquote(user_str))
    except Exception as exc:
        logger.warning("_verify_telegram_init_data error: %s", exc)
        return None


def _get_client_id(
    x_telegram_init_data: Optional[str],
    x_client_token: Optional[str],
) -> Optional[int]:
    """
    Разрешает client_id из заголовков.
    Приоритет: Telegram initData → magic-token.
    """
    db = _get_db()
    bot_token = os.environ.get("BOT_TOKEN", "")
    skip_auth = os.environ.get("SKIP_AUTH", "false").lower() == "true"

    # 1. Telegram initData
    if x_telegram_init_data:
        if skip_auth:
            # Dev-режим: парсим без верификации
            try:
                for part in x_telegram_init_data.split("&"):
                    if part.startswith("user="):
                        user = json.loads(unquote(part[5:]))
                        return user.get("id")
            except Exception:
                pass
        else:
            user = _verify_telegram_init_data(x_telegram_init_data, bot_token)
            if user:
                return user.get("id")

    # 2. Magic-link токен
    if x_client_token:
        doc = db.client_tokens.find_one({
            "token": x_client_token,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        })
        if doc:
            return doc.get("client_id")

    return None


def _serialize_ticket(ticket: dict) -> dict:
    """Сериализация тикета для клиента (без внутренней служебной информации)."""
    return {
        "id": str(ticket.get("_id", "")),
        "status": ticket.get("status", "open"),
        "reason": ticket.get("reason"),
        "created_at": (
            ticket["created_at"].isoformat()
            if ticket.get("created_at") else None
        ),
        "closed_at": (
            ticket["closed_at"].isoformat()
            if ticket.get("closed_at") else None
        ),
        "escalated_at": (
            ticket["escalated_at"].isoformat()
            if ticket.get("escalated_at") else None
        ),
        "history": ticket.get("history", []),
        "last_messages": ticket.get("last_messages", []),
        "attachments": ticket.get("attachments", []),
        "ai_disabled": ticket.get("ai_disabled", False),
    }


# ─────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────

@router.post("/auth/generate-link")
async def generate_magic_link(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
):
    """
    Генерирует magic-link токен (действителен 7 дней).
    Позволяет открыть портал в браузере без Telegram.
    """
    client_id = _get_client_id(x_telegram_init_data, x_client_token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = _get_db()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    db.client_tokens.replace_one(
        {"client_id": client_id},
        {
            "client_id": client_id,
            "token": token,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )

    config = db.settings.find_one({}, {"_id": 0}) or {}
    mini_app_url = config.get("miniapp_url") or (
        f"https://{config.get('mini_app_domain', '')}"
        if config.get("mini_app_domain") else ""
    )

    return {
        "ok": True,
        "token": token,
        "link": f"{mini_app_url.rstrip('/')}/client?token={token}",
        "expires_at": expires_at.isoformat(),
    }


@router.get("/profile")
async def get_client_profile(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """
    Возвращает полный профиль пользователя:
    Remnawave (подписка, трафик, устройства) + Bedolaga (баланс).
    """
    client_id = _get_client_id(x_telegram_init_data, x_client_token or token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = _get_db()
    config = db.settings.find_one({}, {"_id": 0}) or {}
    api_url = (config.get("remnawave_api_url") or "").rstrip("/")
    api_token = config.get("remnawave_api_token") or ""
    bedolaga_url = (
        config.get("bedolaga_api_url")
        or os.environ.get("BEDOLAGA_API_URL", "")
    )
    bedolaga_token = (
        config.get("bedolaga_api_token")
        or os.environ.get("BEDOLAGA_API_TOKEN", "")
    )

    result: dict = {"client_id": client_id, "remnawave": None, "bedolaga": None}

    async with httpx.AsyncClient(timeout=10) as http:
        # Remnawave
        if api_url and api_token:
            headers = {"Authorization": f"Bearer {api_token}"}
            try:
                r = await http.get(
                    f"{api_url}/api/users/by-telegram-id/{client_id}",
                    headers=headers,
                )
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
                            r2 = await http.get(
                                f"{api_url}/api/subscriptions/by-uuid/{uuid}",
                                headers=headers,
                            )
                            if r2.status_code == 200:
                                result["remnawave"]["subscription"] = (
                                    r2.json().get("response")
                                )
                        except Exception:
                            pass

                        # HWID-устройства
                        try:
                            r3 = await http.get(
                                f"{api_url}/api/hwid/devices/{uuid}",
                                headers=headers,
                            )
                            if r3.status_code == 200:
                                hwid_raw = r3.json().get("response", {})
                                result["remnawave"]["devices"] = (
                                    hwid_raw.get("devices", [])
                                    if isinstance(hwid_raw, dict) else []
                                )
                        except Exception:
                            pass
                    else:
                        result["remnawave"] = {"not_found": True}
                elif r.status_code == 404:
                    result["remnawave"] = {"not_found": True}
            except Exception as exc:
                result["remnawave"] = {"error": str(exc)}

        # Bedolaga
        if bedolaga_url and bedolaga_token:
            headers_b = {"Authorization": f"Bearer {bedolaga_token}"}
            try:
                rb = await http.get(
                    f"{bedolaga_url.rstrip('/')}/api/users/by-telegram-id/{client_id}",
                    headers=headers_b,
                )
                if rb.status_code == 200:
                    result["bedolaga"] = rb.json()
            except Exception as exc:
                result["bedolaga"] = {"error": str(exc)}

    return {"ok": True, **result}


@router.get("/tickets")
async def get_client_tickets(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Возвращает историю тикетов пользователя (последние 20)."""
    client_id = _get_client_id(x_telegram_init_data, x_client_token or token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = _get_db()
    tickets = list(
        db.tickets.find(
            {"client_id": client_id},
        ).sort("created_at", -1).limit(20)
    )
    return {"ok": True, "tickets": [_serialize_ticket(t) for t in tickets]}


@router.get("/tickets/active")
async def get_client_active_ticket(
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Возвращает текущий открытый тикет пользователя (если есть)."""
    client_id = _get_client_id(x_telegram_init_data, x_client_token or token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = _get_db()
    ticket = db.tickets.find_one(
        {
            "client_id": client_id,
            "is_removed": {"$ne": True},
            "status": {"$ne": "closed"},
        },
        sort=[("created_at", -1)],
    )
    return {"ok": True, "ticket": _serialize_ticket(ticket) if ticket else None}


@router.post("/tickets/message")
async def send_client_message(
    data: dict = Body(...),
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """
    Отправить сообщение от клиента через портал.
    Если активный тикет есть — добавляет в него.
    Если нет — создаёт новый тикет со статусом 'open'.
    """
    client_id = _get_client_id(x_telegram_init_data, x_client_token or token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    message = (data.get("message") or "").strip()
    if not message:
        return {"ok": False, "error": "message_required"}

    db = _get_db()

    msg_record = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "via": "portal",
    }

    ticket = db.tickets.find_one(
        {
            "client_id": client_id,
            "is_removed": {"$ne": True},
            "status": {"$ne": "closed"},
        },
        sort=[("created_at", -1)],
    )

    if ticket:
        db.tickets.update_one(
            {"_id": ticket["_id"]},
            {
                "$push": {"history": msg_record},
                "$set": {"last_user_message_at": datetime.now(timezone.utc)},
            },
        )
        ticket_id = str(ticket["_id"])
    else:
        new_ticket = {
            "client_id": client_id,
            "client_name": data.get("client_name", f"User {client_id}"),
            "client_username": data.get("client_username", ""),
            "status": "open",
            "reason": "Обращение через портал самообслуживания",
            "history": [msg_record],
            "last_messages": [msg_record],
            "attachments": [],
            "created_at": datetime.now(timezone.utc),
            "is_removed": False,
            "ai_disabled": False,
        }
        result = db.tickets.insert_one(new_ticket)
        ticket_id = str(result.inserted_id)

    return {"ok": True, "ticket_id": ticket_id}


@router.get("/tickets/{ticket_id}/history")
async def get_ticket_history(
    ticket_id: str,
    x_telegram_init_data: Optional[str] = Header(None),
    x_client_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Возвращает полную историю переписки по конкретному тикету."""
    client_id = _get_client_id(x_telegram_init_data, x_client_token or token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(status_code=400, detail="Invalid ticket_id")

    db = _get_db()
    ticket = db.tickets.find_one(
        {"_id": ObjectId(ticket_id), "client_id": client_id}
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "ok": True,
        "history": ticket.get("history", []),
        "status": ticket.get("status"),
    }

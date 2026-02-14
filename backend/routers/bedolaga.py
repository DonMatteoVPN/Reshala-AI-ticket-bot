"""
Bedolaga API Router — проверка баланса и история пополнений

ПРАВИЛЬНАЯ РЕАЛИЗАЦИЯ:
- Заголовок авторизации: X-API-Key (НЕ Bearer!)
- Эндпоинт баланса: GET /users/{telegram_id}
- Эндпоинт транзакций: GET /transactions?user_id={bedolaga_id}
"""
from fastapi import APIRouter
from pymongo import MongoClient
import httpx
import os

router = APIRouter()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reshala_support")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def _get_bedolaga_config():
    """Получить URL и токен Bedolaga из настроек"""
    config = db.settings.find_one({}, {"_id": 0}) or {}
    # Поддержка старых и новых названий полей
    api_url = (config.get("bedolaga_webhook_url") or config.get("bedolaga_api_url") or "").rstrip("/")
    api_token = config.get("bedolaga_web_api_token") or config.get("bedolaga_api_token") or ""
    return api_url, api_token


@router.get("/balance/{telegram_id}")
async def get_balance(telegram_id: int):
    """Получить баланс пользователя через Bedolaga API"""
    api_url, api_token = _get_bedolaga_config()
    
    if not api_url or not api_token:
        return {"ok": False, "error": "Bedolaga API не настроен"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            # ПРАВИЛЬНЫЙ эндпоинт и заголовок авторизации
            r = await http_client.get(
                f"{api_url}/users/{telegram_id}",
                headers={"X-API-Key": api_token}  # НЕ Bearer!
            )
            
            if r.status_code == 200:
                data = r.json()
                # Баланс может быть в рублях или копейках
                balance = data.get("balance_rubles")
                if balance is None:
                    balance = data.get("balance_kopeks", 0) / 100
                
                return {
                    "ok": True,
                    "balance": balance,
                    "currency": "RUB",
                    "bedolaga_user_id": data.get("id"),  # Внутренний ID для транзакций
                }
            elif r.status_code == 404:
                return {"ok": True, "balance": 0, "currency": "RUB", "message": "Пользователь не найден в Bedolaga"}
            else:
                return {"ok": False, "error": f"Ошибка API: {r.status_code}"}
                
    except httpx.TimeoutException:
        return {"ok": False, "error": "Timeout при запросе к Bedolaga"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/deposits/{telegram_id}")
async def get_deposits(telegram_id: int, limit: int = 30):
    """Получить историю транзакций (пополнений) пользователя"""
    api_url, api_token = _get_bedolaga_config()
    
    if not api_url or not api_token:
        return {"ok": False, "error": "Bedolaga API не настроен", "deposits": []}
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            # Шаг 1: Получаем внутренний ID пользователя Bedolaga
            user_r = await http_client.get(
                f"{api_url}/users/{telegram_id}",
                headers={"X-API-Key": api_token}
            )
            
            if user_r.status_code != 200:
                return {"ok": False, "deposits": [], "error": "Пользователь не найден в Bedolaga"}
            
            bedolaga_user_id = user_r.json().get("id")
            if not bedolaga_user_id:
                return {"ok": False, "deposits": [], "error": "Не получен ID пользователя"}
            
            # Шаг 2: Получаем транзакции по внутреннему ID
            tx_r = await http_client.get(
                f"{api_url}/transactions",
                params={"user_id": bedolaga_user_id, "limit": limit, "offset": 0},
                headers={"X-API-Key": api_token}
            )
            
            if tx_r.status_code == 200:
                data = tx_r.json()
                items = data.get("items") or []
                
                # Нормализуем формат для фронтенда
                deposits = []
                for item in items:
                    amount = item.get("amount_rubles")
                    if amount is None:
                        amount = item.get("amount_kopeks", 0) / 100
                    
                    deposits.append({
                        "amount": amount,
                        "currency": "RUB",
                        "type": item.get("type", ""),
                        "description": item.get("description", ""),
                        "method": item.get("method") or item.get("type", ""),
                        "created_at": item.get("created_at", ""),
                        "status": item.get("status", "completed"),
                    })
                
                return {"ok": True, "deposits": deposits}
            
            return {"ok": False, "deposits": [], "error": f"Ошибка получения транзакций: {tx_r.status_code}"}
            
    except Exception as e:
        return {"ok": False, "error": str(e), "deposits": []}

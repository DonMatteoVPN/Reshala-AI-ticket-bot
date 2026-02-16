"""
Bedolaga API Router — проверка баланса и история пополнений

ПРАВИЛЬНАЯ РЕАЛИЗАЦИЯ:
- Заголовок авторизации: X-API-Key (НЕ Bearer!)
- Эндпоинт баланса: GET /users/{telegram_id}
- Эндпоинт транзакций: GET /transactions?user_id={bedolaga_id}
"""
from fastapi import APIRouter
from utils.bedolaga_api import fetch_bedolaga_balance, fetch_bedolaga_transactions

router = APIRouter()

@router.get("/balance/{telegram_id}")
async def get_balance(telegram_id: int):
    """Получить баланс пользователя через Bedolaga API"""
    data = await fetch_bedolaga_balance(telegram_id)
    
    if data:
        return {
            "ok": True,
            "balance": data.get("balance"),
            "currency": data.get("currency", "RUB"),
            "bedolaga_user_id": data.get("id"),
        }
    else:
        # Если data пустое, это может быть ошибка сети или конфига, или юзер не найден.
        # utils функция возвращает {} при ошибке.
        # Для совместимости вернем generic error или 0 баланс?
        # В старом коде 404 возвращал balance: 0.
        return {"ok": False, "error": "Не удалось получить данные (API не настроен или ошибка)"}


@router.get("/deposits/{telegram_id}")
async def get_deposits(telegram_id: int, limit: int = 30):
    """Получить историю транзакций (пополнений) пользователя"""
    # 1. Get user to find internal ID
    balance_data = await fetch_bedolaga_balance(telegram_id)
    bedolaga_user_id = balance_data.get("id")
    
    if not bedolaga_user_id:
        return {"ok": False, "deposits": [], "error": "Пользователь не найден в Bedolaga"}
    
    # 2. Get transactions
    items = await fetch_bedolaga_transactions(bedolaga_user_id)
    if not items:
        # Если items пустой список, то ок, просто нет депозитов.
        return {"ok": True, "deposits": []}

    # 3. Normalize
    deposits = []
    for item in items[:limit]:
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

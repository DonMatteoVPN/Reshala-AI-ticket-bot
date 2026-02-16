import httpx
import logging
from utils.db_config import get_settings

logger = logging.getLogger(__name__)

async def fetch_bedolaga_balance(telegram_id: int) -> dict:
    """
    Get balance from Bedolaga API.
    """
    config = get_settings()
    api_url = (config.get("bedolaga_webhook_url") or config.get("bedolaga_api_url") or "").rstrip("/")
    api_token = config.get("bedolaga_web_api_token") or config.get("bedolaga_api_token") or ""
    
    if not api_url or not api_token:
        return {}
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            r = await http_client.get(
                f"{api_url}/users/{telegram_id}",
                headers={"X-API-Key": api_token}
            )
            if r.status_code == 200:
                data = r.json()
                # Balance can be in rubles or kopecks
                balance = data.get("balance_rubles")
                if balance is None:
                    balance = data.get("balance_kopeks", 0) / 100
                return {
                    "balance": balance,
                    "currency": "RUB",
                    "id": data.get("id")  # Internal ID for transactions
                }
    except Exception as e:
        logger.warning(f"fetch_bedolaga_balance error: {e}")
    return {}


async def fetch_bedolaga_transactions(bedolaga_user_id: int) -> list:
    """
    Get transactions from Bedolaga API.
    """
    config = get_settings()
    api_url = (config.get("bedolaga_webhook_url") or config.get("bedolaga_api_url") or "").rstrip("/")
    api_token = config.get("bedolaga_web_api_token") or config.get("bedolaga_api_token") or ""
    
    if not api_url or not api_token or not bedolaga_user_id:
        return []
    
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            r = await http_client.get(
                f"{api_url}/transactions",
                params={"user_id": bedolaga_user_id, "limit": 30, "offset": 0},
                headers={"X-API-Key": api_token}
            )
            if r.status_code == 200:
                return r.json().get("items") or []
    except Exception as e:
        logger.warning(f"fetch_bedolaga_transactions error: {e}")
    return []


async def fetch_bedolaga_deposits(telegram_id: int) -> list:
    """Get deposit history (wrapper for compatibility)"""
    # First get balance to get internal ID
    balance_data = await fetch_bedolaga_balance(telegram_id)
    bedolaga_user_id = balance_data.get("id")
    
    if not bedolaga_user_id:
        return []
    
    # Get transactions by internal ID
    items = await fetch_bedolaga_transactions(bedolaga_user_id)
    
    # Normalize format
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
            "created_at": item.get("created_at", ""),
        })
    
    return deposits

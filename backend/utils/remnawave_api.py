import httpx
import logging
from utils.db_config import get_settings

logger = logging.getLogger(__name__)

async def fetch_user_data(telegram_id: int) -> dict:
    """Получение полных данных пользователя из Remnawave API"""
    config = get_settings()
    api_url = config.get("remnawave_api_url", "").rstrip("/")
    api_token = config.get("remnawave_api_token", "")
    
    if not api_url or not api_token:
        return {"not_configured": True}
    
    headers = {"Authorization": f"Bearer {api_token}"}
    result = {}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Используем тот же эндпоинт что и Mini App
            r = await client.get(f"{api_url}/api/users/by-telegram-id/{telegram_id}", headers=headers)
            
            if r.status_code == 200:
                data = r.json()
                raw = data.get("response")
                
                # API может вернуть список или объект
                if isinstance(raw, list):
                    user = raw[0] if raw else None
                elif isinstance(raw, dict) and raw.get("uuid"):
                    user = raw
                else:
                    user = None
                
                if not user:
                    result["not_found"] = True
                    return result
                
                result["user"] = user
                uuid = user.get("uuid", "")
                
                # Получаем подписку
                if uuid:
                    try:
                        r2 = await client.get(f"{api_url}/api/subscriptions/by-uuid/{uuid}", headers=headers)
                        if r2.status_code == 200:
                            result["subscription"] = r2.json().get("response")
                    except:
                        pass
                    
                    # Получаем HWID устройства
                    try:
                        r3 = await client.get(f"{api_url}/api/hwid/devices/{uuid}", headers=headers)
                        if r3.status_code == 200:
                            devices_data = r3.json().get("response", {})
                            result["devices"] = devices_data.get("devices", []) if isinstance(devices_data, dict) else []
                    except:
                        pass
                        
            elif r.status_code == 404:
                result["not_found"] = True
            else:
                result["error"] = f"API error: {r.status_code}"
                
    except Exception as e:
        logger.warning(f"fetch_user_data: {e}")
        result["error"] = str(e)
    
    return result

async def remnawave_action(user_uuid: str, action_type: str) -> dict:
    """
    Выполнение действий над пользователем Remnawave.
    action_type: reset_traffic, revoke_sub, disable, enable, hwid_all
    """
    config = get_settings()
    api_url = config.get("remnawave_api_url", "").rstrip("/")
    api_token = config.get("remnawave_api_token", "")
    
    if not api_url or not api_token:
        return {"error": "not_configured"}
        
    headers = {"Authorization": f"Bearer {api_token}"}
    
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            if action_type == "reset_traffic":
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/reset-traffic", headers=headers)
                return {"ok": r.status_code == 200, "status": r.status_code}
                
            elif action_type == "revoke_sub":
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/revoke", json={}, headers=headers)
                return {"ok": r.status_code == 200, "status": r.status_code}
                
            elif action_type == "disable":
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/disable", json={}, headers=headers)
                return {"ok": r.status_code == 200, "status": r.status_code}
                
            elif action_type == "enable":
                r = await http.post(f"{api_url}/api/users/{user_uuid}/actions/enable", json={}, headers=headers)
                return {"ok": r.status_code == 200, "status": r.status_code}
                
            elif action_type == "hwid_all":
                r = await http.post(f"{api_url}/api/hwid/devices/delete-all", json={"userUuid": user_uuid}, headers=headers)
                return {"ok": r.status_code == 200, "status": r.status_code}
                
    except Exception as e:
        logger.error(f"remnawave_action {action_type} error: {e}")
        return {"error": str(e)}
    
    return {"error": "unknown_action"}


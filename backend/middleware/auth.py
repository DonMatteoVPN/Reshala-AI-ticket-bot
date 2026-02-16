
import hashlib
import hmac
import json
import urllib.parse
import os
from typing import Dict, Optional

from fastapi import Header, HTTPException, Depends, Request
from utils.db_config import get_bot_token

async def verify_telegram_auth(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    """
    Validates Telegram WebApp initData.
    Expects header: X-Telegram-Init-Data
    """
    # SKIP_AUTH for local development/debugging
    skip_auth = os.environ.get("SKIP_AUTH", "false").lower() == "true"

    if not x_telegram_init_data:
        if skip_auth:
            # Return a dummy manager for development
            # Usually the first manager from ALLOWED_MANAGER_IDS
            from utils.db_config import get_settings
            config = get_settings()
            managers = config.get("allowed_manager_ids", [0])
            manager_id = managers[0] if managers else 0
            
            return {"id": manager_id, "first_name": "Dev", "last_name": "Manager", "username": "dev_manager"}
            
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")

    bot_token = get_bot_token()
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    try:
        parsed_data = urllib.parse.parse_qs(x_telegram_init_data)
        data_dict = {k: v[0] for k, v in parsed_data.items()}
        
        if "hash" not in data_dict:
            raise HTTPException(status_code=401, detail="Invalid initData: missing hash")

        hash_value = data_dict.pop("hash")
        
        # Sort keys alpha
        data_check_string = "\n".join(f"{k}={data_dict[k]}" for k in sorted(data_dict.keys()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if calculated_hash != hash_value:
             raise HTTPException(status_code=403, detail="Invalid initData signature")

        # Parse user data if needed
        user_data = json.loads(data_dict.get("user", "{}"))
        return user_data

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth failed: {str(e)}")

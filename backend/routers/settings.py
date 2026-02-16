from fastapi import APIRouter, Body, Depends
from middleware.auth import verify_telegram_auth

import sys
import os

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.db_config import get_db, get_settings

router = APIRouter()
db = get_db()


def mask_secret(secret: str) -> str:
    if not secret or len(secret) < 8:
        return "***"
    return secret[:4] + "***" + secret[-4:]

@router.get("")
def get_settings_endpoint(user_data: dict = Depends(verify_telegram_auth)):
    doc = get_settings()
    if not doc:
        return {"error": "no settings"}
    
    # Mask critical secrets
    sensitive_keys = ["bot_token", "remnawave_api_token", "bedolaga_api_token"]
    for key in sensitive_keys:
        if key in doc:
            doc[key] = mask_secret(doc[key])
            
    return doc


@router.put("")
def update_settings(data: dict = Body(...), user_data: dict = Depends(verify_telegram_auth)):
    protected = ["_id"]
    update = {}
    
    for k, v in data.items():
        if k in protected:
            continue
        # Skip masked values
        if isinstance(v, str) and "***" in v:
            continue
        update[k] = v
        
    if not update:
        return {"ok": False, "error": "nothing to update"}
    db.settings.update_one({}, {"$set": update})
    return {"ok": True}


@router.get("/providers")
def get_providers():
    providers = list(db.ai_providers.find({}, {"_id": 0}))
    for p in providers:
        keys = p.get("api_keys", [])
        p["keys_count"] = len(keys)
        p["api_keys_masked"] = [k[:8] + "..." + k[-4:] if len(k) > 12 else "***" for k in keys]
    return {"providers": providers}


@router.put("/providers/{name}")
def update_provider(name: str, data: dict = Body(...)):
    protected = ["_id", "name"]
    update = {k: v for k, v in data.items() if k not in protected}
    if not update:
        return {"ok": False, "error": "nothing to update"}
    db.ai_providers.update_one({"name": name}, {"$set": update})
    return {"ok": True}


@router.post("/providers/{name}/keys")
def add_provider_key(name: str, data: dict = Body(...)):
    key = data.get("key", "").strip()
    if not key:
        return {"ok": False, "error": "key required"}
    db.ai_providers.update_one({"name": name}, {"$addToSet": {"api_keys": key}})
    return {"ok": True}


@router.delete("/providers/{name}/keys/{index}")
def remove_provider_key(name: str, index: int):
    provider = db.ai_providers.find_one({"name": name})
    if not provider:
        return {"ok": False, "error": "provider not found"}
    keys = provider.get("api_keys", [])
    if 0 <= index < len(keys):
        keys.pop(index)
        active_idx = provider.get("active_key_index", 0)
        if active_idx >= len(keys):
            active_idx = max(0, len(keys) - 1)
        db.ai_providers.update_one(
            {"name": name},
            {"$set": {"api_keys": keys, "active_key_index": active_idx}}
        )
        return {"ok": True}
    return {"ok": False, "error": "invalid index"}

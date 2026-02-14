from fastapi import APIRouter, Body
from pymongo import MongoClient
import os

router = APIRouter()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reshala_support")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


@router.get("")
def get_settings():
    doc = db.settings.find_one({}, {"_id": 0})
    if not doc:
        return {"error": "no settings"}
    return doc


@router.put("")
def update_settings(data: dict = Body(...)):
    protected = ["_id"]
    update = {k: v for k, v in data.items() if k not in protected}
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

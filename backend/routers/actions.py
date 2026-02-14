from fastapi import APIRouter, Body
import requests
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_api():
    from pymongo import MongoClient
    MONGO_URL = os.environ.get("MONGO_URL")
    DB_NAME = os.environ.get("DB_NAME", "reshala_support")
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    settings = db.settings.find_one({}, {"_id": 0})
    if not settings:
        return None, None
    return settings.get("remnawave_api_url", "").rstrip("/"), settings.get("remnawave_api_token", "")


def _api_post(path: str, body=None):
    api_url, token = _get_api()
    if not api_url or not token:
        return False, "API not configured"
    try:
        r = requests.post(
            f"{api_url}{path}",
            json=body or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        return r.status_code == 200, f"HTTP {r.status_code}" if r.status_code != 200 else "OK"
    except Exception as e:
        return False, str(e)


@router.post("/reset-traffic")
def reset_traffic(data: dict = Body(...)):
    uuid = data.get("userUuid", "").strip()
    if not uuid:
        return {"ok": False, "error": "userUuid required"}
    ok, msg = _api_post(f"/api/users/{uuid}/actions/reset-traffic")
    return {"ok": ok, "message": "Трафик сброшен." if ok else msg}


@router.post("/revoke-subscription")
def revoke_sub(data: dict = Body(...)):
    uuid = data.get("userUuid", "").strip()
    if not uuid:
        return {"ok": False, "error": "userUuid required"}
    ok, msg = _api_post(f"/api/users/{uuid}/actions/revoke")
    return {"ok": ok, "message": "Подписка перевыпущена." if ok else msg}


@router.post("/enable-user")
def enable_user(data: dict = Body(...)):
    uuid = data.get("userUuid", "").strip()
    if not uuid:
        return {"ok": False, "error": "userUuid required"}
    ok, msg = _api_post(f"/api/users/{uuid}/actions/enable")
    return {"ok": ok, "message": "Профиль включён." if ok else msg}


@router.post("/disable-user")
def disable_user(data: dict = Body(...)):
    uuid = data.get("userUuid", "").strip()
    if not uuid:
        return {"ok": False, "error": "userUuid required"}
    ok, msg = _api_post(f"/api/users/{uuid}/actions/disable")
    return {"ok": ok, "message": "Профиль заблокирован." if ok else msg}


@router.post("/hwid-delete-all")
def hwid_delete_all(data: dict = Body(...)):
    uuid = data.get("userUuid", "").strip()
    if not uuid:
        return {"ok": False, "error": "userUuid required"}
    ok, msg = _api_post("/api/hwid/devices/delete-all", {"userUuid": uuid})
    return {"ok": ok, "message": "Все устройства удалены." if ok else msg}


@router.post("/hwid-delete")
def hwid_delete(data: dict = Body(...)):
    uuid = data.get("userUuid", "").strip()
    hwid = data.get("hwid", "").strip()
    if not uuid or not hwid:
        return {"ok": False, "error": "userUuid and hwid required"}
    ok, msg = _api_post("/api/hwid/devices/delete", {"userUuid": uuid, "hwid": hwid})
    return {"ok": ok, "message": "Устройство удалено." if ok else msg}

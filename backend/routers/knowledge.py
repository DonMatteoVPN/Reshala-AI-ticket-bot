from fastapi import APIRouter, Body
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone
import os

router = APIRouter()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reshala_support")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


@router.get("")
def get_articles():
    articles = list(db.knowledge_base.find({}).sort("updated_at", -1))
    for a in articles:
        a["id"] = str(a.pop("_id"))
    return {"articles": articles}


@router.get("/{article_id}")
def get_article(article_id: str):
    try:
        doc = db.knowledge_base.find_one({"_id": ObjectId(article_id)})
    except Exception:
        return {"ok": False, "error": "invalid_id"}
    if not doc:
        return {"ok": False, "error": "not_found"}
    doc["id"] = str(doc.pop("_id"))
    return {"ok": True, "article": doc}


@router.post("")
def create_article(data: dict = Body(...)):
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    category = (data.get("category") or "general").strip()
    if not title or not content:
        return {"ok": False, "error": "title and content required"}
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "title": title,
        "content": content,
        "category": category,
        "created_at": now,
        "updated_at": now,
    }
    result = db.knowledge_base.insert_one(doc)
    return {"ok": True, "id": str(result.inserted_id)}


@router.put("/{article_id}")
def update_article(article_id: str, data: dict = Body(...)):
    try:
        oid = ObjectId(article_id)
    except Exception:
        return {"ok": False, "error": "invalid_id"}
    update = {}
    for k in ["title", "content", "category"]:
        if k in data:
            update[k] = data[k]
    if not update:
        return {"ok": False, "error": "nothing to update"}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    db.knowledge_base.update_one({"_id": oid}, {"$set": update})
    return {"ok": True}


@router.delete("/{article_id}")
def delete_article(article_id: str):
    try:
        oid = ObjectId(article_id)
    except Exception:
        return {"ok": False, "error": "invalid_id"}
    result = db.knowledge_base.delete_one({"_id": oid})
    return {"ok": result.deleted_count > 0}


@router.get("/search/{query}")
def search_articles(query: str):
    regex = {"$regex": query, "$options": "i"}
    articles = list(db.knowledge_base.find(
        {"$or": [{"title": regex}, {"content": regex}, {"category": regex}]}
    ).sort("updated_at", -1).limit(20))
    for a in articles:
        a["id"] = str(a.pop("_id"))
    return {"articles": articles}

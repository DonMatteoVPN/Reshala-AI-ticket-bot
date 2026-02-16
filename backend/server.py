import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

# Rate Limiting
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from middleware.rate_limit import limiter

# Exception Handlers
from exception_handlers import add_exception_handlers

# Database Indexes
from database.indexes import ensure_indexes

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reshala_support")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def init_default_settings():
    if db.settings.count_documents({}) == 0:
        db.settings.insert_one({
            "service_name": "Решала support",
            "bot_token": "",
            "remnawave_api_url": "",
            "remnawave_api_token": "",
            "allowed_manager_ids": [],
            "support_group_id": None,
            "mini_app_domain": "",
            "bedolaga_api_url": "",
            "bedolaga_api_token": "",
            "ai_enabled": True,
            "active_provider": "",
            "system_prompt_override": "",
        })
    if db.ai_providers.count_documents({}) == 0:
        providers = [
            {"name": "groq", "display_name": "Groq", "api_keys": [], "active_key_index": 0, "base_url": "https://api.groq.com/openai/v1", "models": [], "selected_model": "", "vision_model": "", "enabled": False, "proxy": ""},
            {"name": "openai", "display_name": "OpenAI", "api_keys": [], "active_key_index": 0, "base_url": "https://api.openai.com/v1", "models": [], "selected_model": "", "vision_model": "", "enabled": False, "proxy": ""},
            {"name": "anthropic", "display_name": "Anthropic", "api_keys": [], "active_key_index": 0, "base_url": "https://api.anthropic.com", "models": [], "selected_model": "", "vision_model": "", "enabled": False, "proxy": ""},
            {"name": "google", "display_name": "Google AI (Gemini)", "api_keys": [], "active_key_index": 0, "base_url": "https://generativelanguage.googleapis.com/v1beta", "models": [], "selected_model": "", "vision_model": "", "enabled": False, "proxy": ""},
            {"name": "openrouter", "display_name": "OpenRouter", "api_keys": [], "active_key_index": 0, "base_url": "https://openrouter.ai/api/v1", "models": [], "selected_model": "", "vision_model": "", "enabled": False, "proxy": ""},
        ]
        db.ai_providers.insert_many(providers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize settings
    init_default_settings()
    
    # Create Indexes
    try:
        await ensure_indexes(db)
        logger.info("MongoDB indexes verified.")
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        
    logger.info("Решала support от DonMatteo - Backend started")
    yield
    client.close()


app = FastAPI(title="Решала support от DonMatteo", lifespan=lifespan)

# Rate Limiter Setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global Exception Handlers
add_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.settings import router as settings_router
from routers.ai_router import router as ai_router
from routers.lookup import router as lookup_router
from routers.actions import router as actions_router
from routers.knowledge import router as knowledge_router
from routers.tickets import router as tickets_router
from routers.bedolaga import router as bedolaga_router

app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(lookup_router, prefix="/api/lookup", tags=["lookup"])
app.include_router(actions_router, prefix="/api/actions", tags=["actions"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(tickets_router, prefix="/api/tickets", tags=["tickets"])
app.include_router(bedolaga_router, prefix="/api/bedolaga", tags=["bedolaga"])


@app.get("/api/health")
def health():
    # Simple check
    try:
        client.admin.command('ping')
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
        
    return {
        "status": "ok", 
        "service": "Решала support от DonMatteo",
        "database": db_status
    }

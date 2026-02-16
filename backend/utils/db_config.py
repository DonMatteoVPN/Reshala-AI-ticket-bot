
import os
from pymongo import MongoClient
import logging

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "reshala_support")

# Global client and db
_client = None
_db = None

def get_db():
    """
    Get the MongoDB database instance.
    Initializes connection if not already established.
    """
    global _client, _db
    if _db is None:
        try:
            _client = MongoClient(MONGO_URL)
            _db = _client[DB_NAME]
            # Verify connection
            _client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {DB_NAME}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return None
    return _db

def get_settings():
    """
    Get the current settings from the database, falling back to environment variables.
    This ensures that settings defined in .env are visible in the Mini App and can be overridden.
    """
    db = get_db()
    settings = {}
    if db is not None:
        try:
            settings = db.settings.find_one({}, {"_id": 0}) or {}
        except Exception as e:
            logger.error(f"Error fetching settings: {e}")

    # Environment variable mapping (DB Key -> ENV Key)
    env_mapping = {
        "bot_token": "BOT_TOKEN",
        "remnawave_api_url": "REMNAWAVE_API_URL",
        "remnawave_api_token": "REMNAWAVE_API_TOKEN",
        "support_group_id": "SUPPORT_GROUP_ID",
        "allowed_manager_ids": "ALLOWED_MANAGER_IDS",
        "bedolaga_api_url": "BEDOLAGA_API_URL",
        "bedolaga_api_token": "BEDOLAGA_API_TOKEN",
        "react_app_backend_url": "REACT_APP_BACKEND_URL",
        "miniapp_url": "MINI_APP_URL",
        "mini_app_domain": "MINI_APP_DOMAIN",
        "service_name": "SERVICE_NAME"
    }

    for db_key, env_key in env_mapping.items():
        if db_key not in settings:
            val = os.environ.get(env_key)
            if val:
                # Type conversion
                if db_key == "support_group_id":
                    try: val = int(val)
                    except: pass
                elif db_key == "allowed_manager_ids":
                    try:
                        if isinstance(val, str):
                            val = [int(i.strip()) for i in val.split(",") if i.strip()]
                        elif isinstance(val, (int, float)):
                            val = [int(val)]
                    except Exception as e:
                        logger.error(f"Error parsing allowed_manager_ids: {e}")
                        val = []
                
                # Special case for miniapp_url if only domain is provided
                if db_key == "miniapp_url" and val and not str(val).startswith("http"):
                    val = f"https://{val}"
                
                settings[db_key] = val
    
    # Fallback for miniapp_url from mini_app_domain if miniapp_url still missing
    if "miniapp_url" not in settings:
        domain = settings.get("mini_app_domain")
        if domain:
            if not str(domain).startswith("http"):
                settings["miniapp_url"] = f"https://{domain}"
            else:
                settings["miniapp_url"] = domain

    return settings

def get_bot_token():
    """Get bot token from settings."""
    settings = get_settings()
    return settings.get("bot_token", "")

def get_support_group_id():
    """Get support group ID from settings."""
    settings = get_settings()
    return settings.get("support_group_id")

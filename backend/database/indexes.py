from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

async def ensure_indexes(db: Database):
    """
    Ensure required indexes exist on MongoDB collections.
    This should be called on application startup.
    """
    try:
        # Tickets collection
        # Compound index for active tickets query (escalated first, then created desc)
        # Note: 'status' is heavily filtered
        logger.info("Ensuring indexes for 'tickets' collection...")
        
        # 1. Status + CreatedAt (for sorting/filtering)
        db.tickets.create_index([("status", 1), ("created_at", -1)])
        
        # 2. Client ID (for lookup)
        db.tickets.create_index("client_id")
        
        # 3. Topic ID (for Telegram thread lookup)
        db.tickets.create_index("topic_id")
        
        # 4. Escalated At (for sorting)
        db.tickets.create_index([("escalated_at", -1)])
        
        logger.info("Indexes created successfully.")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from services.ticket_service import TicketService

@pytest.mark.asyncio
async def test_create_ticket():
    """Test ticket creation with Telegram topic"""
    db = MagicMock()
    telegram_service = AsyncMock()
    service = TicketService(db, telegram_service=telegram_service, support_group_id=123)

    # Mock DB insert
    db.tickets.insert_one.return_value.inserted_id = ObjectId()
    
    # Mock Telegram
    telegram_service.create_forum_topic.return_value = 999
    
    result = await service.create_ticket(
        client_id=12345,
        client_name="Test User",
        client_username="testuser",
        user_data={},
        is_suspicious=False
    )
    
    assert result["status"] == "open"
    assert result["topic_id"] == 999
    db.tickets.insert_one.assert_called_once()
    telegram_service.create_forum_topic.assert_called_once()

@pytest.mark.asyncio
async def test_escalate_ticket():
    """Test ticket escalation logic"""
    db = MagicMock()
    service = TicketService(db)
    
    ticket_id = str(ObjectId())
    
    # Mock update
    db.tickets.update_one.return_value.modified_count = 1
    
    success = await service.escalate_ticket(ticket_id, reason="Test Reason")
    
    assert success is True
    db.tickets.update_one.assert_called_once()
    call_args = db.tickets.update_one.call_args
    assert call_args[0][0]["_id"] == ObjectId(ticket_id)
    assert call_args[0][1]["$set"]["status"] == "escalated"

@pytest.mark.asyncio
async def test_close_ticket():
    """Test closing a ticket"""
    db = MagicMock()
    telegram_service = AsyncMock()
    service = TicketService(db, telegram_service, support_group_id=123)
    
    ticket_id = str(ObjectId())
    
    # Mock find
    db.tickets.find_one.return_value = {
        "_id": ObjectId(ticket_id),
        "topic_id": 999,
        "client_id": 12345,
        "status": "escalated"
    }
    
    result = await service.close_ticket(ticket_id, user_id=1, is_manager=True)
    
    assert result["ok"] is True
    telegram_service.close_forum_topic.assert_called_with(123, 999)
    db.tickets.update_one.assert_called()

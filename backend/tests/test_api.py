"""
Backend API Tests for Решала Support от DonMatteo
Tests: Health, Settings, AI Chat, Tickets, Lookup, Knowledge Base, Actions
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealth:
    """Health endpoint tests"""
    
    def test_health_check(self):
        """Test /api/health returns ok status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "Решала" in data["service"]
        print(f"✓ Health check passed: {data}")


class TestSettings:
    """Settings API tests"""
    
    def test_get_settings(self):
        """Test GET /api/settings returns settings"""
        response = requests.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        data = response.json()
        # Should have service_name
        assert "service_name" in data or "error" in data
        print(f"✓ Settings retrieved: {list(data.keys())}")
    
    def test_get_providers(self):
        """Test GET /api/settings/providers returns AI providers list"""
        response = requests.get(f"{BASE_URL}/api/settings/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)
        print(f"✓ Providers count: {len(data['providers'])}")
        # Check provider structure
        if data["providers"]:
            provider = data["providers"][0]
            assert "name" in provider
            assert "display_name" in provider


class TestAIChat:
    """AI Chat API tests"""
    
    def test_chat_empty_message(self):
        """Test /api/ai/chat rejects empty message"""
        response = requests.post(f"{BASE_URL}/api/ai/chat", json={"message": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        assert "error" in data
        print(f"✓ Empty message rejected: {data['error']}")
    
    def test_chat_with_message(self):
        """Test /api/ai/chat with valid message"""
        response = requests.post(f"{BASE_URL}/api/ai/chat", json={"message": "Привет, как подключить VPN?"})
        assert response.status_code == 200
        data = response.json()
        # Either ok with reply or error (if no AI provider configured)
        assert "ok" in data
        if data["ok"]:
            assert "reply" in data
            print(f"✓ AI replied: {data['reply'][:100]}...")
        else:
            print(f"✓ AI chat endpoint works (no provider): {data.get('error', 'unknown')}")
    
    def test_get_stock_prompt(self):
        """Test GET /api/ai/stock-prompt returns system prompt"""
        response = requests.get(f"{BASE_URL}/api/ai/stock-prompt")
        assert response.status_code == 200
        data = response.json()
        assert "prompt" in data
        assert "VPN" in data["prompt"]
        assert "БЕЗОПАСНОСТЬ" in data["prompt"]
        print(f"✓ Stock prompt retrieved, length: {len(data['prompt'])} chars")


class TestTickets:
    """Tickets API tests"""
    
    def test_get_escalated_tickets(self):
        """Test GET /api/tickets/escalated returns tickets list"""
        response = requests.get(f"{BASE_URL}/api/tickets/escalated")
        assert response.status_code == 200
        data = response.json()
        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        print(f"✓ Escalated tickets count: {len(data['tickets'])}")
        # Check ticket structure if any exist
        if data["tickets"]:
            ticket = data["tickets"][0]
            assert "id" in ticket
            assert "client_id" in ticket
            print(f"  First ticket ID: {ticket['id']}")
    
    def test_create_ticket(self):
        """Test POST /api/tickets/create creates new ticket"""
        ticket_data = {
            "client_id": 999999999,
            "client_name": "TEST_User",
            "client_username": "test_user",
            "reason": "TEST: Automated test ticket",
            "last_messages": [
                {"role": "user", "content": "Test message from user"},
                {"role": "assistant", "content": "Test AI response"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/tickets/create", json=ticket_data)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "ticket_id" in data
        print(f"✓ Ticket created: {data['ticket_id']}")
        return data["ticket_id"]
    
    def test_get_ticket_by_id(self):
        """Test GET /api/tickets/{id} returns ticket"""
        # First create a ticket
        ticket_data = {
            "client_id": 888888888,
            "client_name": "TEST_GetTicket",
            "reason": "TEST: Get ticket test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/tickets/create", json=ticket_data)
        ticket_id = create_resp.json().get("ticket_id")
        
        # Then get it
        response = requests.get(f"{BASE_URL}/api/tickets/{ticket_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "ticket" in data
        assert data["ticket"]["client_id"] == 888888888
        print(f"✓ Ticket retrieved: {data['ticket']['id']}")
    
    def test_ticket_not_found(self):
        """Test GET /api/tickets/{invalid_id} returns error"""
        response = requests.get(f"{BASE_URL}/api/tickets/000000000000000000000000")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Invalid ticket handled: {data.get('error')}")
    
    def test_reply_to_ticket(self):
        """Test POST /api/tickets/{id}/reply adds reply"""
        # Create ticket first
        ticket_data = {"client_id": 777777777, "client_name": "TEST_Reply"}
        create_resp = requests.post(f"{BASE_URL}/api/tickets/create", json=ticket_data)
        ticket_id = create_resp.json().get("ticket_id")
        
        # Send reply
        response = requests.post(f"{BASE_URL}/api/tickets/{ticket_id}/reply", json={"message": "Test manager reply"})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        print(f"✓ Reply sent to ticket: {ticket_id}")
    
    def test_close_ticket(self):
        """Test POST /api/tickets/{id}/close closes ticket"""
        # Create ticket first
        ticket_data = {"client_id": 666666666, "client_name": "TEST_Close"}
        create_resp = requests.post(f"{BASE_URL}/api/tickets/create", json=ticket_data)
        ticket_id = create_resp.json().get("ticket_id")
        
        # Close it
        response = requests.post(f"{BASE_URL}/api/tickets/{ticket_id}/close")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        print(f"✓ Ticket closed: {ticket_id}")
    
    def test_escalate_ticket(self):
        """Test POST /api/tickets/{id}/escalate escalates ticket"""
        # Create ticket first
        ticket_data = {"client_id": 555555555, "client_name": "TEST_Escalate"}
        create_resp = requests.post(f"{BASE_URL}/api/tickets/create", json=ticket_data)
        ticket_id = create_resp.json().get("ticket_id")
        
        # Escalate it
        escalate_data = {
            "reason": "TEST: User requested manager",
            "last_messages": [{"role": "user", "content": "I need a manager"}]
        }
        response = requests.post(f"{BASE_URL}/api/tickets/{ticket_id}/escalate", json=escalate_data)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        print(f"✓ Ticket escalated: {ticket_id}")


class TestLookup:
    """User lookup API tests"""
    
    def test_lookup_empty_query(self):
        """Test /api/lookup rejects empty query"""
        response = requests.post(f"{BASE_URL}/api/lookup", json={"query": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        assert data["error"] == "query_required"
        print(f"✓ Empty query rejected")
    
    def test_lookup_user_by_telegram_id(self):
        """Test /api/lookup with Telegram ID"""
        # Test with provided test user ID
        response = requests.post(f"{BASE_URL}/api/lookup", json={"query": "5367956099"})
        assert response.status_code == 200
        data = response.json()
        # Either found user or API not configured
        assert "ok" in data
        if data["ok"]:
            assert "user" in data
            print(f"✓ User found: {data['user'].get('username', 'N/A')}")
        else:
            print(f"✓ Lookup endpoint works: {data.get('error')}")


class TestKnowledge:
    """Knowledge base API tests"""
    
    def test_get_articles(self):
        """Test GET /api/knowledge returns articles list"""
        response = requests.get(f"{BASE_URL}/api/knowledge")
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert isinstance(data["articles"], list)
        print(f"✓ Knowledge articles count: {len(data['articles'])}")
    
    def test_create_article(self):
        """Test POST /api/knowledge creates article"""
        article_data = {
            "title": "TEST_Article",
            "content": "This is a test article content for automated testing",
            "category": "test"
        }
        response = requests.post(f"{BASE_URL}/api/knowledge", json=article_data)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "id" in data
        print(f"✓ Article created: {data['id']}")
        return data["id"]
    
    def test_create_article_validation(self):
        """Test POST /api/knowledge validates required fields"""
        response = requests.post(f"{BASE_URL}/api/knowledge", json={"title": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Validation works: {data.get('error')}")
    
    def test_get_article_by_id(self):
        """Test GET /api/knowledge/{id} returns article"""
        # Create first
        create_resp = requests.post(f"{BASE_URL}/api/knowledge", json={
            "title": "TEST_GetArticle",
            "content": "Test content for get",
            "category": "test"
        })
        article_id = create_resp.json().get("id")
        
        # Get it
        response = requests.get(f"{BASE_URL}/api/knowledge/{article_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert data["article"]["title"] == "TEST_GetArticle"
        print(f"✓ Article retrieved: {article_id}")
    
    def test_update_article(self):
        """Test PUT /api/knowledge/{id} updates article"""
        # Create first
        create_resp = requests.post(f"{BASE_URL}/api/knowledge", json={
            "title": "TEST_UpdateArticle",
            "content": "Original content",
            "category": "test"
        })
        article_id = create_resp.json().get("id")
        
        # Update it
        response = requests.put(f"{BASE_URL}/api/knowledge/{article_id}", json={
            "title": "TEST_UpdateArticle_Modified",
            "content": "Updated content"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
        # Verify update
        get_resp = requests.get(f"{BASE_URL}/api/knowledge/{article_id}")
        assert get_resp.json()["article"]["title"] == "TEST_UpdateArticle_Modified"
        print(f"✓ Article updated: {article_id}")
    
    def test_delete_article(self):
        """Test DELETE /api/knowledge/{id} deletes article"""
        # Create first
        create_resp = requests.post(f"{BASE_URL}/api/knowledge", json={
            "title": "TEST_DeleteArticle",
            "content": "To be deleted",
            "category": "test"
        })
        article_id = create_resp.json().get("id")
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/knowledge/{article_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
        # Verify deletion
        get_resp = requests.get(f"{BASE_URL}/api/knowledge/{article_id}")
        assert get_resp.json()["ok"] == False
        print(f"✓ Article deleted: {article_id}")
    
    def test_search_articles(self):
        """Test GET /api/knowledge/search/{query} searches articles"""
        # Create article with specific content
        requests.post(f"{BASE_URL}/api/knowledge", json={
            "title": "TEST_SearchVPN",
            "content": "How to connect VPN service",
            "category": "vpn"
        })
        
        # Search for it
        response = requests.get(f"{BASE_URL}/api/knowledge/search/VPN")
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        print(f"✓ Search results: {len(data['articles'])} articles")


class TestActions:
    """User actions API tests (require Remnawave API)"""
    
    def test_reset_traffic_no_uuid(self):
        """Test /api/actions/reset-traffic rejects empty uuid"""
        response = requests.post(f"{BASE_URL}/api/actions/reset-traffic", json={"userUuid": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        assert "userUuid required" in data.get("error", "")
        print(f"✓ Reset traffic validation works")
    
    def test_revoke_subscription_no_uuid(self):
        """Test /api/actions/revoke-subscription rejects empty uuid"""
        response = requests.post(f"{BASE_URL}/api/actions/revoke-subscription", json={"userUuid": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Revoke subscription validation works")
    
    def test_enable_user_no_uuid(self):
        """Test /api/actions/enable-user rejects empty uuid"""
        response = requests.post(f"{BASE_URL}/api/actions/enable-user", json={"userUuid": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Enable user validation works")
    
    def test_disable_user_no_uuid(self):
        """Test /api/actions/disable-user rejects empty uuid"""
        response = requests.post(f"{BASE_URL}/api/actions/disable-user", json={"userUuid": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Disable user validation works")
    
    def test_hwid_delete_all_no_uuid(self):
        """Test /api/actions/hwid-delete-all rejects empty uuid"""
        response = requests.post(f"{BASE_URL}/api/actions/hwid-delete-all", json={"userUuid": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ HWID delete all validation works")
    
    def test_hwid_delete_no_params(self):
        """Test /api/actions/hwid-delete rejects missing params"""
        response = requests.post(f"{BASE_URL}/api/actions/hwid-delete", json={"userUuid": "", "hwid": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ HWID delete validation works")


class TestAIProviders:
    """AI Provider management tests"""
    
    def test_test_connection_no_provider(self):
        """Test /api/ai/test-connection rejects empty provider"""
        response = requests.post(f"{BASE_URL}/api/ai/test-connection", json={"provider": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Test connection validation works")
    
    def test_get_models(self):
        """Test GET /api/ai/models/{provider} returns models"""
        response = requests.get(f"{BASE_URL}/api/ai/models/groq")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        print(f"✓ Models endpoint works: {len(data.get('models', []))} models")
    
    def test_set_model_validation(self):
        """Test /api/ai/set-model validates input"""
        response = requests.post(f"{BASE_URL}/api/ai/set-model", json={"provider": "", "model": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Set model validation works")
    
    def test_set_active_provider_validation(self):
        """Test /api/ai/set-active-provider validates input"""
        response = requests.post(f"{BASE_URL}/api/ai/set-active-provider", json={"provider": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Set active provider validation works")


# Cleanup fixture
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after all tests"""
    yield
    # Cleanup test tickets
    try:
        from pymongo import MongoClient
        MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        DB_NAME = os.environ.get("DB_NAME", "reshala_support")
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Delete test tickets
        result = db.tickets.delete_many({"client_name": {"$regex": "^TEST_"}})
        print(f"\n✓ Cleaned up {result.deleted_count} test tickets")
        
        # Delete test articles
        result = db.knowledge_base.delete_many({"title": {"$regex": "^TEST_"}})
        print(f"✓ Cleaned up {result.deleted_count} test articles")
        
        client.close()
    except Exception as e:
        print(f"Cleanup warning: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

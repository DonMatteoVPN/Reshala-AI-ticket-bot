#!/usr/bin/env python3
"""
Backend API Testing for Telegram Bot + Mini App VPN Support
Testing Bedolaga API integration and Tickets functionality
"""
import requests
import sys
import json
from datetime import datetime

class VPNSupportAPITester:
    def __init__(self, base_url="https://brain-trainer-46.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_bedolaga_balance(self, telegram_id=123456789):
        """Test GET /api/bedolaga/balance/{telegram_id}"""
        print(f"\n🔍 Testing Bedolaga Balance API...")
        
        try:
            url = f"{self.base_url}/api/bedolaga/balance/{telegram_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Should return ok:false with error "Bedolaga API не настроен"
                if not data.get("ok") and "Bedolaga API не настроен" in data.get("error", ""):
                    self.log_test("Bedolaga Balance API", True, "Correctly returns 'Bedolaga API не настроен'")
                    return True
                elif data.get("ok"):
                    self.log_test("Bedolaga Balance API", True, f"API configured and working: {data}")
                    return True
                else:
                    self.log_test("Bedolaga Balance API", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("Bedolaga Balance API", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Bedolaga Balance API", False, f"Exception: {str(e)}")
            return False

    def test_bedolaga_deposits(self, telegram_id=123456789):
        """Test GET /api/bedolaga/deposits/{telegram_id}"""
        print(f"\n🔍 Testing Bedolaga Deposits API...")
        
        try:
            url = f"{self.base_url}/api/bedolaga/deposits/{telegram_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Should return ok:false with error "Bedolaga API не настроен" and deposits:[]
                if (not data.get("ok") and 
                    "Bedolaga API не настроен" in data.get("error", "") and
                    data.get("deposits") == []):
                    self.log_test("Bedolaga Deposits API", True, "Correctly returns 'Bedolaga API не настроен' with empty deposits")
                    return True
                elif data.get("ok") and isinstance(data.get("deposits"), list):
                    self.log_test("Bedolaga Deposits API", True, f"API configured and working: {len(data['deposits'])} deposits")
                    return True
                else:
                    self.log_test("Bedolaga Deposits API", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("Bedolaga Deposits API", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Bedolaga Deposits API", False, f"Exception: {str(e)}")
            return False

    def test_tickets_reply(self):
        """Test POST /api/tickets/{ticket_id}/reply"""
        print(f"\n🔍 Testing Tickets Reply API...")
        
        # Use a fake ticket ID for testing
        fake_ticket_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format
        
        try:
            url = f"{self.base_url}/api/tickets/{fake_ticket_id}/reply"
            payload = {
                "message": "Test reply from manager",
                "manager_name": "Test Manager"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Should return ok:false with error "ticket_not_found" for fake ID
                if not data.get("ok") and data.get("error") == "ticket_not_found":
                    self.log_test("Tickets Reply API", True, "Correctly handles non-existent ticket")
                    return True
                elif data.get("ok"):
                    self.log_test("Tickets Reply API", True, f"Reply sent successfully: {data}")
                    return True
                else:
                    self.log_test("Tickets Reply API", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("Tickets Reply API", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Tickets Reply API", False, f"Exception: {str(e)}")
            return False

    def test_tickets_reply_validation(self):
        """Test POST /api/tickets/{ticket_id}/reply with invalid data"""
        print(f"\n🔍 Testing Tickets Reply API Validation...")
        
        fake_ticket_id = "507f1f77bcf86cd799439011"
        
        try:
            url = f"{self.base_url}/api/tickets/{fake_ticket_id}/reply"
            
            # Test empty message
            payload = {"message": "", "manager_name": "Test Manager"}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if not data.get("ok") and data.get("error") == "message_required":
                    self.log_test("Tickets Reply Validation", True, "Correctly validates empty message")
                    return True
                else:
                    self.log_test("Tickets Reply Validation", False, f"Should reject empty message: {data}")
                    return False
            else:
                self.log_test("Tickets Reply Validation", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Tickets Reply Validation", False, f"Exception: {str(e)}")
            return False

    def test_tickets_active(self):
        """Test GET /api/tickets/active"""
        print(f"\n🔍 Testing Active Tickets API...")
        
        try:
            url = f"{self.base_url}/api/tickets/active"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "tickets" in data and isinstance(data["tickets"], list):
                    self.log_test("Active Tickets API", True, f"Returns {len(data['tickets'])} tickets")
                    return True
                else:
                    self.log_test("Active Tickets API", False, f"Invalid response format: {data}")
                    return False
            else:
                self.log_test("Active Tickets API", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Active Tickets API", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting VPN Support Backend API Tests")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test Bedolaga APIs
        self.test_bedolaga_balance()
        self.test_bedolaga_deposits()
        
        # Test Tickets APIs
        self.test_tickets_reply()
        self.test_tickets_reply_validation()
        self.test_tickets_active()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = VPNSupportAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
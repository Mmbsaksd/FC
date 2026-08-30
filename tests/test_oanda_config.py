import unittest
from fastapi.testclient import TestClient
from app.api.server import app
from app.config.settings import settings

class TestOANDAConfigEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_save_oanda_credentials(self):
        """Test saving OANDA API Key, Account ID, and Environment."""
        payload = {
            "api_key": "test_oanda_api_key_12345",
            "account_id": "101-001-9999999-001",
            "environment": "practice"
        }
        res = self.client.post("/api/config/oanda/save", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        
        # Verify runtime settings updated
        self.assertEqual(settings.OANDA_API_KEY, "test_oanda_api_key_12345")
        self.assertEqual(settings.OANDA_ACCOUNT_ID, "101-001-9999999-001")
        self.assertEqual(settings.OANDA_ENVIRONMENT, "practice")

    def test_oanda_connection_empty_key(self):
        """Test OANDA test endpoint with empty API Key."""
        settings.OANDA_API_KEY = ""
        payload = {
            "api_key": "",
            "account_id": "",
            "environment": "practice"
        }
        res = self.client.post("/api/config/oanda/test", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "FAILED")
        self.assertIn("OANDA API Key is required", data["message"])

    def test_oanda_connection_invalid_key(self):
        """Test OANDA test endpoint with mock invalid key (verifies REST call attempt)."""
        payload = {
            "api_key": "invalid_mock_key_abc",
            "account_id": "101-001-0000000-001",
            "environment": "practice"
        }
        res = self.client.post("/api/config/oanda/test", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "FAILED")
        self.assertIn("HTTP", data["message"])

if __name__ == "__main__":
    unittest.main()

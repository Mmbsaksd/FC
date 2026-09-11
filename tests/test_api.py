import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api.server import app

class TestFastAPIServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher = patch("app.api.server.SIGNALS_STORAGE_PATH", "non_existent_file.json")
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        self.client = TestClient(app)

    def test_overview_endpoint(self):
        res = self.client.get("/api/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("currency_strength", data)

    def test_signals_endpoint(self):
        res = self.client.get("/api/signals")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("signals", data)
        self.assertGreater(len(data["signals"]), 0)

    def test_paper_trading_endpoint(self):
        res = self.client.get("/api/paper-trading")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current_balance", data)

    def test_funnel_endpoint(self):
        res = self.client.get("/api/funnel")
        self.assertEqual(res.status_code, 200)

    def test_config_endpoint(self):
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("telegram", data)
        self.assertIn("llm_providers", data)
        self.assertIn("oanda", data)
        # Ensure raw unmasked keys are never exposed in cleartext if present
        for p, cfg in data.get("llm_providers", {}).items():
            k = cfg.get("key", "")
            if k:
                self.assertIn("••••", k)

if __name__ == '__main__':
    unittest.main()

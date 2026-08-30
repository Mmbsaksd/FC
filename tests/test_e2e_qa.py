import unittest
from unittest.mock import patch
import json
import os
import sys
from fastapi.testclient import TestClient

# Add project root directory
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.api.server import app
from app.engines.technical_engine import TechnicalAnalysisEngine
from app.engines.currency_strength import CurrencyStrengthEngine
from app.engines.signal_engine import SignalGenerationEngine
from app.risk.risk_engine import RiskEngine
from app.engines.paper_trading import PaperTradingEngine

class EndToEndQATestSuite(unittest.TestCase):
    """
    Comprehensive E2E QA Test Suite testing Client, User, and Engineering perspectives.
    """

    @classmethod
    def setUpClass(cls):
        cls.patcher = patch("app.api.server.SIGNALS_STORAGE_PATH", "non_existent_file.json")
        cls.patcher.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    # ==========================================
    # 1. CLIENT / TRADER PERSPECTIVE TESTS
    # ==========================================
    def test_client_signal_reasoning_quality(self):
        """Verify signals contain structured 'WHY THIS TRADE?' rationale."""
        res = self.client.get("/api/signals")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("signals", data)
        self.assertGreater(len(data["signals"]), 0)

        for sig in data["signals"]:
            self.assertIn("signal_id", sig)
            self.assertIn("direction", sig)
            self.assertIn("risk_reward", sig)
            self.assertGreaterEqual(sig["risk_reward"], 2.0)
            self.assertIn("reasoning_object", sig)
            reasoning = sig["reasoning_object"]
            self.assertIn("summary", reasoning)
            self.assertIn("supporting_factors", reasoning)

    def test_client_risk_reward_thresholds(self):
        """Verify Risk Engine enforces minimum 1:2.0 R:R."""
        params = RiskEngine.calculate_trade_parameters(
            symbol="EURUSD=X", direction="LONG", current_price=1.0850, atr=0.0020
        )
        self.assertTrue(params["valid"])
        self.assertGreaterEqual(params["risk_reward"], 2.0)

    # ==========================================
    # 2. USER / FRONTEND PERSPECTIVE TESTS
    # ==========================================
    def test_user_dashboard_html_rendering(self):
        """Verify root URL serves the single-page HTML dashboard."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("AI Market Intelligence", res.text)
        self.assertIn("Currency Strength Matrix", res.text)

    def test_user_overview_data_feed(self):
        """Verify overview endpoint returns currency matrix & asset monitor."""
        res = self.client.get("/api/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertIn("currency_strength", data)
        self.assertIn("tracked_assets", data)

    def test_user_telegram_test_connection_endpoint(self):
        """Verify Telegram test connection endpoint handles payloads safely."""
        res = self.client.post("/api/config/telegram/test", json={"bot_token": "", "chat_id": ""})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "FAILED")

    # ==========================================
    # 3. QA & ENGINEERING PERSPECTIVE TESTS
    # ==========================================
    def test_qa_paper_trading_engine(self):
        """Verify paper trading balance and trade logging."""
        res = self.client.get("/api/paper-trading")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current_balance", data)
        self.assertGreaterEqual(data["current_balance"], 10000.0)

    def test_qa_funnel_metrics_endpoint(self):
        """Verify filter funnel metrics endpoint returns conversion breakdown."""
        res = self.client.get("/api/funnel")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("latest_snapshot", data)

    def test_qa_manual_scan_trigger(self):
        """Verify manual scan trigger endpoint executes without crashing."""
        res = self.client.post("/api/scan/trigger")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")

if __name__ == "__main__":
    unittest.main()

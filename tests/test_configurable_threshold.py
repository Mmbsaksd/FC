import unittest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.config.settings import settings, update_env_file
from app.risk.final_gate import DeterministicFinalRiskGate
from app.llm.decision_engine import LLMDecisionEngine
from app.parallel.aggregator import CompleteMarketContext
from app.api.server import app

class TestConfigurableThreshold(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.original_threshold = settings.MIN_OPPORTUNITY_SCORE

    def tearDown(self):
        # Restore original threshold
        settings.MIN_OPPORTUNITY_SCORE = self.original_threshold
        update_env_file({"MIN_OPPORTUNITY_SCORE": str(self.original_threshold)})

    def test_api_threshold_save_and_reload(self):
        """Verify saving threshold via API updates settings and persists."""
        for test_val in [50.0, 60.0, 75.0, 80.0, 90.0]:
            res = self.client.post("/api/config/thresholds/save", json={"min_score": test_val})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "SUCCESS")
            self.assertEqual(data["min_score"], test_val)
            self.assertEqual(settings.MIN_OPPORTUNITY_SCORE, test_val)

            # Check GET /api/config
            cfg_res = self.client.get("/api/config")
            self.assertEqual(cfg_res.status_code, 200)
            self.assertEqual(cfg_res.json()["thresholds"]["min_score"], test_val)

    def test_risk_gate_evaluation_at_different_thresholds(self):
        """Verify Risk Gate PASS/REJECT dynamically switches based on configured threshold."""
        gate = DeterministicFinalRiskGate(min_rr=2.0)

        candidate = {
            "symbol_name": "EUR/USD",
            "opportunity_score": 67.0,
            "decision": "TRADE"
        }
        context_meta = {"data_quality": "VALID", "spread_pips": 1.2}
        risk_metrics = {"risk_reward": 2.5}

        # Case 1: Threshold = 60.0 -> Score 67.0 >= 60.0 => PASS
        settings.MIN_OPPORTUNITY_SCORE = 60.0
        passed, reason = gate.validate_candidate(candidate, context_meta, risk_metrics)
        self.assertTrue(passed, f"Expected PASS at threshold 60.0, got: {reason}")

        # Case 2: Threshold = 70.0 -> Score 67.0 < 70.0 => REJECT
        settings.MIN_OPPORTUNITY_SCORE = 70.0
        passed, reason = gate.validate_candidate(candidate, context_meta, risk_metrics)
        self.assertFalse(passed)
        self.assertIn("Below Required Threshold (70.0)", reason)

        # Case 3: Threshold = 80.0 -> Score 67.0 < 80.0 => REJECT
        settings.MIN_OPPORTUNITY_SCORE = 80.0
        passed, reason = gate.validate_candidate(candidate, context_meta, risk_metrics)
        self.assertFalse(passed)
        self.assertIn("Below Required Threshold (80.0)", reason)

    def test_safety_gates_remain_active_with_low_threshold(self):
        """Verify lowering threshold to 50.0 does NOT bypass data quality or R:R gates."""
        settings.MIN_OPPORTUNITY_SCORE = 50.0
        gate = DeterministicFinalRiskGate(min_rr=2.0)

        candidate = {
            "symbol_name": "GBP/USD",
            "opportunity_score": 55.0, # Passes 50.0 threshold
            "decision": "TRADE"
        }

        # 1. Stale Data must still be REJECTED
        stale_meta = {"data_quality": "STALE", "spread_pips": 1.0}
        passed, reason = gate.validate_candidate(candidate, stale_meta, {"risk_reward": 2.5})
        self.assertFalse(passed)
        self.assertIn("Data Quality", reason)

        # 2. Bad R:R (1.4 < 2.0) must still be REJECTED
        valid_meta = {"data_quality": "VALID", "spread_pips": 1.0}
        passed, reason = gate.validate_candidate(candidate, valid_meta, {"risk_reward": 1.4})
        self.assertFalse(passed)
        self.assertIn("Risk/Reward", reason)

if __name__ == "__main__":
    unittest.main()

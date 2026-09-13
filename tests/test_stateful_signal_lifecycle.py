import os
import sys
import unittest
from datetime import datetime, timezone

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.storage.sqlite_manager import db_manager
from app.engines.signal_lifecycle_manager import signal_lifecycle_manager, SignalLifecycleManager
from app.risk.final_gate import DeterministicFinalRiskGate

class TestStatefulSignalLifecycle(unittest.TestCase):
    def setUp(self):
        self.db = db_manager
        self.lifecycle = signal_lifecycle_manager
        self.gate = DeterministicFinalRiskGate()

    def test_01_first_detection_creates_new_signal(self):
        """Test Case 1: First detection creates NEW state."""
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 74.0,
            "ml_probability": 0.55,
            "entry_price": 1.2000,
            "stop_loss": 1.2050,
            "take_profit_1": 1.1900,
            "risk_reward": 2.0
        }
        cand["setup_key"] = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        
        # Ensure any old test signal is cleaned up
        with self.db._get_connection() as conn:
            conn.cursor().execute("DELETE FROM signals WHERE setup_key = ?", (cand["setup_key"],))
            conn.commit()

        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "NEW")
        self.assertIsNone(active)

        # Save new signal
        cand["signal_id"] = "SIG-TEST-001"
        is_created, _ = self.db.save_signal(cand)
        self.assertTrue(is_created)

    def test_02_same_signal_next_scan_is_unchanged(self):
        """Test Case 2: Same signal on next scan is UNCHANGED (Alert Suppressed)."""
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 74.2, # Minor 0.2 pt change
            "ml_probability": 0.552,   # Minor 0.2% change
            "entry_price": 1.2001,     # 0.1 pip fluctuation
            "stop_loss": 1.2050,
            "take_profit_1": 1.1900,
            "risk_reward": 2.0
        }
        cand["setup_key"] = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        
        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "UNCHANGED")
        self.assertIsNotNone(active)
        self.assertEqual(active["signal_id"], "SIG-TEST-001")

    def test_03_small_score_or_entry_change_suppressed(self):
        """Test Case 3: Small price tick or score fluctuation remains UNCHANGED."""
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 75.5, # +1.5 pts (below 5.0 threshold)
            "ml_probability": 0.57,    # +2% (below 8% threshold)
            "entry_price": 1.1998,     # 0.2 pips
            "stop_loss": 1.2050,
            "take_profit_1": 1.1900,
            "risk_reward": 2.0
        }
        cand["setup_key"] = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "UNCHANGED")

    def test_04_material_improvement_transitions_to_strengthened(self):
        """Test Case 4: Significant score (+6.0) or ML (+10%) improvement triggers STRENGTHENED."""
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 80.5, # +6.5 pts!
            "ml_probability": 0.65,    # +10% ML!
            "entry_price": 1.1995,
            "stop_loss": 1.2050,
            "take_profit_1": 1.1890,
            "risk_reward": 2.2
        }
        cand["setup_key"] = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "STRENGTHENED")
        self.assertGreaterEqual(deltas["delta_score"], 5.0)

        # Verify revision saving in SQLite
        new_v = self.db.save_signal_revision("SIG-TEST-001", {
            "scan_id": "scan-test-2",
            "state": "STRENGTHENED",
            "opportunity_score": 80.5,
            "ml_probability": 0.65,
            "entry_price": 1.1995,
            "stop_loss": 1.2050,
            "take_profit_1": 1.1890,
            "change_reason": ", ".join(deltas.get("reasons", [])),
            "deltas": deltas
        })
        self.assertEqual(new_v, 2)
        
        revisions = self.db.get_signal_revisions("SIG-TEST-001")
        self.assertEqual(len(revisions), 2)
        self.assertEqual(revisions[1]["version_number"], 2)
        self.assertEqual(revisions[1]["state"], "STRENGTHENED")

    def test_05_material_deterioration_transitions_to_weakened(self):
        """Test Case 5: Significant drop in score (-7.0) triggers WEAKENED."""
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 73.0, # Dropped from 80.5 (-7.5 pts!)
            "ml_probability": 0.52,    # Dropped -13%
            "entry_price": 1.1995,
            "stop_loss": 1.2050,
            "take_profit_1": 1.1890,
            "risk_reward": 2.0
        }
        cand["setup_key"] = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "WEAKENED")

    def test_06_invalidation_when_price_crosses_stop_loss(self):
        """Test Case 6: Price crossing SL triggers INVALIDATED."""
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 60.0,
            "ml_probability": 0.35,
            "entry_price": 1.2055, # Crossed above 1.2050 SL for SHORT!
            "stop_loss": 1.2050,
            "take_profit_1": 1.1890,
            "risk_reward": 2.0
        }
        cand["setup_key"] = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "INVALIDATED")

    def test_07_quality_tier_and_ml_probability_floor(self):
        """Test Case 7: Trade with high score but low ML prob (<40%) is rejected and never labeled HIGH_QUALITY."""
        cand = {
            "symbol_name": "TEST/USD",
            "opportunity_score": 74.5,
            "ml_probability": 0.178, # Low ML probability (17.8%)!
            "decision": "TRADE"
        }
        passed, reason = self.gate.validate_candidate(
            candidate_decision=cand,
            context_meta={"data_quality": "VALID", "spread_pips": 1.0},
            risk_metrics={"risk_reward": 2.0},
            mode="CHAMPION"
        )
        self.assertFalse(passed)
        self.assertIn("Weak ML Probability", reason)

    def test_08_new_signal_permitted_after_old_is_closed(self):
        """Test Case 8: Once previous signal is CLOSED, a new setup creates a new signal."""
        setup_key = self.db.compute_setup_key("TEST/USD", "SHORT", "5M")
        
        # Close previous test signal
        self.db.update_signal_progress("SIG-TEST-001", {
            "status": "CLOSED",
            "outcome": "TARGET_2_HIT",
            "realized_r": 2.0,
            "realized_pnl": 100.0
        })
        
        cand = {
            "symbol_name": "TEST/USD",
            "direction": "SHORT",
            "timeframe": "5M",
            "opportunity_score": 76.0,
            "ml_probability": 0.58,
            "entry_price": 1.1850,
            "stop_loss": 1.1900,
            "take_profit_1": 1.1750,
            "risk_reward": 2.0
        }
        cand["setup_key"] = setup_key
        state, active, deltas = self.lifecycle.evaluate_signal_transition(cand)
        self.assertEqual(state, "NEW")
        self.assertIsNone(active)

        # Clean up test records
        with self.db._get_connection() as conn:
            conn.cursor().execute("DELETE FROM signals WHERE symbol = 'TEST/USD'")
            conn.cursor().execute("DELETE FROM signal_revisions WHERE signal_id IN ('SIG-TEST-001', 'SIG-TEST-002')")
            conn.commit()

if __name__ == "__main__":
    unittest.main()

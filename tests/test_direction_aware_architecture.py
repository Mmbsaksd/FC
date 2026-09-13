import os
import unittest
import pandas as pd
import numpy as np

from app.parallel.base_engine import MarketSnapshot, AnalysisResult
from app.parallel.aggregator import EvidenceAggregator, DirectionAwareEvidenceAggregator, CompleteMarketContext
from app.risk.candidate_qualifier import CandidateQualificationEngine
from app.risk.final_gate import DeterministicFinalRiskGate
from app.llm.decision_engine import LLMDecisionEngine
from app.observability.decision_auditor import DecisionAuditor

class TestDirectionAwareArchitecture(unittest.TestCase):
    def setUp(self):
        self.aggregator = DirectionAwareEvidenceAggregator()
        self.champion_aggregator = EvidenceAggregator()
        self.qualifier = CandidateQualificationEngine(min_consensus=0.15, min_rr=2.0, min_ev_r=0.0)
        self.final_gate = DeterministicFinalRiskGate(min_rr=2.0, max_spread_pips=10.0)
        self.llm_engine = LLMDecisionEngine()

        # Dummy 30 candles dataframe
        dates = pd.date_range("2026-09-01", periods=30, freq="15min")
        self.dummy_candles = pd.DataFrame({
            "time": dates,
            "open": np.linspace(1.25, 1.26, 30),
            "high": np.linspace(1.252, 1.262, 30),
            "low": np.linspace(1.248, 1.258, 30),
            "close": np.linspace(1.251, 1.261, 30),
            "volume": [1000] * 30
        })

        self.fx_snapshot = MarketSnapshot(
            timestamp="2026-09-11T12:00:00Z",
            symbol="GBPUSD=X",
            symbol_name="GBP/USD",
            asset_class="FOREX",
            price=1.2610,
            bid=1.2609,
            ask=1.2611,
            spread_pips=1.2,
            timeframe="15M",
            candles=self.dummy_candles,
            session="LONDON",
            pip_size=0.0001,
            base_currency="GBP",
            quote_currency="USD"
        )

        self.gold_snapshot = MarketSnapshot(
            timestamp="2026-09-11T12:00:00Z",
            symbol="GC=F",
            symbol_name="Gold",
            asset_class="COMMODITY",
            price=2500.0,
            bid=2499.8,
            ask=2500.2,
            spread_pips=4.0,
            timeframe="15M",
            candles=self.dummy_candles,
            session="LONDON",
            pip_size=0.10,
            base_currency="XAU",
            quote_currency="USD"
        )

        self.btc_snapshot = MarketSnapshot(
            timestamp="2026-09-11T12:00:00Z",
            symbol="BTC-USD",
            symbol_name="Bitcoin (BTC)",
            asset_class="CRYPTO",
            price=65000.0,
            bid=64995.0,
            ask=65005.0,
            spread_pips=10.0,
            timeframe="15M",
            candles=self.dummy_candles,
            session="24/7",
            pip_size=1.00,
            base_currency="BTC",
            quote_currency="USD",
            is_crypto=True
        )

    # 1. Opposing evidence is not incorrectly added as positive evidence
    def test_01_opposing_evidence_not_added_as_positive(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(
                engine_name="TechnicalAnalysis", status="SUCCESS", score=90.0,
                direction="LONG", confidence=0.90, evidence=["Bullish momentum"]
            ),
            "MarketStructure": AnalysisResult(
                engine_name="MarketStructure", status="SUCCESS", score=90.0,
                direction="SHORT", confidence=0.90, evidence=["Bearish swing break"]
            )
        }
        # In Candidate direction-aware aggregator:
        candidate_ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        
        # Long evidence and short evidence should be recorded in their own pools
        self.assertGreater(candidate_ctx.long_evidence, 0.0)
        self.assertGreater(candidate_ctx.short_evidence, 0.0)
        # Net consensus should be near 0 because they are equal and opposite
        self.assertAlmostEqual(candidate_ctx.directional_consensus, 0.0, delta=0.05)
        # Opposing short evidence did NOT inflate long evidence!
        self.assertEqual(candidate_ctx.dominant_direction, "NEUTRAL")

    # 2. Directional evidence is calculated separately
    def test_02_directional_evidence_calculated_separately(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(
                engine_name="TechnicalAnalysis", status="SUCCESS", score=80.0,
                direction="LONG", confidence=0.80, evidence=["Bullish setup"]
            ),
            "RiskMetrics": AnalysisResult(
                engine_name="RiskMetrics", status="SUCCESS", score=95.0,
                direction="LONG", confidence=0.85, evidence=["Favorable RR"]
            ),
            "MarketStructure": AnalysisResult(
                engine_name="MarketStructure", status="SUCCESS", score=70.0,
                direction="SHORT", confidence=0.70, evidence=["Bearish pullback"]
            ),
            "MarketRegime": AnalysisResult(
                engine_name="MarketRegime", status="SUCCESS", score=75.0,
                direction="NEUTRAL", confidence=0.80, evidence=["Normal volatility"]
            )
        }
        ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        self.assertGreater(ctx.long_evidence, ctx.short_evidence)
        self.assertGreater(ctx.neutral_evidence, 0.0)
        self.assertGreater(ctx.directional_consensus, 0.0)
        self.assertEqual(ctx.dominant_direction, "LONG")

    # 3. Asset-specific weights are respected
    def test_03_asset_specific_weights_respected(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=80.0, direction="LONG", confidence=0.80),
            "CurrencyStrength": AnalysisResult(engine_name="CurrencyStrength", status="SUCCESS", score=90.0, direction="LONG", confidence=0.90),
            "MacroAnalysis": AnalysisResult(engine_name="MacroAnalysis", status="SUCCESS", score=80.0, direction="LONG", confidence=0.80)
        }
        fx_ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        gold_ctx = self.aggregator.aggregate_evidence(self.gold_snapshot, results)
        
        # In Forex, CurrencyStrength has 0.15 weight; in Commodities (Gold), it has 0.00 weight
        self.assertIn("CurrencyStrength", fx_ctx.weighted_contributions)
        self.assertEqual(fx_ctx.weighted_contributions["CurrencyStrength"]["weight"], 0.15)
        # For Gold, CurrencyStrength must be 0.00 weight (or not in active contributions)
        if "CurrencyStrength" in gold_ctx.weighted_contributions:
            self.assertEqual(gold_ctx.weighted_contributions["CurrencyStrength"]["weight"], 0.00)

    # 4. CurrencyStrength does not distort Gold/Crypto
    def test_04_currency_strength_does_not_distort_gold_or_crypto(self):
        results = {
            "CurrencyStrength": AnalysisResult(engine_name="CurrencyStrength", status="SUCCESS", score=99.0, direction="LONG", confidence=0.99)
        }
        btc_ctx = self.aggregator.aggregate_evidence(self.btc_snapshot, results)
        gold_ctx = self.aggregator.aggregate_evidence(self.gold_snapshot, results)

        # Currency strength has 0 weight on Crypto and Gold, so long evidence must NOT come from CurrencyStrength
        self.assertEqual(btc_ctx.long_evidence, 0.0)
        self.assertEqual(gold_ctx.long_evidence, 0.0)
        self.assertNotIn("CurrencyStrength", btc_ctx.weighted_contributions)
        self.assertNotIn("CurrencyStrength", gold_ctx.weighted_contributions)

    # 5. Score is not treated as probability
    def test_05_score_is_not_treated_as_probability(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=95.0, direction="LONG", confidence=0.95),
            "MLPrediction": AnalysisResult(engine_name="MLPrediction", status="SUCCESS", score=42.0, direction="LONG", confidence=0.42)
        }
        ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        # Even though Technical score is 95/100, ctx.overall_confidence must NOT be 0.95
        self.assertLess(ctx.overall_confidence, 0.90)

    # 6. Heuristic confidence is identified correctly
    def test_06_heuristic_confidence_identified_correctly(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=80.0, direction="LONG", confidence=0.80)
        }
        ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        self.assertEqual(ctx.confidence_type, "heuristic")
        self.assertEqual(ctx.weighted_contributions["TechnicalAnalysis"]["confidence_type"], "heuristic")

    # 7. Positive EV candidate can reach the LLM even when heuristic score is below the old threshold
    def test_07_positive_ev_candidate_qualifies_below_old_threshold(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=85.0, direction="LONG", confidence=0.85),
            "MarketStructure": AnalysisResult(engine_name="MarketStructure", status="SUCCESS", score=80.0, direction="LONG", confidence=0.80),
            "MLPrediction": AnalysisResult(engine_name="MLPrediction", status="SUCCESS", score=45.0, direction="LONG", confidence=0.45),
            "RiskMetrics": AnalysisResult(engine_name="RiskMetrics", status="SUCCESS", score=90.0, direction="LONG", confidence=0.85)
        }
        ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        trade_params = {"risk_reward": 3.0, "risk_pips": 20.0, "pip_size": 0.0001}
        ml_prob = 0.45  # 45% win rate on 1:3 RR -> EV = 0.45 * 3 - 0.55 * 1 = +0.80R!
        
        qualified, reason, metrics = self.qualifier.evaluate_qualification(ctx, trade_params, ml_probability=ml_prob)
        self.assertTrue(qualified)
        self.assertGreater(metrics["expected_value_r"], 0.50)
        self.assertTrue(ctx.candidate_qualified)

    # 8. Negative EV candidate cannot become a trade merely because aggregate score is high
    def test_08_negative_ev_candidate_cannot_become_trade(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=98.0, direction="LONG", confidence=0.98),
            "MarketStructure": AnalysisResult(engine_name="MarketStructure", status="SUCCESS", score=95.0, direction="LONG", confidence=0.95),
            "RiskMetrics": AnalysisResult(engine_name="RiskMetrics", status="SUCCESS", score=95.0, direction="LONG", confidence=0.85)
        }
        ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        trade_params = {"risk_reward": 2.0, "risk_pips": 15.0, "pip_size": 0.0001, "entry_price": 1.2610, "stop_loss": 1.2595, "take_profit_1": 1.2640}
        # Low win prob 20% on 1:2.0 RR -> EV = 0.20 * 2.0 - 0.80 - spread_cost = -0.46R
        qualified, reason, metrics = self.qualifier.evaluate_qualification(ctx, trade_params, ml_probability=0.20)
        self.assertFalse(qualified)
        self.assertIn("Negative or zero mathematical Expected Value", reason)

        # And if passed to FinalRiskGate with negative EV, risk gate MUST REJECT IT:
        decision_payload = {
            "symbol_name": "GBP/USD", "direction": "LONG", "decision": "TRADE",
            "expected_value_r": -0.50, "opportunity_score": 95.0
        }
        passed, gate_reason = self.final_gate.validate_candidate(decision_payload, ctx.snapshot_meta, trade_params, mode="CANDIDATE")
        self.assertFalse(passed)
        self.assertIn("Negative Expected Value", gate_reason)

    # 9. LLM cannot override hard risk controls
    def test_09_llm_cannot_override_hard_risk_controls(self):
        # Case A: Excessive spread (35 pips > 10 pips max)
        bad_spread_meta = dict(self.fx_snapshot.__dict__)
        bad_spread_meta["spread_pips"] = 35.0
        trade_params = {"entry_price": 1.2610, "stop_loss": 1.2580, "take_profit_1": 1.2700, "risk_reward": 3.0}
        candidate_decision = {"symbol_name": "GBP/USD", "direction": "LONG", "decision": "TRADE", "expected_value_r": 0.50}

        passed, reason = self.final_gate.validate_candidate(candidate_decision, bad_spread_meta, trade_params, mode="CANDIDATE")
        self.assertFalse(passed)
        self.assertIn("Excessive Spread", reason)

        # Case B: Inverted price geometry (SL above Entry for Long)
        inverted_trade_params = {"entry_price": 1.2610, "stop_loss": 1.2700, "take_profit_1": 1.2500, "risk_reward": 3.0}
        passed, reason = self.final_gate.validate_candidate(candidate_decision, self.fx_snapshot.__dict__, inverted_trade_params, mode="CANDIDATE")
        self.assertFalse(passed)
        self.assertIn("Inverted Long Geometry", reason)

    # 10. All evidence sent to LLM is traceable to the candidate
    def test_10_evidence_traceable_to_candidate(self):
        results = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=88.0, direction="LONG", confidence=0.88, evidence=["RSI healthy bullish"])
        }
        ctx = self.aggregator.aggregate_evidence(self.fx_snapshot, results)
        ctx.candidate_qualified = True
        ctx.expected_value_r = 0.45

        eval_res = self.llm_engine.evaluate_market_context(ctx, snapshot=self.fx_snapshot, mode="CANDIDATE")
        raw_ctx = eval_res.get("raw_context", {})
        self.assertEqual(raw_ctx["market"]["symbol_name"], "GBP/USD")
        self.assertEqual(raw_ctx["trade"]["direction"], "LONG")
        self.assertIn("TechnicalAnalysis", raw_ctx["engine_breakdown"])

    # 11. Candidate IDs cannot cross-contaminate
    def test_11_candidate_ids_cannot_cross_contaminate(self):
        auditor = DecisionAuditor()
        event1 = auditor.record_decision_audit(
            candidate_id="cand-EURUSD-001", scan_id="scan-1", instrument="EUR/USD", asset_class="FOREX",
            timestamp="2026-09-11T12:00:00Z", direction="LONG", engine_outputs={}, weighted_contributions={},
            long_evidence=50.0, short_evidence=0.0, neutral_evidence=0.0, directional_consensus=1.0,
            composite_opportunity_score=70.0, ml_probability=0.55, expected_value_r=0.4, risk_reward=2.5,
            entry_price=1.10, stop_loss=1.09, take_profit=1.125, candidate_qualified=True, qualification_reason="OK",
            llm_decision="TRADE", llm_reason="Approved", llm_supporting_factors=[], llm_contradicting_factors=[],
            final_risk_passed=True, final_decision="TRADE"
        )
        event2 = auditor.record_decision_audit(
            candidate_id="cand-USDJPY-002", scan_id="scan-1", instrument="USD/JPY", asset_class="FOREX",
            timestamp="2026-09-11T12:00:00Z", direction="SHORT", engine_outputs={}, weighted_contributions={},
            long_evidence=0.0, short_evidence=60.0, neutral_evidence=0.0, directional_consensus=-1.0,
            composite_opportunity_score=65.0, ml_probability=0.52, expected_value_r=0.3, risk_reward=2.5,
            entry_price=145.0, stop_loss=146.0, take_profit=142.5, candidate_qualified=True, qualification_reason="OK",
            llm_decision="TRADE", llm_reason="Approved", llm_supporting_factors=[], llm_contradicting_factors=[],
            final_risk_passed=True, final_decision="TRADE"
        )
        self.assertNotEqual(event1["candidate_id"], event2["candidate_id"])
        self.assertEqual(event1["instrument"], "EUR/USD")
        self.assertEqual(event2["instrument"], "USD/JPY")

    # 12. Logs contain the complete decision explanation
    def test_12_logs_contain_complete_decision_explanation(self):
        auditor = DecisionAuditor()
        event = auditor.record_decision_audit(
            candidate_id="cand-USDJPY-003", scan_id="scan-2", instrument="USD/JPY", asset_class="FOREX",
            timestamp="2026-09-11T12:00:00Z", direction="LONG", engine_outputs={}, weighted_contributions={},
            long_evidence=65.0, short_evidence=10.0, neutral_evidence=5.0, directional_consensus=0.68,
            composite_opportunity_score=68.5, ml_probability=0.55, expected_value_r=0.56, risk_reward=3.0,
            entry_price=154.50, stop_loss=154.10, take_profit=155.70, candidate_qualified=True, qualification_reason="Strong consensus and positive EV",
            llm_decision="TRADE", llm_reason="Clear bullish structure aligned with technicals",
            llm_supporting_factors=["Strong momentum", "BOS confirmed"], llm_contradicting_factors=["Slight USD strength"],
            final_risk_passed=True, final_decision="TRADE", signal_id="SIG-USDJPY-003"
        )
        self.assertIn("directional_consensus_metrics", event)
        self.assertIn("mathematical_edge", event)
        self.assertIn("stage1_qualification", event)
        self.assertIn("stage2_llm_adjudication", event)
        self.assertIn("stage3_final_risk_gate", event)
        self.assertEqual(event["final_outcome"]["is_executable_signal"], True)

    # 13. Stop-loss root-cause fields are preserved separately from outcome
    def test_13_stop_loss_root_cause_fields_preserved(self):
        from app.storage.sqlite_manager import db_manager
        # Record a test decision snapshot
        snap_id = db_manager.save_market_snapshot({
            "snapshot_id": "test-snap-001",
            "scan_id": "test-scan-001",
            "symbol": "EUR/USD",
            "timestamp": "2026-09-11T12:00:00Z",
            "price": 1.1000,
            "bid": 1.0999,
            "ask": 1.1001,
            "spread_pips": 1.0,
            "session": "LONDON",
            "data_quality": "VALID"
        })
        self.assertTrue(snap_id)

        # 1. Create a test signal with decision-time features
        import uuid
        test_uid = uuid.uuid4().hex[:8]
        sig_payload = {
            "signal_id": f"SIG-TEST-SL-{test_uid}",
            "fingerprint": f"fp-test-{test_uid}",
            "setup_key": f"SETUP-TEST-{test_uid}",
            "symbol_name": "EUR/USD",
            "symbol": "EUR/USD",
            "direction": "LONG",
            "entry_price": 1.1000,
            "stop_loss": 1.0960,
            "take_profit_1": 1.1080,
            "risk_reward": 2.0,
            "opportunity_score": 75.0,
            "ml_probability": 0.62,
            "features": {"adx": 28.5, "rsi": 54.0, "regime": "TRENDING_BULLISH"},
            "supporting_evidence": ["Bullish momentum", "FVG retest"],
            "why_this_trade": {"catalyst": "H4 breakout"}
        }
        is_created, sig_id = db_manager.save_signal(sig_payload)
        self.assertTrue(is_created)

        # 2. Record ML training record at decision time (zero leakage)
        db_manager.save_ml_training_record(sig_payload)

        # 3. Simulate Stop Loss outcome event with root cause analysis
        db_manager.update_ml_training_outcome(
            signal_id=sig_id,
            outcome_class="LOSS",
            realized_r=-1.0,
            realized_pnl=-150.0,
            mfe_r=0.45,
            mae_r=-1.02,
            holding_mins=45,
            exit_reason="STOP_LOSS_HIT",
            root_cause="VOLATILITY_EXPANSION_SPIKE",
            root_cause_evidence="High-impact Red Folder news release caused 40 pip spread spike"
        )

        # 4. Verify outcome record has root cause preserved separately from decision-time features
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ml_training_records WHERE signal_id = ?", (sig_id,))
            ml_row = cursor.fetchone()
            self.assertIsNotNone(ml_row)
            self.assertEqual(ml_row["outcome_class"], "LOSS")
            self.assertEqual(ml_row["root_cause"], "VOLATILITY_EXPANSION_SPIKE")
            self.assertIn("Red Folder", ml_row["root_cause_evidence"])
            self.assertIn("TRENDING_BULLISH", ml_row["signal_time_features_json"])
            # Ensure outcome fields are NOT leaked into decision-time features
            self.assertNotIn("VOLATILITY_EXPANSION_SPIKE", ml_row["signal_time_features_json"])

    # 14. Processing one asset cannot alter another asset's state
    def test_14_cross_asset_state_isolation(self):
        results_fx = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=90.0, direction="LONG", confidence=0.90)
        }
        results_gold = {
            "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=85.0, direction="SHORT", confidence=0.85)
        }
        ctx_fx = self.aggregator.aggregate_evidence(self.fx_snapshot, results_fx)
        ctx_gold = self.aggregator.aggregate_evidence(self.gold_snapshot, results_gold)

        self.assertEqual(ctx_fx.symbol_name, "GBP/USD")
        self.assertEqual(ctx_fx.dominant_direction, "LONG")
        self.assertEqual(ctx_gold.symbol_name, "Gold")
        self.assertEqual(ctx_gold.dominant_direction, "SHORT")
        self.assertNotEqual(ctx_fx.directional_consensus, ctx_gold.directional_consensus)

if __name__ == "__main__":
    unittest.main()

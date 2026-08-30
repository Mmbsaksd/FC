import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from app.risk.risk_engine import RiskEngine
from app.ml.classifier import OpportunityMLClassifier
from app.parallel.base_engine import MarketSnapshot, AnalysisResult
from app.parallel.aggregator import EvidenceAggregator
from app.parallel.engines.candle_engine import ParallelCandleEngine
from app.engines.technical_engine import TechnicalAnalysisEngine
from app.engines.currency_strength import CurrencyStrengthEngine

class TestAnalyticsImprovements(unittest.TestCase):
    """
    Unit test suite verifying all analytics pipeline improvements and refactorings.
    """

    def test_risk_direction_reconciliation_long(self):
        """Verify LONG parameters satisfy Stop Loss < Entry Price < Take Profit."""
        params = RiskEngine.calculate_trade_parameters(
            symbol="EURUSD=X",
            direction="LONG",
            current_price=1.0850,
            atr=0.0020,
            pip_size=0.0001
        )
        self.assertTrue(params["valid"])
        self.assertEqual(params["entry_price"], 1.0850)
        self.assertLess(params["stop_loss"], params["entry_price"])
        self.assertGreater(params["take_profit_1"], params["entry_price"])
        self.assertGreater(params["take_profit_2"], params["take_profit_1"])
        self.assertGreaterEqual(params["risk_reward"], 2.0)

    def test_risk_direction_reconciliation_short(self):
        """Verify SHORT parameters satisfy Take Profit < Entry Price < Stop Loss."""
        params = RiskEngine.calculate_trade_parameters(
            symbol="EURUSD=X",
            direction="SHORT",
            current_price=1.0850,
            atr=0.0020,
            pip_size=0.0001
        )
        self.assertTrue(params["valid"])
        self.assertEqual(params["entry_price"], 1.0850)
        self.assertGreater(params["stop_loss"], params["entry_price"])
        self.assertLess(params["take_profit_1"], params["entry_price"])
        self.assertLess(params["take_profit_2"], params["take_profit_1"])
        self.assertGreaterEqual(params["risk_reward"], 2.0)

    def test_expected_value_calculation(self):
        """Verify dynamic EV calculation in R-multiples."""
        ev = RiskEngine.calculate_expected_value(win_prob=0.65, risk_reward=2.5, estimated_spread_pips=1.2)
        # EV = (0.65 * 2.5) - (0.35 * 1.0) - (1.2 * 0.05) = 1.625 - 0.35 - 0.06 = 1.215
        self.assertAlmostEqual(ev, 1.215, places=2)
        self.assertGreater(ev, 0.0)

    def test_calibrated_ml_classifier_range(self):
        """Verify calibrated statistical classifier outputs valid probabilities."""
        classifier = OpportunityMLClassifier()
        
        # High quality bullish setup
        bull_features = {
            "rsi": 58.0,
            "adx": 32.0,
            "tech_score": 85.0,
            "strength_diff": 3.2,
            "direction": "LONG"
        }
        prob_bull = classifier.predict_probability(bull_features)
        self.assertGreaterEqual(prob_bull, 0.60)
        self.assertLessEqual(prob_bull, 0.85)

        # Choppy / neutral setup
        neutral_features = {
            "rsi": 50.0,
            "adx": 15.0,
            "tech_score": 50.0,
            "strength_diff": 0.0,
            "direction": "NEUTRAL"
        }
        prob_neut = classifier.predict_probability(neutral_features)
        self.assertEqual(prob_neut, 0.40)

    def test_weighted_evidence_aggregator(self):
        """Verify evidence aggregator applies weights and preserves directional confluence."""
        aggregator = EvidenceAggregator()
        
        # Create sample dummy snapshot
        snapshot = MarketSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol="EURUSD=X",
            symbol_name="EUR/USD",
            asset_class="FOREX",
            price=1.0850,
            bid=1.0849,
            ask=1.0851,
            spread_pips=2.0,
            timeframe="15M",
            candles=pd.DataFrame(),
            session="LONDON",
            pip_size=0.0001,
            base_currency="EUR",
            quote_currency="USD"
        )

        engine_results = {
            "TechnicalAnalysis": AnalysisResult(
                engine_name="TechnicalAnalysis",
                status="SUCCESS",
                score=88.0,
                direction="LONG",
                confidence=0.85,
                evidence=["Strong technical breakout"],
                metrics={"setup_type": "DONCHIAN_BREAKOUT_LONG"}
            ),
            "MarketStructure": AnalysisResult(
                engine_name="MarketStructure",
                status="SUCCESS",
                score=85.0,
                direction="LONG",
                confidence=0.85,
                evidence=["Confirmed BOS Long"]
            ),
            "CurrencyStrength": AnalysisResult(
                engine_name="CurrencyStrength",
                status="SUCCESS",
                score=80.0,
                direction="LONG",
                confidence=0.80,
                evidence=["EUR strength divergence"]
            ),
            "MLPrediction": AnalysisResult(
                engine_name="MLPrediction",
                status="SUCCESS",
                score=72.0,
                direction="LONG",
                confidence=0.72,
                evidence=["Statistical win probability 72%"],
                metrics={"win_probability": 0.72}
            ),
            "MarketRegime": AnalysisResult(
                engine_name="MarketRegime",
                status="SUCCESS",
                score=75.0,
                direction="NEUTRAL",
                confidence=0.80,
                metrics={"regime": "TRENDING_MOMENTUM"}
            )
        }

        context = aggregator.aggregate_evidence(snapshot, engine_results)
        self.assertEqual(context.dominant_direction, "LONG")
        self.assertGreaterEqual(context.composite_opportunity_score, 70.0)
        self.assertGreater(context.overall_confidence, 0.60)

    def test_technical_engine_non_overlapping_indicators(self):
        """Verify TechnicalAnalysisEngine calculates MACD, ROC, and valid non-overlapping signals."""
        prices = np.linspace(1.0800, 1.0900, 30)
        df = pd.DataFrame({
            'open': prices - 0.0002,
            'high': prices + 0.0004,
            'low': prices - 0.0003,
            'close': prices,
            'volume': [1000] * 30
        })
        eval_res = TechnicalAnalysisEngine.evaluate_technical_score(df)
        self.assertIn("score", eval_res)
        self.assertIn("direction", eval_res)
        self.assertIn("macd", eval_res)
        self.assertIn("roc_10", eval_res)
        self.assertIn("setup_type", eval_res)

if __name__ == "__main__":
    unittest.main()

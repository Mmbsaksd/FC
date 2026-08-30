import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from app.parallel.base_engine import MarketSnapshot
from app.parallel.registry import AnalysisEngineRegistry
from app.parallel.engines.technical_engine import ParallelTechnicalEngine
from app.parallel.engines.candle_engine import ParallelCandleEngine
from app.parallel.engines.market_structure_engine import ParallelMarketStructureEngine
from app.parallel.engines.currency_strength_engine import ParallelCurrencyStrengthEngine
from app.parallel.engines.ml_engine import ParallelMLEngine
from app.parallel.engines.regime_engine import ParallelRegimeEngine
from app.parallel.engines.fundamental_engine import ParallelFundamentalEngine
from app.parallel.engines.macro_engine import ParallelMacroEngine
from app.parallel.engines.risk_engine import ParallelRiskEngine
from app.parallel.engines.sentiment_engine import ParallelSentimentEngine
from app.parallel.parallel_orchestrator import ParallelOrchestrator
from app.parallel.aggregator import EvidenceAggregator
from app.llm.decision_engine import LLMDecisionEngine
from app.risk.final_gate import DeterministicFinalRiskGate

class TestParallelArchitecture(unittest.TestCase):
    def setUp(self):
        # Create dummy OHLCV candle dataset for test snapshot
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=50, freq='15min')
        prices = np.linspace(1.0800, 1.0880, 50) + np.random.normal(0, 0.0005, 50)
        df = pd.DataFrame({
            'open': prices - 0.0002,
            'high': prices + 0.0005,
            'low': prices - 0.0005,
            'close': prices,
            'volume': np.random.randint(100, 1000, 50)
        }, index=dates)

        self.snapshot = MarketSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol="EURUSD=X",
            symbol_name="EUR/USD",
            asset_class="FOREX",
            price=float(df['close'].iloc[-1]),
            bid=float(df['close'].iloc[-1]) - 0.0001,
            ask=float(df['close'].iloc[-1]) + 0.0001,
            spread_pips=1.0,
            timeframe="15M",
            candles=df,
            session="LONDON",
            pip_size=0.0001,
            base_currency="EUR",
            quote_currency="USD"
        )

        self.registry = AnalysisEngineRegistry()
        self.registry.register(ParallelTechnicalEngine())
        self.registry.register(ParallelCandleEngine())
        self.registry.register(ParallelMarketStructureEngine())
        self.registry.register(ParallelCurrencyStrengthEngine())
        self.registry.register(ParallelMLEngine())
        self.registry.register(ParallelRegimeEngine())
        self.registry.register(ParallelFundamentalEngine())
        self.registry.register(ParallelMacroEngine())
        self.registry.register(ParallelRiskEngine())
        self.registry.register(ParallelSentimentEngine())

    def test_parallel_execution_and_orchestrator(self):
        """Test concurrent execution of all 10 parallel analysis engines."""
        orchestrator = ParallelOrchestrator(registry=self.registry, max_workers=4)
        results = orchestrator.execute_parallel_analysis(self.snapshot)

        self.assertGreaterEqual(len(results), 8)
        self.assertIn("TechnicalAnalysis", results)
        self.assertIn("CandleStructure", results)
        self.assertIn("MarketStructure", results)

        for name, res in results.items():
            self.assertIn(res.status, ["SUCCESS", "UNAVAILABLE"])
            self.assertGreaterEqual(res.score, 0.0)
            self.assertLessEqual(res.score, 100.0)

    def test_evidence_aggregator(self):
        """Test evidence normalization and aggregation."""
        orchestrator = ParallelOrchestrator(registry=self.registry, max_workers=4)
        results = orchestrator.execute_parallel_analysis(self.snapshot)
        aggregator = EvidenceAggregator()
        context = aggregator.aggregate_evidence(self.snapshot, results)

        self.assertIsNotNone(context.scan_id)
        self.assertIsNotNone(context.trace_id)
        self.assertIn(context.dominant_direction, ["LONG", "SHORT", "NEUTRAL"])
        self.assertIsInstance(context.supporting_evidence, list)

    def test_llm_decision_and_final_gate(self):
        """Test LLM Decision Engine and Deterministic Final Risk Gate."""
        orchestrator = ParallelOrchestrator(registry=self.registry, max_workers=4)
        results = orchestrator.execute_parallel_analysis(self.snapshot)
        aggregator = EvidenceAggregator()
        context = aggregator.aggregate_evidence(self.snapshot, results)

        llm_engine = LLMDecisionEngine()
        decision = llm_engine.evaluate_market_context(context)

        self.assertIn(decision["decision"], ["TRADE", "WATCH", "NO_TRADE"])
        self.assertIn("why_this_trade", decision)

        risk_gate = DeterministicFinalRiskGate(min_rr=2.0)
        risk_metrics = results.get("RiskMetrics", {}).metrics if "RiskMetrics" in results else {}
        approved, reason = risk_gate.validate_candidate(decision, context.snapshot_meta, risk_metrics)
        self.assertIsInstance(approved, bool)

if __name__ == "__main__":
    unittest.main()

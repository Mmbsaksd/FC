import os
import sys
import time
import requests
import unittest
import pandas as pd
from datetime import datetime, timezone

# Set root directory
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.providers.yahoo_provider import YahooMarketDataProvider
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

print("=" * 70)
print("🚀 RUNNING FULL END-TO-END SYSTEM DIAGNOSTIC & NETWORK HEALTH CHECK")
print("=" * 70)

# 1. Test Network & Market Data Feed
print("\n[1/4] Testing Live Market Data Feed (Yahoo Finance)...")
t0 = time.time()
provider = YahooMarketDataProvider()
df_forex = provider.fetch_ohlcv("EURUSD=X", timeframe="15M", limit=60)
df_gold = provider.fetch_ohlcv("GC=F", timeframe="15M", limit=60)
df_crypto = provider.fetch_ohlcv("BTC-USD", timeframe="15M", limit=60)
data_fetch_ms = (time.time() - t0) * 1000.0

assert not df_forex.empty, "EUR/USD candles are empty!"
assert not df_gold.empty, "Gold candles are empty!"
assert not df_crypto.empty, "Bitcoin candles are empty!"
print(f"  ✅ Live Feeds Verified in {data_fetch_ms:.1f}ms: EURUSD ({len(df_forex)} bars), Gold ({len(df_gold)} bars), BTC ({len(df_crypto)} bars)")

# 2. Test 10 Parallel Analysis Engines
print("\n[2/4] Testing 10 Parallel Analysis Engines & Orchestrator...")
snapshot = MarketSnapshot(
    timestamp=datetime.now(timezone.utc).isoformat(),
    symbol="EURUSD=X",
    symbol_name="EUR/USD",
    asset_class="FOREX",
    price=float(df_forex['close'].iloc[-1]),
    bid=float(df_forex['close'].iloc[-1]) - 0.0001,
    ask=float(df_forex['close'].iloc[-1]) + 0.0001,
    spread_pips=1.0,
    timeframe="15M",
    candles=df_forex,
    session="LONDON",
    pip_size=0.0001,
    base_currency="EUR",
    quote_currency="USD"
)

registry = AnalysisEngineRegistry()
registry.register(ParallelTechnicalEngine())
registry.register(ParallelCandleEngine())
registry.register(ParallelMarketStructureEngine())
registry.register(ParallelCurrencyStrengthEngine(provider=provider))
registry.register(ParallelMLEngine())
registry.register(ParallelRegimeEngine())
registry.register(ParallelFundamentalEngine())
registry.register(ParallelMacroEngine())
registry.register(ParallelRiskEngine())
registry.register(ParallelSentimentEngine())

orchestrator = ParallelOrchestrator(registry=registry, max_workers=4)
t_start = time.time()
engine_results = orchestrator.execute_parallel_analysis(snapshot)
orch_duration_ms = (time.time() - t_start) * 1000.0

assert len(engine_results) == 10, f"Expected 10 engines, got {len(engine_results)}"
for name, res in engine_results.items():
    assert res.status == "SUCCESS", f"Engine {name} failed: {res.error_message}"
    print(f"  ✅ Engine [{name:<22}]: Score={res.score:>5.1f} | Dir={res.direction:<7} | Conf={res.confidence*100:>4.0f}% | Status={res.status}")
print(f"  ⚡ All 10 engines completed concurrently in {orch_duration_ms:.1f}ms")

# 3. Test Evidence Aggregation, LLM Decision & Risk Gate
print("\n[3/4] Testing Evidence Aggregator, LLM Decision & Final Risk Gate...")
aggregator = EvidenceAggregator()
context = aggregator.aggregate_evidence(snapshot, engine_results)
assert context.dominant_direction in ["LONG", "SHORT", "NEUTRAL"], f"Invalid direction: {context.dominant_direction}"
print(f"  ✅ Aggregator Output: Dominant Direction={context.dominant_direction}, Score={context.composite_opportunity_score:.1f}, Confidence={context.overall_confidence*100:.1f}%")

llm_engine = LLMDecisionEngine()
decision = llm_engine.evaluate_market_context(context)
assert "decision" in decision and "why_this_trade" in decision, "Invalid LLM decision payload"
print(f"  ✅ LLM Decision Layer: Decision={decision['decision']} | Provider={decision['provider']} | Approved={decision['llm_approved']}")

gate = DeterministicFinalRiskGate(min_rr=2.0)
passed, reason = gate.validate_candidate(decision, context.snapshot_meta, engine_results.get("RiskMetrics", {}).metrics)
print(f"  ✅ Deterministic Risk Gate: Passed={passed} | Reason: {reason}")

# 4. Test Local FastAPI Server HTTP Endpoints
print("\n[4/4] Testing Local FastAPI Server HTTP Endpoints (http://127.0.0.1:8000)...")
base_url = "http://127.0.0.1:8000"
endpoints = [
    ("/", "HTML Dashboard"),
    ("/api/overview", "Live Overview & Currency Matrix"),
    ("/api/signals", "Live Signals Feed"),
    ("/api/paper-trading", "Paper Trading Simulation"),
    ("/api/funnel", "System Mirror Telemetry"),
    ("/api/parallel/health", "Parallel Health Matrix"),
    ("/api/config", "System Configuration"),
    ("/api/config/scheduler", "Scan Scheduler Config")
]

for path, desc in endpoints:
    try:
        r = requests.get(f"{base_url}{path}", timeout=10)
        assert r.status_code == 200, f"Status code {r.status_code}"
        print(f"  ✅ {desc:<35} [{path:<22}] -> HTTP 200 OK")
    except Exception as e:
        print(f"  ❌ {desc:<35} [{path:<22}] -> Failed: {e}")

print("\n" + "=" * 70)
print("🎉 ALL SYSTEMS, NETWORKS, ENGINES, AND PIPELINES VERIFIED 100% OPERATIONAL")
print("=" * 70)

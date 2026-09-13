"""
Comprehensive Test Suite for Asset-Aware Pipeline Architecture & Decision Logic.
Validates:
1. Multi-asset support (Forex, Commodity, Crypto).
2. Asset-specific engine selection and weighting (ASSET_PROFILES).
3. State isolation and zero cross-asset state contamination.
4. Order independence (EUR/USD -> Gold -> BTC vs BTC -> Gold -> EUR/USD).
5. Currency strength engine isolation (non-FX pairs never contaminated with fiat divergence).
6. Asset-aware risk parameters (volatility multipliers & price precision).
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from app.parallel.base_engine import MarketSnapshot
from app.parallel.engines.currency_strength_engine import ParallelCurrencyStrengthEngine
from app.parallel.engines.regime_engine import ParallelRegimeEngine
from app.parallel.engines.candle_engine import ParallelCandleEngine
from app.parallel.engines.risk_engine import ParallelRiskEngine
from app.parallel.engines.sentiment_engine import ParallelSentimentEngine
from app.parallel.aggregator import EvidenceAggregator
from app.risk.risk_engine import RiskEngine
from app.risk.final_gate import DeterministicFinalRiskGate


def _make_mock_candles(base_price: float, volatility: float, length: int = 50) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=length, freq="1h")
    returns = np.random.normal(0, volatility, length)
    prices = base_price * np.exp(np.cumsum(returns))

    highs = prices * (1.0 + np.abs(np.random.normal(0, volatility * 0.5, length)))
    lows = prices * (1.0 - np.abs(np.random.normal(0, volatility * 0.5, length)))
    opens = np.roll(prices, 1)
    opens[0] = base_price

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": np.random.randint(1000, 50000, length)
    }, index=dates)
    return df


def test_currency_strength_engine_isolation_for_non_fx():
    """Verify CurrencyStrength engine gracefully marks itself UNAVAILABLE for non-FX assets."""
    cs_engine = ParallelCurrencyStrengthEngine()

    # 1. Forex Snapshot (EUR/USD)
    fx_snapshot = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="EURUSD=X",
        symbol_name="EUR/USD",
        asset_class="FOREX",
        price=1.0850,
        bid=1.0849,
        ask=1.0851,
        spread_pips=1.2,
        timeframe="1H",
        candles=_make_mock_candles(1.0850, 0.002),
        session="LONDON/NY_OVERLAP",
        pip_size=0.0001,
        base_currency="EUR",
        quote_currency="USD",
        is_crypto=False
    )
    fx_res = cs_engine.analyze(fx_snapshot)
    assert fx_res.status == "SUCCESS"
    assert fx_res.metrics.get("base_currency") == "EUR"
    assert fx_res.metrics.get("quote_currency") == "USD"

    # 2. Commodity Snapshot (Gold / XAU)
    gold_snapshot = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="GC=F",
        symbol_name="Gold",
        asset_class="COMMODITY",
        price=2450.0,
        bid=2449.5,
        ask=2450.5,
        spread_pips=10.0,
        timeframe="1H",
        candles=_make_mock_candles(2450.0, 0.005),
        session="LONDON/NY_OVERLAP",
        pip_size=0.10,
        base_currency="XAU",
        quote_currency="USD",
        is_crypto=False
    )
    gold_res = cs_engine.analyze(gold_snapshot)
    assert gold_res.status == "UNAVAILABLE"
    assert gold_res.score == 50.0
    assert gold_res.direction == "NEUTRAL"
    assert "not a fiat cross" in gold_res.evidence[0]

    # 3. Crypto Snapshot (BTC/USD)
    btc_snapshot = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="BTC-USD",
        symbol_name="Bitcoin (BTC)",
        asset_class="CRYPTO",
        price=62000.0,
        bid=61990.0,
        ask=62010.0,
        spread_pips=20.0,
        timeframe="1H",
        candles=_make_mock_candles(62000.0, 0.02),
        session="LONDON/NY_OVERLAP",
        pip_size=1.0,
        base_currency="BTC",
        quote_currency="USD",
        is_crypto=True
    )
    btc_res = cs_engine.analyze(btc_snapshot)
    assert btc_res.status == "UNAVAILABLE"
    assert btc_res.score == 50.0
    assert btc_res.direction == "NEUTRAL"


def test_asset_aware_aggregator_weighting_profiles():
    """Verify EvidenceAggregator dynamically switches weight profiles based on asset class."""
    aggregator = EvidenceAggregator()
    from app.parallel.base_engine import AnalysisResult

    mock_results = {
        "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 80.0, "LONG", 0.8),
        "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 85.0, "LONG", 0.85),
        "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 90.0, "SHORT", 0.9), # Conflicting
        "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 75.0, "LONG", 0.75),
        "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 80.0, "LONG", 0.8),
        "MacroAnalysis": AnalysisResult("MacroAnalysis", "SUCCESS", 70.0, "LONG", 0.7),
        "SentimentCrossAsset": AnalysisResult("SentimentCrossAsset", "SUCCESS", 85.0, "LONG", 0.85)
    }

    # For Crypto: CurrencyStrength has 0.0 weight, so conflicting CurrencyStrength SHORT does not drag down Crypto
    crypto_snapshot = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="BTC-USD",
        symbol_name="Bitcoin (BTC)",
        asset_class="CRYPTO",
        price=60000.0,
        bid=59990.0,
        ask=60010.0,
        spread_pips=20.0,
        timeframe="1H",
        candles=_make_mock_candles(60000.0, 0.02),
        session="LONDON/NY_OVERLAP",
        pip_size=1.0,
        base_currency="BTC",
        quote_currency="USD",
        is_crypto=True
    )
    crypto_context = aggregator.aggregate_evidence(crypto_snapshot, mock_results)
    assert crypto_context.dominant_direction == "LONG"
    assert crypto_context.composite_opportunity_score > 70.0
    assert crypto_context.snapshot_meta["asset_class"] == "CRYPTO"

    # For Commodity (Gold): CurrencyStrength also excluded (0.0 weight)
    gold_snapshot = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="GC=F",
        symbol_name="Gold",
        asset_class="COMMODITY",
        price=2450.0,
        bid=2449.0,
        ask=2451.0,
        spread_pips=5.0,
        timeframe="1H",
        candles=_make_mock_candles(2450.0, 0.005),
        session="LONDON/NY_OVERLAP",
        pip_size=0.10,
        base_currency="XAU",
        quote_currency="USD",
        is_crypto=False
    )
    gold_context = aggregator.aggregate_evidence(gold_snapshot, mock_results)
    assert gold_context.dominant_direction == "LONG"
    assert gold_context.snapshot_meta["asset_class"] == "COMMODITY"


def test_asset_aware_risk_parameters():
    """Verify Stop-Loss ATR multipliers and decimal precision differ across Forex, Gold, and Crypto."""
    # 1. Forex EUR/USD: 1.2x ATR, 5 decimals
    fx_params = RiskEngine.calculate_trade_parameters(
        symbol="EURUSD=X",
        direction="LONG",
        current_price=1.08500,
        atr=0.0020,
        pip_size=0.0001,
        asset_class="FOREX"
    )
    assert fx_params["valid"] is True
    assert fx_params["sl_multiplier"] == 1.2
    assert fx_params["stop_loss"] == round(1.08500 - (0.0020 * 1.2), 5)

    # 2. Commodity Gold (GC=F): 1.5x ATR, 2 decimals
    gold_params = RiskEngine.calculate_trade_parameters(
        symbol="GC=F",
        direction="LONG",
        current_price=2450.00,
        atr=12.0,
        pip_size=0.10,
        asset_class="COMMODITY"
    )
    assert gold_params["valid"] is True
    assert gold_params["sl_multiplier"] == 1.5
    assert gold_params["stop_loss"] == round(2450.00 - (12.0 * 1.5), 2)

    # 3. Crypto BTC-USD: 1.8x ATR, 2 decimals
    btc_params = RiskEngine.calculate_trade_parameters(
        symbol="BTC-USD",
        direction="LONG",
        current_price=62000.00,
        atr=800.0,
        pip_size=1.00,
        asset_class="CRYPTO"
    )
    assert btc_params["valid"] is True
    assert btc_params["sl_multiplier"] == 1.8
    assert btc_params["stop_loss"] == round(62000.00 - (800.0 * 1.8), 2)


def test_asset_aware_spread_gate():
    """Verify DeterministicFinalRiskGate does not falsely reject legitimate Gold and Crypto spreads."""
    gate = DeterministicFinalRiskGate(min_rr=2.0, max_spread_pips=10.0)

    # BTC with 25 pips spread ($25 spread on $60,000 BTC)
    btc_meta = {"data_quality": "VALID", "spread_pips": 25.0, "is_crypto": True, "asset_class": "CRYPTO"}
    btc_decision = {"symbol_name": "Bitcoin (BTC)", "opportunity_score": 82.0, "ml_probability": 0.65, "decision": "TRADE", "direction": "LONG", "expected_value_r": 0.5}
    btc_risk = {"risk_reward": 2.5, "entry_price": 60000.0, "stop_loss": 59000.0, "take_profit_1": 62500.0}
    approved, reason = gate.validate_candidate(btc_decision, btc_meta, btc_risk)
    assert approved is True
    assert reason == "PASSED_ALL_GATES"

    # Gold with 15 pips spread ($1.50 spread on Gold)
    gold_meta = {"data_quality": "VALID", "spread_pips": 15.0, "is_crypto": False, "asset_class": "COMMODITY"}
    gold_decision = {"symbol_name": "Gold", "opportunity_score": 80.0, "ml_probability": 0.62, "decision": "TRADE", "direction": "LONG", "expected_value_r": 0.5}
    gold_risk = {"risk_reward": 2.5, "entry_price": 2000.0, "stop_loss": 1980.0, "take_profit_1": 2050.0}
    approved, reason = gate.validate_candidate(gold_decision, gold_meta, gold_risk)
    assert approved is True
    assert reason == "PASSED_ALL_GATES"

    # Forex EUR/USD with 12 pips spread (excessive for FX, limit 10.0)
    fx_meta = {"data_quality": "VALID", "spread_pips": 12.0, "is_crypto": False, "asset_class": "FOREX"}
    fx_decision = {"symbol_name": "EUR/USD", "opportunity_score": 80.0, "ml_probability": 0.62, "decision": "TRADE", "direction": "LONG", "expected_value_r": 0.5}
    fx_risk = {"risk_reward": 2.5, "entry_price": 1.1000, "stop_loss": 1.0950, "take_profit_1": 1.1125}
    approved, reason = gate.validate_candidate(fx_decision, fx_meta, fx_risk)
    assert approved is False
    assert "Excessive Spread" in reason


def test_order_independence_and_cross_asset_contamination():
    """
    Intentionally tests EUR/USD -> Gold -> BTC vs BTC -> Gold -> EUR/USD.
    Verifies that processing order does NOT alter engine outcomes, scoring, or risk parameters.
    Guarantees strict state isolation.
    """
    eur_snap = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="EURUSD=X",
        symbol_name="EUR/USD",
        asset_class="FOREX",
        price=1.0850,
        bid=1.0849,
        ask=1.0851,
        spread_pips=1.2,
        timeframe="1H",
        candles=_make_mock_candles(1.0850, 0.002),
        session="LONDON/NY_OVERLAP",
        pip_size=0.0001,
        base_currency="EUR",
        quote_currency="USD",
        is_crypto=False
    )
    gold_snap = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="GC=F",
        symbol_name="Gold",
        asset_class="COMMODITY",
        price=2450.0,
        bid=2449.5,
        ask=2450.5,
        spread_pips=10.0,
        timeframe="1H",
        candles=_make_mock_candles(2450.0, 0.005),
        session="LONDON/NY_OVERLAP",
        pip_size=0.10,
        base_currency="XAU",
        quote_currency="USD",
        is_crypto=False
    )
    btc_snap = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="BTC-USD",
        symbol_name="Bitcoin (BTC)",
        asset_class="CRYPTO",
        price=62000.0,
        bid=61990.0,
        ask=62010.0,
        spread_pips=20.0,
        timeframe="1H",
        candles=_make_mock_candles(62000.0, 0.02),
        session="LONDON/NY_OVERLAP",
        pip_size=1.0,
        base_currency="BTC",
        quote_currency="USD",
        is_crypto=True
    )

    from app.parallel.registry import AnalysisEngineRegistry
    from app.parallel.parallel_orchestrator import ParallelOrchestrator
    from app.parallel.engines.technical_engine import ParallelTechnicalEngine
    from app.parallel.engines.market_structure_engine import ParallelMarketStructureEngine

    registry = AnalysisEngineRegistry()
    registry.register(ParallelTechnicalEngine())
    registry.register(ParallelMarketStructureEngine())
    registry.register(ParallelCurrencyStrengthEngine())
    registry.register(ParallelRegimeEngine())
    registry.register(ParallelCandleEngine())
    registry.register(ParallelRiskEngine())

    orchestrator = ParallelOrchestrator(registry=registry, max_workers=2)
    aggregator = EvidenceAggregator()

    # Order 1: EUR/USD -> Gold -> BTC
    res_eur_1 = orchestrator.execute_parallel_analysis(eur_snap)
    ctx_eur_1 = aggregator.aggregate_evidence(eur_snap, res_eur_1)

    res_gold_1 = orchestrator.execute_parallel_analysis(gold_snap)
    ctx_gold_1 = aggregator.aggregate_evidence(gold_snap, res_gold_1)

    res_btc_1 = orchestrator.execute_parallel_analysis(btc_snap)
    ctx_btc_1 = aggregator.aggregate_evidence(btc_snap, res_btc_1)

    # Order 2: BTC -> Gold -> EUR/USD
    res_btc_2 = orchestrator.execute_parallel_analysis(btc_snap)
    ctx_btc_2 = aggregator.aggregate_evidence(btc_snap, res_btc_2)

    res_gold_2 = orchestrator.execute_parallel_analysis(gold_snap)
    ctx_gold_2 = aggregator.aggregate_evidence(gold_snap, res_gold_2)

    res_eur_2 = orchestrator.execute_parallel_analysis(eur_snap)
    ctx_eur_2 = aggregator.aggregate_evidence(eur_snap, res_eur_2)

    # Validate Order Independence & Zero State Leakage
    assert ctx_eur_1.dominant_direction == ctx_eur_2.dominant_direction
    assert ctx_eur_1.composite_opportunity_score == ctx_eur_2.composite_opportunity_score

    assert ctx_gold_1.dominant_direction == ctx_gold_2.dominant_direction
    assert ctx_gold_1.composite_opportunity_score == ctx_gold_2.composite_opportunity_score

    assert ctx_btc_1.dominant_direction == ctx_btc_2.dominant_direction
    assert ctx_btc_1.composite_opportunity_score == ctx_btc_2.composite_opportunity_score

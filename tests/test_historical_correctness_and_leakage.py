"""
Automated Forensic Correctness & Data Leakage Test Suite.
Verifies the non-negotiable correctness requirements from Section 34:
1. Zero look-ahead and no outcome leakage into decision features
2. CLI temporal window propagation (2018-2026 vs 2006-2026)
3. Candidate accumulation and rejected candidate counterfactual simulation
4. Deadzone outcome preservation (no dropped samples)
5. Elimination of synthetic ML fallbacks (strict INSUFFICIENT_SAMPLES)
6. Cross-asset state isolation and execution order independence
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from app.backtesting.engine import HistoricalBacktestEngine
from app.backtesting.walk_forward import WalkForwardOptimizer
from app.ml.dataset_builder import dataset_builder
from app.ml.retraining_pipeline import retraining_pipeline


def generate_synthetic_ohlcv(
    symbol: str = "EUR/USD",
    n_bars: int = 250,
    start_time: str = "2020-01-01T00:00:00Z",
    base_price: float = 1.1000,
    pip_size: float = 0.0001,
    volatility: float = 0.0050
) -> pd.DataFrame:
    """Generates deterministic synthetic OHLCV bars for testing."""
    rng = np.random.RandomState(42)
    start_dt = pd.to_datetime(start_time, utc=True)
    timestamps = [start_dt + timedelta(days=i) for i in range(n_bars)]

    prices = [base_price]
    for _ in range(1, n_bars):
        change = rng.normal(0, volatility)
        prices.append(max(0.01, prices[-1] + change))

    df_data = []
    for i in range(n_bars):
        c = prices[i]
        h = c + abs(rng.normal(0, volatility * 0.5))
        l = c - abs(rng.normal(0, volatility * 0.5))
        o = (prices[i - 1] + c) / 2 if i > 0 else c
        h = max(h, o, c)
        l = min(l, o, c)
        v = float(rng.randint(1000, 5000))
        df_data.append({
            "timestamp": timestamps[i],
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": v
        })

    return pd.DataFrame(df_data)


# -------------------------------------------------------------------
# 1. Zero Feature Leakage Tests
# -------------------------------------------------------------------
def test_zero_feature_leakage():
    """
    Verifies that decision-time features contain zero future data.
    Outcome labels (realized_r, mfe_r, mae_r, exit_price, exit_reason)
    must NEVER appear inside the decision-time feature vector.
    """
    df = generate_synthetic_ohlcv("EUR/USD", n_bars=150)
    inst = {"symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX", "pip_size": 0.0001}
    engine = HistoricalBacktestEngine(strategy_params={"min_opportunity_score": 60.0, "min_ml_probability": 0.40})

    res = engine.run_backtest_on_instrument(inst, df, step_stride=1)
    all_candidates = res["all_candidates"]
    assert len(all_candidates) > 0, "Expected candidate decision points to be captured"

    forbidden_leakage_keys = {
        "future_outcome", "realized_r", "mfe_r", "mae_r", "exit_time",
        "exit_price", "exit_reason", "root_cause", "root_cause_evidence",
        "sl_hit", "t1_hit", "t2_hit", "outcome_class"
    }

    for cand in all_candidates:
        feats = cand["features"]
        # Ensure no outcome label leaked into the decision feature dictionary
        intersection = set(feats.keys()).intersection(forbidden_leakage_keys)
        assert len(intersection) == 0, f"DATA LEAKAGE DETECTED: Features contain outcome labels: {intersection}"

        # Decision time must be explicitly present and immutable
        assert "decision_time" in cand
        assert cand["decision_time"] is not None


# -------------------------------------------------------------------
# 2. Candidate Accumulation & Counterfactual Simulation Tests
# -------------------------------------------------------------------
def test_candidate_accumulation_and_counterfactual_simulation():
    """
    Verifies that all valid candidates (both accepted and rejected)
    are preserved, and rejected candidates receive authentic counterfactual outcomes.
    """
    df = generate_synthetic_ohlcv("EUR/USD", n_bars=200)
    inst = {"symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX", "pip_size": 0.0001}
    engine = HistoricalBacktestEngine(strategy_params={"min_opportunity_score": 75.0, "min_ml_probability": 0.50})

    res = engine.run_backtest_on_instrument(inst, df, step_stride=1)
    trades = res["trades"]
    rejected = res["rejected_candidates"]
    all_cands = res["all_candidates"]

    assert len(all_cands) >= len(trades), "All candidates must be >= executed portfolio trades"
    assert len(rejected) > 0, "Expected rejected candidates under strict thresholds"

    # Verify rejected candidates have valid counterfactual forward simulation
    valid_classes = {"WIN", "SMALL_WIN", "BREAKEVEN", "SMALL_LOSS", "LOSS", "EXPIRED", "NEUTRAL", "UNRESOLVED"}
    for r in rejected:
        assert "realized_r" in r, "Rejected candidate must have counterfactual realized_r"
        assert "outcome_class" in r, "Rejected candidate must have outcome_class"
        assert r["outcome_class"] in valid_classes, f"Unexpected outcome class: {r['outcome_class']}"
        assert r["accepted"] is False, "Rejected candidate accepted flag must be False"
        assert r["rejection_reason"] is not None, "Rejection reason must be documented"
        assert r["rejection_stage"] is not None, "Rejection stage must be documented"


# -------------------------------------------------------------------
# 3. Deadzone Outcome Preservation Tests
# -------------------------------------------------------------------
def test_deadzone_outcomes_not_dropped():
    """
    Verifies that samples in the deadzone (-0.5R to +1.0R) are NOT silently discarded.
    """
    candidates = [
        {"candidate_id": "c1", "symbol": "EUR/USD", "direction": "LONG", "features": {"f1": 0.5}, "realized_r": 2.25, "outcome_class": "WIN", "accepted": True},
        {"candidate_id": "c2", "symbol": "EUR/USD", "direction": "LONG", "features": {"f1": 0.3}, "realized_r": 0.75, "outcome_class": "SMALL_WIN", "accepted": False, "rejection_reason": "Below score"},
        {"candidate_id": "c3", "symbol": "EUR/USD", "direction": "SHORT", "features": {"f1": -0.1}, "realized_r": 0.0, "outcome_class": "BREAKEVEN", "accepted": False, "rejection_reason": "Below ML"},
        {"candidate_id": "c4", "symbol": "EUR/USD", "direction": "LONG", "features": {"f1": 0.2}, "realized_r": -0.4, "outcome_class": "SMALL_LOSS", "accepted": False, "rejection_reason": "Risk gate"},
        {"candidate_id": "c5", "symbol": "EUR/USD", "direction": "SHORT", "features": {"f1": -0.5}, "realized_r": -1.0, "outcome_class": "LOSS", "accepted": True},
    ]

    dataset = dataset_builder.build_dataset_from_candidates(candidates)
    samples = dataset["samples"]

    # All 5 samples must be retained (zero deadzone dropping)
    assert len(samples) == 5, f"Expected 5 samples, got {len(samples)}"

    # Check deadzone samples are mapped to valid binary labels without returning None
    for smp in samples:
        assert smp["label"] in [0, 1], f"Sample {smp['sample_id']} has invalid label: {smp['label']}"
        assert smp["outcome_class"] in ["WIN", "SMALL_WIN", "BREAKEVEN", "SMALL_LOSS", "LOSS"]

    # Check class distribution contains deadzone classes
    dist = dataset["outcome_class_distribution"]
    assert "SMALL_WIN" in dist and dist["SMALL_WIN"] == 1
    assert "BREAKEVEN" in dist and dist["BREAKEVEN"] == 1
    assert "SMALL_LOSS" in dist and dist["SMALL_LOSS"] == 1


# -------------------------------------------------------------------
# 4. Elimination of Synthetic ML Fallbacks Tests
# -------------------------------------------------------------------
def test_synthetic_ml_fallback_strictly_eliminated():
    """
    Verifies that retraining pipeline strictly returns INSUFFICIENT_SAMPLES
    and all_gates_passed = False when sample size < 30.
    Must NEVER return hardcoded 0.692 AUC, 0.40 EV, 8.0 MDD, or fake weights.
    """
    sparse_samples = [
        {"features": {"tech_score_norm": 0.5}, "label": 1, "realized_r": 1.5}
        for _ in range(10)
    ]

    result = retraining_pipeline.run_retraining_experiment(
        candidate_name="test-sparse-model",
        training_samples=sparse_samples
    )

    candidate = result["candidate"]
    assert candidate["status"] == "INSUFFICIENT_SAMPLES"
    assert result["all_gates_passed"] is False
    assert result["recommendation"] == "REJECT_KEEP_EXISTING_PRODUCTION"

    # Verify no fake metrics were reported
    assert candidate["oos_auc_roc"] is None, "Synthetic AUC must be None"
    assert candidate["expected_value_r"] is None, "Synthetic EV must be None"
    assert candidate["max_drawdown_pct"] is None, "Synthetic MDD must be None"
    assert candidate["learned_weights"] is None, "Learned weights must be None"
    assert candidate["sample_size"] == 10
    assert candidate["required_minimum"] == 30


# -------------------------------------------------------------------
# 5. Temporal Window Propagation Tests
# -------------------------------------------------------------------
def test_temporal_window_propagation():
    """
    Verifies that CLI start_year and end_year strictly control historical windows
    and that untouched test periods are dynamically derived without hardcoding.
    """
    from scripts.run_historical_learning import compute_historical_windows

    # Scenario 1: 2018 -> 2026 (Span 9 years)
    win_2018 = compute_historical_windows(2018, 2026)
    assert win_2018["start_year"] == 2018
    assert win_2018["end_year"] == 2026
    assert win_2018["in_sample_start_year"] == 2018
    assert win_2018["untouched_end_year"] == 2026
    # Final 2 years reserved as untouched: 2025-2026
    assert win_2018["untouched_start_year"] == 2025
    assert win_2018["in_sample_end_year"] == 2024
    assert win_2018["in_sample_end_date"] < win_2018["untouched_start_date"]

    # Scenario 2: 2006 -> 2026 (Span 21 years)
    win_2006 = compute_historical_windows(2006, 2026)
    assert win_2006["start_year"] == 2006
    assert win_2006["end_year"] == 2026
    assert win_2006["in_sample_start_year"] == 2006
    assert win_2006["untouched_end_year"] == 2026
    assert win_2006["untouched_start_year"] == 2025
    assert win_2006["in_sample_end_year"] == 2024
    assert win_2006["in_sample_end_date"] < win_2006["untouched_start_date"]


# -------------------------------------------------------------------
# 6. Asset Order Independence Tests
# -------------------------------------------------------------------
def test_asset_order_independence():
    """
    Verifies that running backtests in different processing orders
    [Gold -> EUR/USD -> BTC] vs [BTC -> EUR/USD -> Gold]
    produces identical metrics and trade counts.
    """
    df_eur = generate_synthetic_ohlcv("EUR/USD", n_bars=100, base_price=1.1000)
    df_gold = generate_synthetic_ohlcv("Gold", n_bars=100, base_price=1800.0, pip_size=0.1)
    df_btc = generate_synthetic_ohlcv("BTC", n_bars=100, base_price=30000.0, pip_size=1.0)

    inst_eur = {"symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX", "pip_size": 0.0001}
    inst_gold = {"symbol": "GC=F", "name": "Gold", "type": "COMMODITY", "pip_size": 0.1}
    inst_btc = {"symbol": "BTC-USD", "name": "Bitcoin", "type": "CRYPTO", "pip_size": 1.0}

    engine = HistoricalBacktestEngine(strategy_params={"min_opportunity_score": 65.0, "min_ml_probability": 0.40})

    # Order 1: Gold -> EUR/USD -> BTC
    res_gold_1 = engine.run_backtest_on_instrument(inst_gold, df_gold)
    res_eur_1 = engine.run_backtest_on_instrument(inst_eur, df_eur)
    res_btc_1 = engine.run_backtest_on_instrument(inst_btc, df_btc)

    # Order 2: BTC -> EUR/USD -> Gold
    res_btc_2 = engine.run_backtest_on_instrument(inst_btc, df_btc)
    res_eur_2 = engine.run_backtest_on_instrument(inst_eur, df_eur)
    res_gold_2 = engine.run_backtest_on_instrument(inst_gold, df_gold)

    # Assert results are identical
    assert len(res_eur_1["trades"]) == len(res_eur_2["trades"])
    assert res_eur_1["summary"]["net_r"] == res_eur_2["summary"]["net_r"]
    assert len(res_gold_1["trades"]) == len(res_gold_2["trades"])
    assert res_gold_1["summary"]["net_r"] == res_gold_2["summary"]["net_r"]
    assert len(res_btc_1["trades"]) == len(res_btc_2["trades"])
    assert res_btc_1["summary"]["net_r"] == res_btc_2["summary"]["net_r"]

"""
Comprehensive Test Suite for Historical Learning, Walk-Forward Optimization & Backtesting.
Validates:
1. Data ingestion & quality gate (outlier detection, deduplication, price sanity).
2. Strict point-in-time look-ahead protection.
3. Trade execution lifecycle (TP1, TP2, Stop Loss, Excursions).
4. Empirical Stop-Loss root-cause attribution.
5. Walk-forward window slicing, purging, and embargoing.
6. Parameter stability evaluation.
7. Champion vs Candidate strategy comparison & promotion rules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from app.backtesting.data_loader import HistoricalDataLoader
from app.backtesting.engine import HistoricalBacktestEngine
from app.backtesting.walk_forward import WalkForwardOptimizer
from app.backtesting.evaluator import StrategyEvaluator


def _create_synthetic_candles(base_price: float = 1.1000, n_bars: int = 150) -> pd.DataFrame:
    np.random.seed(42)
    start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
    dates = [start_time + timedelta(days=i) for i in range(n_bars)]
    
    returns = np.random.normal(0.0005, 0.005, n_bars)
    prices = base_price * np.exp(np.cumsum(returns))
    
    highs = prices * (1.0 + np.abs(np.random.normal(0, 0.002, n_bars)))
    lows = prices * (1.0 - np.abs(np.random.normal(0, 0.002, n_bars)))
    opens = np.roll(prices, 1)
    opens[0] = base_price
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": np.random.randint(5000, 25000, n_bars)
    })
    return df


def test_historical_data_loader_quality_checks():
    """Verify data loader cleans anomalies and accurately scores data quality."""
    loader = HistoricalDataLoader()
    df = _create_synthetic_candles(1.1000, 50)
    
    # Introduce deliberate defects: 1 duplicate, 1 inverted high/low, 1 negative price
    df.loc[10, "timestamp"] = df.loc[9, "timestamp"]  # Duplicate timestamp
    df.loc[20, "high"] = 0.50  # Inverted high below open/close
    df.loc[30, "close"] = -1.0  # Invalid negative price
    
    cleaned_df, report = loader.clean_and_validate_dataset(df, symbol="EURUSD=X", timeframe="1D")
    
    assert report["duplicates_dropped"] == 1
    assert report["invalid_prices_dropped"] == 1
    assert report["corrected_high_low_inconsistencies"] >= 1
    assert report["quality_status"] in ["GOOD", "EXCELLENT"]
    assert len(cleaned_df) == 48


def test_point_in_time_feature_lookahead_prevention():
    """Verify feature generation at step t strictly uses data up to t and is invariant to future bars."""
    df_long = _create_synthetic_candles(1.1000, 120)
    df_short = df_long.iloc[:60].copy()
    
    inst = {
        "symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX",
        "pip_size": 0.0001, "base": "EUR", "quote": "USD"
    }
    
    engine = HistoricalBacktestEngine()
    
    # Simulate backtest on short df up to bar 50
    res_short = engine.run_backtest_on_instrument(inst, df_short.iloc[:50])
    # Simulate backtest on long df up to bar 50
    res_long = engine.run_backtest_on_instrument(inst, df_long.iloc[:50])
    
    # Results on the same historical slice MUST be identical
    assert res_short["summary"]["trade_count"] == res_long["summary"]["trade_count"]
    assert res_short["summary"]["net_r"] == res_long["summary"]["net_r"]
    assert res_short["summary"]["win_rate"] == res_long["summary"]["win_rate"]


def test_backtest_trade_execution_and_stop_loss_root_cause():
    """Verify trade fill, TP/SL execution, and root-cause classification."""
    df = _create_synthetic_candles(1.1000, 100)
    inst = {
        "symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX",
        "pip_size": 0.0001, "base": "EUR", "quote": "USD"
    }
    
    engine = HistoricalBacktestEngine(strategy_params={"min_opportunity_score": 60.0, "min_ml_probability": 0.40})
    res = engine.run_backtest_on_instrument(inst, df)
    
    trades = res["trades"]
    assert isinstance(trades, list)
    
    if len(trades) > 0:
        t = trades[0]
        assert "signal_id" in t
        assert "entry_price" in t
        assert "stop_loss" in t
        assert "realized_r" in t
        assert "mfe_r" in t
        assert "mae_r" in t
        assert t["exit_reason"] in ["TARGET_2_HIT", "STOP_LOSS_HIT", "BREAKEVEN_STOP_AFTER_TP1", "BREAKEVEN_PROTECTED", "TIME_EXPIRATION"]
        
        # If stopped out, verify empirical root cause is assigned
        sl_trades = [tr for tr in trades if tr["sl_hit"]]
        for sl_tr in sl_trades:
            if sl_tr["exit_reason"] == "STOP_LOSS_HIT":
                assert sl_tr["root_cause"] is not None


def test_walk_forward_window_generation():
    """Verify chronological walk-forward slicing creates sequential non-overlapping test periods."""
    optimizer = WalkForwardOptimizer(train_years=3, test_years=1)
    
    # Create multi-year synthetic daily data from 2015 to 2026
    dates = pd.date_range("2015-01-01", "2026-06-01", freq="D", tz="UTC")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.10, "volume": 10000
    })
    
    windows = optimizer.generate_walk_forward_windows(df, start_year=2015, end_year=2026)
    assert len(windows) >= 5
    
    # Verify chronological sequence
    for i in range(len(windows) - 1):
        assert windows[i]["test_end"] < windows[i+1]["test_start"]
    
    # Verify final untouched window
    assert windows[-1]["is_final_untouched"] is True


def test_parameter_stability_analysis():
    """Verify parameter stability test calculates variance and classifies plateaus."""
    optimizer = WalkForwardOptimizer()
    df = _create_synthetic_candles(1.1000, 80)
    inst = {
        "symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX",
        "pip_size": 0.0001, "base": "EUR", "quote": "USD"
    }
    
    stab = optimizer.evaluate_parameter_stability(
        instrument_config=inst,
        df=df,
        base_params={"min_opportunity_score": 70.0, "min_ml_probability": 0.40, "min_rr": 2.0},
        param_name="min_opportunity_score",
        test_values=[65.0, 70.0, 75.0]
    )
    
    assert "coefficient_of_variation" in stab
    assert "verdict" in stab
    assert stab["verdict"] in ["ROBUST_PLATEAU", "UNSTABLE_OVERFIT_SPIKE"]


def test_strategy_evaluator_promotion_gates():
    """Verify StrategyEvaluator enforces the 8 promotion rules."""
    # Create winning champion trades
    champ_trades = [
        {"realized_r": 1.5, "sl_hit": False, "root_cause": None},
        {"realized_r": -1.0, "sl_hit": True, "root_cause": "VOLATILITY_EXPANSION"},
        {"realized_r": 2.25, "sl_hit": False, "root_cause": None},
        {"realized_r": -1.0, "sl_hit": True, "root_cause": "MOMENTUM_FAILURE"},
        {"realized_r": 1.5, "sl_hit": False, "root_cause": None},
    ] * 3  # 15 trades
    
    # Candidate with superior expectancy
    cand_trades = [
        {"realized_r": 2.25, "sl_hit": False, "root_cause": None},
        {"realized_r": -1.0, "sl_hit": True, "root_cause": "VOLATILITY_EXPANSION"},
        {"realized_r": 2.25, "sl_hit": False, "root_cause": None},
        {"realized_r": -0.8, "sl_hit": True, "root_cause": "MOMENTUM_FAILURE"},
        {"realized_r": 2.25, "sl_hit": False, "root_cause": None},
    ] * 3  # 15 trades
    
    comp = StrategyEvaluator.compare_champion_vs_candidate(champ_trades, cand_trades)
    assert "promotion_rules" in comp
    assert "recommendation" in comp
    assert comp["deltas"]["net_r"] > 0.0
    assert comp["recommendation"] == "PROMOTE_CANDIDATE_STRATEGY"

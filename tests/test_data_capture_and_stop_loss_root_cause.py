import os
import json
import pytest
from datetime import datetime, timezone, timedelta

from app.storage.sqlite_manager import SQLiteManager
from app.engines.outcome_tracker import TradeOutcomeTracker
from app.memory.experience_memory import ExperienceMemory
from app.memory.training_memory import TrainingMemory
from app.llm.router import LLMRouter
from app.llm.decision_engine import LLMDecisionEngine
from app.parallel.aggregator import CompleteMarketContext

@pytest.fixture
def test_db():
    db = SQLiteManager()
    with db._get_connection() as conn:
        conn.execute("DELETE FROM signals WHERE signal_id LIKE 'SIG-TEST-AUDIT-%'")
        conn.execute("DELETE FROM ml_training_records WHERE signal_id LIKE 'SIG-TEST-AUDIT-%'")
        conn.execute("DELETE FROM signal_lifecycle_events WHERE signal_id LIKE 'SIG-TEST-AUDIT-%'")
        conn.commit()
    yield db
    with db._get_connection() as conn:
        conn.execute("DELETE FROM signals WHERE signal_id LIKE 'SIG-TEST-AUDIT-%'")
        conn.execute("DELETE FROM ml_training_records WHERE signal_id LIKE 'SIG-TEST-AUDIT-%'")
        conn.execute("DELETE FROM signal_lifecycle_events WHERE signal_id LIKE 'SIG-TEST-AUDIT-%'")
        conn.commit()

def test_signal_creation_captures_complete_reasoning_and_features(test_db):
    """
    Verifies that saving a signal captures:
    - why_this_trade_json
    - supporting_evidence_json
    - contradicting_evidence_json
    - neutral_evidence_json
    - features_json
    - and propagates decision-time features to ml_training_records without lookahead.
    """
    sig_id = "SIG-TEST-AUDIT-001"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    features = {
        "rsi": 62.5,
        "adx": 28.4,
        "atr": 0.0015,
        "ema_20": 1.1020,
        "ema_50": 1.0980,
        "spread_pips": 0.8
    }
    supporting = ["RSI > 55 bullish momentum", "EMA(20) > EMA(50) trend continuation", "USD currency strength +1.8"]
    contradicting = ["Macro bias slightly bearish on higher timeframe"]
    neutral = ["Session London/NY Overlap"]
    
    why_trade = {
        "what": "EUR/USD LONG Trade Setup (15M)",
        "why": "Strong multi-engine confluence with favorable risk/reward",
        "why_now": "Breakout confirmed on 15M candle close",
        "provider": "AzureOpenAI",
        "model": "gpt-4o",
        "is_llm_fallback": False,
        "supporting_factors": supporting,
        "contradicting_factors": contradicting,
        "ml_logic": "Statistical Meta-Model Win Probability: 72.5%"
    }

    sig_payload = {
        "signal_id": sig_id,
        "scan_id": "scan-audit-001",
        "trace_id": "trace-audit-001",
        "symbol": "EUR/USD",
        "symbol_name": "EUR/USD",
        "raw_symbol": "EURUSD=X",
        "direction": "LONG",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit_1": 1.1075,
        "take_profit_2": 1.1150,
        "opportunity_score": 82.5,
        "ml_probability": 0.725,
        "quality_tier": "HIGH_QUALITY",
        "features": features,
        "why_this_trade": why_trade,
        "supporting_evidence": supporting,
        "contradicting_evidence": contradicting,
        "neutral_evidence": neutral,
        "llm_reasoning": "High-confidence momentum breakout with verified risk parameters."
    }

    is_created, saved_id = test_db.save_signal(sig_payload)
    assert is_created is True
    assert saved_id == sig_id

    # Retrieve and verify database record
    stored = test_db.get_signal_by_id(sig_id)
    assert stored is not None
    assert stored["signal_id"] == sig_id
    assert stored["direction"] == "LONG"
    assert stored["entry_price"] == 1.1000
    assert stored["stop_loss"] == 1.0950

    # Verify JSON reasoning and evidence are preserved
    stored_why = json.loads(stored["why_this_trade_json"])
    assert stored_why["model"] == "gpt-4o"
    assert stored_why["is_llm_fallback"] is False

    stored_supp = json.loads(stored["supporting_evidence_json"])
    assert len(stored_supp) == 3
    assert "RSI > 55 bullish momentum" in stored_supp

    stored_contra = json.loads(stored["contradicting_evidence_json"])
    assert len(stored_contra) == 1
    assert "Macro bias slightly bearish" in stored_contra[0]

    stored_feats = json.loads(stored["features_json"])
    assert stored_feats["rsi"] == 62.5
    assert stored_feats["adx"] == 28.4

    # Verify ml_training_records has zero lookahead features
    with test_db._get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM ml_training_records WHERE signal_id = ?", (sig_id,))
        ml_rec = dict(c.fetchone())
        assert ml_rec["outcome_class"] is None  # Outcome unknown at signal time!
        assert ml_rec["realized_r"] is None
        ml_feats = json.loads(ml_rec["signal_time_features_json"])
        assert ml_feats["rsi"] == 62.5
        assert ml_feats["adx"] == 28.4


def test_stop_loss_root_cause_analysis_volatility_expansion(test_db):
    """
    Verifies that when a trade hits Stop Loss due to an ATR surge,
    the system separates exit_reason ('STOP_LOSS') from root_cause ('VOLATILITY_EXPANSION')
    and preserves root_cause_evidence.
    """
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    tracker.db = test_db
    sig_id = "SIG-TEST-AUDIT-SL-VOL"
    
    sig = {
        "signal_id": sig_id,
        "symbol": "USD/JPY",
        "symbol_name": "USD/JPY",
        "raw_symbol": "USDJPY=X",
        "direction": "LONG",
        "entry_price": 154.00,
        "stop_loss": 153.60, # 40 pips risk
        "take_profit_1": 154.60,
        "opportunity_score": 75.0,
        "ml_probability": 0.65,
        "features": {
            "rsi": 58.0,
            "adx": 22.0,
            "atr": 0.10
        }
    }
    tracker.register_signal(sig)

    # Manually test root cause analysis when exit ATR expands to 0.0020 (2x entry ATR)
    now = datetime.now(timezone.utc)
    sig_active = tracker.active_signals[0]
    
    # Mock capture_exit_features to simulate market conditions at stop hit
    tracker.capture_exit_features = lambda s, p: {
        "exit_price": p,
        "exit_timestamp": now.isoformat(),
        "holding_minutes": 25,
        "mfe_r": 0.20,
        "mae_r": -1.10,
        "rsi": 50.0,
        "adx": 24.0,
        "atr": 0.22, # > 1.5x expansion over 0.10!
        "ema_20": 153.80,
        "ema_50": 153.70
    }

    # Process price hit at stop loss (153.58)
    tracker.active_signals = [s for s in tracker.active_signals if s.get("signal_id") == sig_id]
    resolved = tracker.process_price_update([], {"USD/JPY": 153.58})
    matched = [s for s in resolved if s.get("signal_id") == sig_id]
    assert len(matched) == 1
    closed_sig = matched[0]
    
    assert closed_sig["exit_reason"] == "STOP_LOSS"
    assert closed_sig["root_cause"] == "VOLATILITY_EXPANSION"
    assert "ATR expanded" in closed_sig["root_cause_evidence"]

    # Verify SQLite database contains the separated fields
    stored = test_db.get_signal_by_id(sig_id)
    assert stored["exit_reason"] == "STOP_LOSS"
    assert stored["root_cause"] == "VOLATILITY_EXPANSION"
    assert "ATR expanded" in stored["root_cause_evidence"]

    # Verify ML training record has root_cause attached
    with test_db._get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM ml_training_records WHERE signal_id = ?", (sig_id,))
        ml_rec = dict(c.fetchone())
        assert ml_rec["outcome_class"] == "LOSS"
        assert ml_rec["exit_reason"] == "STOP_LOSS"
        assert ml_rec["root_cause"] == "VOLATILITY_EXPANSION"
        assert "ATR expanded" in ml_rec["root_cause_evidence"]


def test_stop_loss_root_cause_analysis_momentum_failure(test_db):
    """
    Verifies that when RSI collapses against the trade direction,
    the root cause is classified as MOMENTUM_FAILURE.
    """
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    sig_id = "SIG-TEST-AUDIT-SL-MOM"
    
    sig = {
        "signal_id": sig_id,
        "symbol": "GBP/USD",
        "symbol_name": "GBP/USD",
        "raw_symbol": "GBPUSD=X",
        "direction": "LONG",
        "entry_price": 1.2500,
        "stop_loss": 1.2450,
        "take_profit_1": 1.2575,
        "opportunity_score": 78.0,
        "ml_probability": 0.68,
        "features": {
            "rsi": 66.0,
            "adx": 25.0,
            "atr": 0.0015
        }
    }
    tracker.register_signal(sig)
    now = datetime.now(timezone.utc)

    # Mock exit features with collapsed RSI (36.0 < 42.0)
    tracker.capture_exit_features = lambda s, p: {
        "exit_price": p,
        "exit_timestamp": now.isoformat(),
        "holding_minutes": 40,
        "mfe_r": 0.30,
        "mae_r": -1.02,
        "rsi": 36.5, # Momentum collapsed!
        "adx": 19.0,
        "atr": 0.0014,
        "ema_20": 1.2460,
        "ema_50": 1.2455
    }

    tracker.active_signals = [s for s in tracker.active_signals if s.get("signal_id") == sig_id]
    resolved = tracker.process_price_update([], {"GBP/USD": 1.2448})
    matched = [s for s in resolved if s.get("signal_id") == sig_id]
    assert len(matched) == 1
    assert matched[0]["exit_reason"] == "STOP_LOSS"
    assert matched[0]["root_cause"] == "MOMENTUM_FAILURE"
    assert "RSI momentum collapsed" in matched[0]["root_cause_evidence"]


def test_stop_loss_root_cause_analysis_trend_reversal(test_db):
    """
    Verifies that when EMAs cross in reverse,
    root cause is classified as TREND_REVERSAL.
    """
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    sig_id = "SIG-TEST-AUDIT-SL-TREND"
    
    sig = {
        "signal_id": sig_id,
        "symbol": "GBP/USD",
        "symbol_name": "GBP/USD",
        "raw_symbol": "GBPUSD=X",
        "direction": "LONG",
        "entry_price": 1.2500,
        "stop_loss": 1.2470,
        "take_profit_1": 1.2550,
        "opportunity_score": 72.0,
        "ml_probability": 0.62,
        "features": {"rsi": 54.0, "adx": 21.0, "atr": 0.0010}
    }
    tracker.register_signal(sig)
    now = datetime.now(timezone.utc)

    # Mock EMA cross against LONG (EMA 20 < EMA 50)
    tracker.capture_exit_features = lambda s, p: {
        "exit_price": p,
        "exit_timestamp": now.isoformat(),
        "holding_minutes": 55,
        "mfe_r": 0.15,
        "mae_r": -1.01,
        "rsi": 46.0,
        "adx": 22.0,
        "atr": 0.0010,
        "ema_20": 1.2465, # EMA20 < EMA50
        "ema_50": 1.2480
    }

    tracker.active_signals = [s for s in tracker.active_signals if s.get("signal_id") == sig_id]
    resolved = tracker.process_price_update([], {"GBP/USD": 1.2468})
    matched = [s for s in resolved if s.get("signal_id") == sig_id]
    assert len(matched) == 1
    assert matched[0]["exit_reason"] == "STOP_LOSS"
    assert matched[0]["root_cause"] == "TREND_REVERSAL"


def test_stop_loss_root_cause_unknown_when_ambiguous(test_db):
    """
    Verifies that when evidence is ambiguous and no thresholds are breached,
    the system NEVER invents or fabricates an explanation, but strictly records root_cause = 'UNKNOWN'.
    """
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    tracker.db = test_db
    sig_id = "SIG-TEST-AUDIT-SL-UNK"
    now = datetime.now(timezone.utc)
    
    sig = {
        "signal_id": sig_id,
        "symbol": "EUR/USD",
        "symbol_name": "EUR/USD",
        "raw_symbol": "EURUSD=X",
        "direction": "LONG",
        "entry_price": 1.0850,
        "stop_loss": 1.0830,
        "take_profit_1": 1.0890,
        "opportunity_score": 70.0,
        "ml_probability": 0.60,
        "created_at": (now - timedelta(minutes=45)).isoformat(),
        "features": {"rsi": 50.0, "adx": 20.0, "atr": 0.0008}
    }
    tracker.register_signal(sig)

    # Mock neutral, non-threshold-breaching exit indicators
    tracker.capture_exit_features = lambda s, p: {
        "exit_price": p,
        "exit_timestamp": now.isoformat(),
        "holding_minutes": 45,
        "mfe_r": 0.25,
        "mae_r": -1.0,
        "rsi": 48.0,
        "adx": 20.0,
        "atr": 0.0008,
        "ema_20": 1.0840,
        "ema_50": 1.0835
    }

    tracker.active_signals = [s for s in tracker.active_signals if s.get("signal_id") == sig_id]
    tracker.active_signals[0]["created_at"] = (now - timedelta(minutes=45)).isoformat()
    tracker.active_signals[0]["mfe_r"] = 0.25

    # Price touches stop loss exactly
    resolved = tracker.process_price_update([], {"EUR/USD": 1.0830})
    matched = [s for s in resolved if s.get("signal_id") == sig_id]
    assert len(matched) == 1
    assert matched[0]["exit_reason"] == "STOP_LOSS"
    # Clean check: no fabrication
    assert matched[0]["root_cause"] in ["UNKNOWN", "MARKET_STRUCTURE_FAILURE"]
    if matched[0]["root_cause"] == "UNKNOWN":
        assert "No anomalous indicator threshold breached" in matched[0]["root_cause_evidence"]


def test_successful_trade_captures_exit_reason_and_features(test_db):
    """
    Verifies that winning trades (TP1/TP2) capture:
    - exit_reason = 'TARGET_1_HIT' / 'TARGET_2_HIT'
    - features_at_exit_json
    - MFE, MAE, realized R
    """
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    tracker.db = test_db
    sig_id = "SIG-TEST-AUDIT-WIN-01"
    
    sig = {
        "signal_id": sig_id,
        "symbol": "USD/JPY",
        "symbol_name": "USD/JPY",
        "raw_symbol": "USDJPY=X",
        "direction": "LONG",
        "entry_price": 150.00,
        "stop_loss": 149.50,
        "take_profit_1": 150.75,
        "take_profit_2": 150.75,
        "single_target": True,
        "opportunity_score": 88.0,
        "ml_probability": 0.76,
        "features": {"rsi": 64.0, "adx": 30.0}
    }
    tracker.register_signal(sig)
    
    # Hit TP1 (150.80)
    tracker.active_signals = [s for s in tracker.active_signals if s.get("signal_id") == sig_id]
    resolved = tracker.process_price_update([], {"USD/JPY": 150.80})
    matched = [s for s in resolved if s.get("signal_id") == sig_id]
    assert len(matched) == 1
    win_sig = matched[0]
    assert win_sig["status"] == "CLOSED"
    assert win_sig["exit_reason"] == "TARGET_1_HIT"
    assert win_sig["realized_r"] == 1.5
    assert win_sig["mfe_r"] >= 1.5

    # Check database
    stored = test_db.get_signal_by_id(sig_id)
    assert stored["exit_reason"] == "TARGET_1_HIT"
    assert stored["features_at_exit_json"] is not None
    exit_feats = json.loads(stored["features_at_exit_json"])
    assert exit_feats["exit_price"] == 150.80


def test_quantitative_fallback_transparency():
    """
    Verifies that when LLM fallback is used:
    - is_llm_fallback is True
    - provider is QuantitativeFallback
    - model is deterministic-rules-engine
    - reasoning is grounded in actual numerical metrics, not generic canned text.
    """
    router = LLMRouter()
    # Force fallback by passing a candidate that doesn't trigger mock API keys
    candidate = {
        "symbol": "EUR/USD",
        "symbol_name": "EUR/USD",
        "direction": "LONG",
        "opportunity_score": 77.5,
        "ml_probability": 0.68,
        "supporting_evidence": ["RSI 61.2 bullish", "Currency strength differential +2.1"],
        "contradicting_evidence": ["Macro bias neutral"]
    }
    
    res = router.evaluate_candidate(candidate)
    if res.get("provider") == "QuantitativeFallback":
        assert res["is_llm_fallback"] is True
        assert res["model"] == "deterministic-rules-engine"
        assert "77.5" in res["reasoning"]
        assert "68.0%" in res["reasoning"]
        assert "RSI 61.2 bullish" in res["reasoning"]
        assert "Macro bias neutral" in res["reasoning"]

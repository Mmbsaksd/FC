import pytest
from fastapi.testclient import TestClient
from app.engines.outcome_tracker import TradeOutcomeTracker
from app.api.server import app

client = TestClient(app)

def test_long_signal_lifecycle_t1_then_t2():
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    with tracker.db._get_connection() as conn:
        conn.execute("DELETE FROM signals WHERE signal_id LIKE 'SIG-TEST-%'")
        conn.commit()
    tracker.active_signals = []
    tracker.closed_signals = []
    tracker.lifecycle_events = []

    # Register LONG signal
    sig = {
        "signal_id": "SIG-TEST-LONG-01",
        "scan_id": "scan-1",
        "trace_id": "trace-1",
        "symbol_name": "EUR/USD",
        "symbol": "EUR_USD",
        "direction": "LONG",
        "entry_price": 1.0800,
        "stop_loss": 1.0750, # Risk = 0.0050
        "take_profit_1": 1.0875, # TP1 = +1.5R (0.0075)
        "take_profit_2": 1.0950, # TP2 = +3.0R (0.0150)
        "opportunity_score": 85.0,
        "ml_probability": 0.72
    }
    tracker.register_signal(sig)
    assert len(tracker.active_signals) == 1
    assert tracker.active_signals[0]["status"] == "MONITORING"

    # Step 1: Price touches TP1 (1.0880)
    tracker.process_price_update([], {"EUR_USD": 1.0880})
    assert tracker.active_signals[0]["t1_hit"] is True
    assert tracker.active_signals[0]["status"] == "TARGET_1_HIT"
    assert tracker.active_signals[0]["realized_r"] == 0.75 # 50% of 1.5R

    # Step 2: Price continues and touches TP2 (1.0960)
    resolved = tracker.process_price_update([], {"EUR_USD": 1.0960})
    assert len(resolved) == 1
    assert len(tracker.active_signals) == 0
    assert len(tracker.closed_signals) == 1
    assert tracker.closed_signals[0]["status"] == "TARGET_2_HIT"
    assert tracker.closed_signals[0]["realized_r"] == 2.25 # 50% @ 1.5R + 50% @ 3.0R = 2.25R


def test_short_signal_lifecycle_straight_stop():
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    with tracker.db._get_connection() as conn:
        conn.execute("DELETE FROM signals WHERE signal_id LIKE 'SIG-TEST-%'")
        conn.commit()
    tracker.active_signals = []
    tracker.closed_signals = []
    tracker.lifecycle_events = []

    # Register SHORT signal
    sig = {
        "signal_id": "SIG-TEST-SHORT-01",
        "scan_id": "scan-2",
        "trace_id": "trace-2",
        "symbol_name": "GBP/USD",
        "symbol": "GBP_USD",
        "direction": "SHORT",
        "entry_price": 1.3000,
        "stop_loss": 1.3050, # Risk = 0.0050
        "take_profit_1": 1.2925,
        "take_profit_2": 1.2850,
        "opportunity_score": 78.0,
        "ml_probability": 0.68
    }
    tracker.register_signal(sig)

    # Price moves up against SHORT and touches Stop Loss (1.3060)
    resolved = tracker.process_price_update([], {"GBP_USD": 1.3060})
    assert len(resolved) == 1
    assert tracker.closed_signals[0]["status"] == "STOPPED_OUT"
    assert tracker.closed_signals[0]["realized_r"] == -1.0


def test_outcome_analytics_summary():
    tracker = TradeOutcomeTracker(storage_path="tests/test_outcomes.json")
    tracker.active_signals = []
    tracker.closed_signals = [
        {"signal_id": "s1", "symbol": "EUR/USD", "direction": "LONG", "opportunity_score": 82.0, "realized_r": 2.25, "realized_pnl": 225.0, "t1_hit": True, "t2_hit": True, "sl_hit": False, "expired": False},
        {"signal_id": "s2", "symbol": "GBP/USD", "direction": "SHORT", "opportunity_score": 75.0, "realized_r": -1.0, "realized_pnl": -100.0, "t1_hit": False, "t2_hit": False, "sl_hit": True, "expired": False},
        {"signal_id": "s3", "symbol": "USD/JPY", "direction": "LONG", "opportunity_score": 65.0, "realized_r": 1.5, "realized_pnl": 150.0, "t1_hit": True, "t2_hit": True, "sl_hit": False, "expired": False},
    ]
    summary = tracker.get_analytics_summary()
    assert summary["total_alerts"] == 3
    assert summary["closed_alerts"] == 3
    assert summary["winning_signals"] == 2
    assert summary["losing_signals"] == 1
    assert summary["win_rate_pct"] == 66.7
    assert summary["target_1_hits"] == 2
    assert summary["stop_loss_hits"] == 1
    assert summary["total_pnl_usd"] == 275.0


def test_api_signal_outcome_endpoints():
    res_analytics = client.get("/api/signals/analytics")
    assert res_analytics.status_code == 200
    data = res_analytics.json()
    assert "win_rate_pct" in data
    assert "target_1_rate_pct" in data

    res_active = client.get("/api/signals/active")
    assert res_active.status_code == 200

    res_history = client.get("/api/signals/history")
    assert res_history.status_code == 200

    res_events = client.get("/api/signals/events")
    assert res_events.status_code == 200

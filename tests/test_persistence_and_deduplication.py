import os
import sys
import shutil
import tempfile
import pytest
from datetime import datetime, timezone

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.storage.sqlite_manager import SQLiteManager
from app.engines.outcome_tracker import TradeOutcomeTracker

@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "test_trading.db")
    manager = SQLiteManager(db_path=temp_db_path)
    yield manager, temp_db_path
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_database_initialization_and_tables(temp_db):
    manager, _ = temp_db
    with manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {
            "signals",
            "signal_lifecycle_events",
            "market_snapshots",
            "engine_analytical_results",
            "ml_training_records",
            "notification_logs",
            "system_observability_events"
        }
        assert expected_tables.issubset(tables)

def test_signal_fingerprint_generation_and_deduplication(temp_db):
    manager, _ = temp_db

    # 1. Deterministic fingerprint for Long EUR/USD setup
    fp1 = manager.compute_fingerprint("EUR/USD", "LONG", 1.08500, 1.08200, 1.08950)
    fp2 = manager.compute_fingerprint("EUR/USD", "LONG", 1.08502, 1.08201, 1.08949) # Micro-variance within bucket
    assert fp1 == fp2, "Similar setup should produce identical deterministic fingerprint"

    # 2. Save Initial Signal
    sig1 = {
        "signal_id": "SIG-PERSIST-001",
        "symbol_name": "EUR/USD",
        "direction": "LONG",
        "entry_price": 1.08500,
        "stop_loss": 1.08200,
        "take_profit_1": 1.08950,
        "take_profit_2": 1.09400,
        "opportunity_score": 85.0,
        "ml_probability": 0.72
    }
    is_created, _ = manager.save_signal(sig1)
    assert is_created is True

    # 3. Attempt duplicate signal while active
    is_dup_created, _ = manager.save_signal(sig1)
    assert is_dup_created is False, "Active setup must not create duplicate record"

def test_restart_recovery_and_deduplication(temp_db):
    manager, db_path = temp_db

    sig = {
        "signal_id": "SIG-RESTART-001",
        "symbol_name": "GBP/USD",
        "direction": "SHORT",
        "entry_price": 1.29500,
        "stop_loss": 1.29800,
        "take_profit_1": 1.29050,
        "take_profit_2": 1.28600,
        "opportunity_score": 82.0,
        "ml_probability": 0.68
    }
    manager.save_signal(sig)

    # Simulate Application / Machine Restart: Instantiate new SQLiteManager pointing to the same DB file
    new_manager = SQLiteManager(db_path=db_path)
    active = new_manager.get_active_signals()

    # Verify signal exists after restart
    matched = [s for s in active if s["signal_id"] == "SIG-RESTART-001"]
    assert len(matched) == 1
    assert matched[0]["symbol"] == "GBP/USD"
    assert matched[0]["status"] == "MONITORING"

    # Verify duplicate is still blocked after restart
    fp = new_manager.compute_fingerprint("GBP/USD", "SHORT", 1.29500, 1.29800, 1.29050)
    assert new_manager.is_duplicate_active_signal(fp) is True

def test_event_idempotency_and_lifecycle_transitions(temp_db):
    manager, _ = temp_db

    sig_id = "SIG-EVENT-001"
    manager.save_signal({
        "signal_id": sig_id,
        "symbol_name": "USD/JPY",
        "direction": "LONG",
        "entry_price": 155.000,
        "stop_loss": 154.500,
        "take_profit_1": 155.750,
        "take_profit_2": 156.500,
        "opportunity_score": 78.0,
        "ml_probability": 0.65
    })

    # Log initial TARGET_1_HIT event
    first_logged = manager.record_event(sig_id, "TARGET_1_HIT", 155.750, "Target 1 hit")
    assert first_logged is True

    # Attempt duplicate TARGET_1_HIT event
    dup_logged = manager.record_event(sig_id, "TARGET_1_HIT", 155.760, "Target 1 hit repeat")
    assert dup_logged is False, "Duplicate event on same signal must be rejected idempotently"

    detail = manager.get_signal_by_id(sig_id)
    events = detail["events"]
    # Should have SIGNAL_CREATED and exactly ONE TARGET_1_HIT
    t1_events = [e for e in events if e["event"] == "TARGET_1_HIT"]
    assert len(t1_events) == 1

def test_ml_training_record_retention_without_leakage(temp_db):
    manager, _ = temp_db

    sig_id = "SIG-ML-001"
    manager.save_signal({
        "signal_id": sig_id,
        "symbol_name": "Gold",
        "direction": "LONG",
        "entry_price": 2500.00,
        "stop_loss": 2485.00,
        "take_profit_1": 2522.50,
        "take_profit_2": 2545.00,
        "opportunity_score": 88.0,
        "ml_probability": 0.75,
        "features": {"rsi": 42.5, "atr": 12.4, "regime": "TRENDING_UP"}
    })

    # Update Outcome upon trade resolution
    manager.update_ml_training_outcome(
        signal_id=sig_id,
        outcome_class="WIN",
        realized_r=2.25,
        realized_pnl=225.00,
        mfe_r=2.50,
        mae_r=-0.20,
        holding_mins=45
    )

    with manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ml_training_records WHERE signal_id = ?", (sig_id,))
        row = dict(cursor.fetchone())
        assert row["outcome_class"] == "WIN"
        assert row["realized_r"] == 2.25
        assert "rsi" in row["signal_time_features_json"]

if __name__ == "__main__":
    def run_with_fresh_fixture(test_func, test_name):
        print(f"Testing {test_name}...")
        tdir = tempfile.mkdtemp()
        tpath = os.path.join(tdir, "test.db")
        m = SQLiteManager(db_path=tpath)
        try:
            test_func((m, tpath))
            print(f"[OK] {test_name} OK")
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    run_with_fresh_fixture(test_database_initialization_and_tables, "Database Tables Initialization")
    run_with_fresh_fixture(test_signal_fingerprint_generation_and_deduplication, "Signal Fingerprinting & Deduplication")
    run_with_fresh_fixture(test_restart_recovery_and_deduplication, "Restart Recovery")
    run_with_fresh_fixture(test_event_idempotency_and_lifecycle_transitions, "Event Idempotency & Lifecycle Transitions")
    run_with_fresh_fixture(test_ml_training_record_retention_without_leakage, "ML Training Record Retention")

    print("\n>>> ALL PERSISTENCE AND DEDUPLICATION TESTS PASSED! <<<")

import json
import sqlite3

def reconstruct_trade(signal_id: str):
    conn = sqlite3.connect('f:/FC/data/trading_system.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Signal & Decision State
    c.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,))
    sig_row = c.fetchone()
    if not sig_row:
        conn.close()
        return None
    sig = dict(sig_row)

    # 2. Revisions
    c.execute("SELECT * FROM signal_revisions WHERE signal_id = ? ORDER BY version_number ASC", (signal_id,))
    revs = [dict(r) for r in c.fetchall()]

    # 3. Lifecycle Events
    c.execute("SELECT * FROM signal_lifecycle_events WHERE signal_id = ? ORDER BY id ASC", (signal_id,))
    events = [dict(r) for r in c.fetchall()]

    # 4. Engine Results (if scan_id present)
    scan_id = sig.get("scan_id")
    c.execute("SELECT engine_name, direction, score, confidence, features_json FROM engine_analytical_results WHERE scan_id = ?", (scan_id,))
    engines = [dict(r) for r in c.fetchall()]

    # 5. ML Training Record
    c.execute("SELECT * FROM ml_training_records WHERE signal_id = ?", (signal_id,))
    ml_row = c.fetchone()
    ml_rec = dict(ml_row) if ml_row else None

    conn.close()

    # Parse JSON fields safely
    def parse_j(val):
        if not val:
            return {}
        try:
            return json.loads(val)
        except Exception:
            return str(val)

    return {
        "signal_id": sig["signal_id"],
        "symbol": sig["symbol"],
        "direction": sig["direction"],
        "entry_price": sig["entry_price"],
        "stop_loss": sig["stop_loss"],
        "take_profit_1": sig["take_profit_1"],
        "take_profit_2": sig["take_profit_2"],
        "risk_reward": sig["risk_reward"],
        "opportunity_score": sig["opportunity_score"],
        "ml_probability": sig["ml_probability"],
        "created_at": sig["created_at"],
        "updated_at": sig["updated_at"],
        "why_trade": parse_j(sig.get("why_this_trade_json")),
        "supporting_evidence": parse_j(sig.get("supporting_evidence_json")),
        "contradicting_evidence": parse_j(sig.get("contradicting_evidence_json")),
        "features_at_entry": parse_j(sig.get("features_json")),
        "features_at_exit": parse_j(sig.get("features_at_exit_json")),
        "exit_reason": sig.get("exit_reason"),
        "root_cause": sig.get("root_cause"),
        "root_cause_evidence": sig.get("root_cause_evidence"),
        "outcome": sig.get("outcome"),
        "realized_r": sig.get("realized_r"),
        "mfe_r": sig.get("mfe_r"),
        "mae_r": sig.get("mae_r"),
        "revisions_count": len(revs),
        "lifecycle_events": events,
        "engine_evaluations_count": len(engines),
        "ml_training_record": ml_rec
    }

def test_historical_reconstruction_on_sample_trades():
    conn = sqlite3.connect('f:/FC/data/trading_system.db')
    c = conn.cursor()
    # Pick a sample of varied trades: WIN, LOSS/STOP, EXPIRED, etc.
    c.execute("SELECT signal_id, outcome, status FROM signals LIMIT 5")
    sample_ids = [r[0] for r in c.fetchall()]
    conn.close()

    assert len(sample_ids) > 0
    for sid in sample_ids:
        recon = reconstruct_trade(sid)
        assert recon is not None
        assert recon["signal_id"] == sid
        assert recon["symbol"] is not None
        assert recon["direction"] in ["LONG", "SHORT"]
        assert recon["entry_price"] > 0
        assert recon["stop_loss"] > 0
        assert recon["take_profit_1"] > 0
        # Check event timeline
        assert len(recon["lifecycle_events"]) > 0
        print(f"Reconstructed {sid}: {recon['symbol']} {recon['direction']} -> Outcome: {recon['outcome']} (R: {recon['realized_r']}) | Exit Reason: {recon['exit_reason']} | Root Cause: {recon['root_cause']}")

if __name__ == "__main__":
    test_historical_reconstruction_on_sample_trades()

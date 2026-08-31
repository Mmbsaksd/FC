import os
import sys
import sqlite3

# Set root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def audit_delivery():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/trading_system.db"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("================================================================")
    print("1. SUMMARY OF LIFECYCLE EVENTS PERSISTED IN SQLITE")
    print("================================================================")
    c.execute("SELECT event_type, COUNT(*) as cnt FROM signal_lifecycle_events GROUP BY event_type")
    for r in c.fetchall():
        print(f"  - {r['event_type']:<20}: {r['cnt']} events")

    print("\n================================================================")
    print("2. LATEST 10 LIFECYCLE PROGRESSION EVENTS WITH TIMESTAMPS")
    print("================================================================")
    c.execute("SELECT event_type, signal_id, timestamp, price, detail FROM signal_lifecycle_events ORDER BY id DESC LIMIT 10")
    for r in c.fetchall():
        print(f"  [{r['event_type']}] {r['signal_id']} | Price: {r['price']} | Time: {r['timestamp']}")
        print(f"    Detail: {r['detail']}")

    print("\n================================================================")
    print("3. ACTIVE SIGNALS VS CLOSED SIGNALS BREAKDOWN")
    print("================================================================")
    c.execute("SELECT status, COUNT(*) as cnt FROM signals GROUP BY status")
    for r in c.fetchall():
        print(f"  - Status {r['status']:<15}: {r['cnt']} trades")

    print("\n================================================================")
    print("4. COMPLETED WINS & LOSSES REALIZED METRICS")
    print("================================================================")
    c.execute("""
        SELECT symbol, direction, entry_price, current_price, outcome, realized_r, realized_pnl, holding_minutes, updated_at
        FROM signals
        WHERE status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT')
        ORDER BY updated_at DESC
        LIMIT 10
    """)
    for r in c.fetchall():
        print(f"  {r['symbol']:<15} {r['direction']:<6} Entry: {r['entry_price']:<10.4f} Exit: {r['current_price']:<10.4f} Outcome: {r['outcome']:<15} R: {r['realized_r']:>+5.2f}R PnL: ${r['realized_pnl']:>+7.2f}")

    print("================================================================")

if __name__ == "__main__":
    audit_delivery()

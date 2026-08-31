"""
Real-time Diagnostic Script: Compares all active signals in SQLite against live market data feeds.
Checks whether any TP1, TP2, or SL levels have been reached in real-time.
"""

import os
import sys

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timezone
from app.storage.sqlite_manager import db_manager
from app.providers.yahoo_provider import YahooMarketDataProvider
from app.engines.outcome_tracker import outcome_tracker

def run_realtime_check():
    provider = YahooMarketDataProvider()
    signals = db_manager.get_active_signals()
    
    print(f"Total Active Signals in Persistent DB: {len(signals)}")
    print("=" * 85)
    print(f"{'SYMBOL':<15} {'DIR':<6} {'ENTRY':<11} {'LIVE PRICE':<11} {'TP1':<11} {'SL':<11} {'DIFF TO TP1':<12} {'DIFF TO SL':<12}")
    print("=" * 85)
    
    # Collect live prices for each unique asset
    unique_symbols = list(set(s.get("raw_symbol") or s.get("symbol") for s in signals))
    live_prices = {}
    
    for sym in unique_symbols:
        p_sym = sym
        if "BTC" in sym or "Bitcoin" in sym: p_sym = "BTC-USD"
        elif "ETH" in sym or "Ethereum" in sym: p_sym = "ETH-USD"
        elif "SOL" in sym or "Solana" in sym: p_sym = "SOL-USD"
        elif "XRP" in sym or "Ripple" in sym: p_sym = "XRP-USD"
        elif "/" in sym: p_sym = sym.replace("/", "") + "=X"
        elif "Gold" in sym: p_sym = "GC=F"
        elif "Oil" in sym: p_sym = "CL=F"
        
        try:
            df = provider.fetch_ohlcv(p_sym, timeframe="15M", limit=5)
            if not df.empty:
                close = float(df["close"].iloc[-1])
                live_prices[sym] = close
                live_prices[p_sym] = close
        except Exception as e:
            pass

    tp1_crosses = []
    sl_crosses = []
    pending_count = 0

    for s in signals:
        sym = s["symbol"]
        raw = s.get("raw_symbol", sym)
        live = live_prices.get(sym) or live_prices.get(raw) or s["entry_price"]
        
        entry = float(s["entry_price"])
        tp1 = float(s["take_profit_1"])
        tp2 = float(s["take_profit_2"] or tp1)
        sl = float(s["stop_loss"])
        d = s["direction"]
        
        is_long = (d == "LONG")
        hit_tp1 = (live >= tp1) if is_long else (live <= tp1)
        hit_sl = (live <= sl) if is_long else (live >= sl)
        
        diff_tp1 = (tp1 - live) if is_long else (live - tp1)
        diff_sl = (live - sl) if is_long else (sl - live)
        
        if hit_tp1:
            tp1_crosses.append((s["signal_id"], sym, d, entry, live, tp1))
        elif hit_sl:
            sl_crosses.append((s["signal_id"], sym, d, entry, live, sl))
        else:
            pending_count += 1
            
        print(f"{sym:<15} {d:<6} {entry:<11.4f} {live:<11.4f} {tp1:<11.4f} {sl:<11.4f} {diff_tp1:<12.4f} {diff_sl:<12.4f}")

    print("=" * 85)
    print(f"Summary of Real-Time Comparison:")
    print(f"  - Pending in Range (MONITORING): {pending_count} signals")
    print(f"  - Reached TP1: {len(tp1_crosses)} signals")
    print(f"  - Reached SL: {len(sl_crosses)} signals")

if __name__ == "__main__":
    run_realtime_check()

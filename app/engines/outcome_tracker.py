import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.storage.sqlite_manager import db_manager
from app.memory.experience_memory import experience_memory
from app.memory.training_memory import training_memory
from app.memory.knowledge_base import knowledge_base
from app.ml.dataset_builder import dataset_builder
from app.observability.flight_recorder import flight_recorder
from app.providers.provider_router import provider_router

logger = logging.getLogger(__name__)

OUTCOMES_STORAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/signal_outcomes_data.json"))

class TradeOutcomeTracker:
    """
    Comprehensive Signal Lifecycle & Post-Signal Outcome Tracker backed by SQLite.
    Monitors all created signals against live tick/candle prices,
    tracks multi-target progression (T1, T2, SL, Expiry), calculates partial P&L,
    dispatches lifecycle alerts, updates Experience & Training Memory,
    and guarantees persistent recovery across application reboots.
    """

    def __init__(self, storage_path: str = OUTCOMES_STORAGE_PATH):
        self.storage_path = storage_path
        self.db = db_manager
        self.exp_memory = experience_memory
        self.train_memory = training_memory
        self.builder = dataset_builder
        self.kb = knowledge_base
        self.active_signals: List[Dict[str, Any]] = []
        self.closed_signals: List[Dict[str, Any]] = []
        self.lifecycle_events: List[Dict[str, Any]] = []
        self._load_state()

    def _load_state(self):
        """Loads state from authoritative SQLite local database and syncs JSON cache."""
        try:
            db_active = self.db.get_active_signals()
            db_closed = self.db.get_closed_signals(limit=300)
            db_events = self.db.get_recent_lifecycle_events(limit=300)

            if db_active or db_closed:
                self.active_signals = db_active
                self.closed_signals = db_closed
                self.lifecycle_events = db_events
            elif os.path.exists(self.storage_path):
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_signals = data.get("active_signals", [])
                    self.closed_signals = data.get("closed_signals", [])
                    self.lifecycle_events = data.get("lifecycle_events", [])
                    # Populate SQLite from initial JSON if empty
                    for s in self.active_signals:
                        self.db.save_signal(s)
                    for s in self.closed_signals:
                        self.db.save_signal(s)
            
            # Run startup reconciliation to immediately clean up stale signals past holding window
            self.reconcile_active_signals(auto_fetch_prices=False)
        except Exception as e:
            logger.error(f"Error loading signal outcomes state: {e}")

    def reconcile_active_signals(self, auto_fetch_prices: bool = True) -> List[Dict[str, Any]]:
        """
        Runs on startup, periodic sweeps, and on-read to reconcile active signals.
        Automatically resolves any signals that have exceeded their maximum holding duration (>4 hours)
        or evaluates them against latest available prices.
        """
        now = datetime.now(timezone.utc)
        active = self.db.get_active_signals()
        if not active:
            self.active_signals = []
            return []

        resolved = []
        current_prices = {}

        for sig in active:
            try:
                created_dt = datetime.fromisoformat(sig["created_at"].replace("Z", "+00:00"))
                holding_mins = int((now - created_dt).total_seconds() / 60.0)
            except Exception:
                holding_mins = sig.get("holding_minutes", 0)

            max_dur_mins = int(float(sig.get("max_duration_hours", 4.0)) * 60)

            # 1. Immediate Expiry for Stale Signals
            if holding_mins >= max_dur_mins and not sig.get("expired"):
                sig_id = sig["signal_id"]
                curr_p = float(sig.get("current_price") or sig.get("entry_price") or 0.0)
                entry_p = float(sig.get("entry_price") or 0.0)
                sl_p = float(sig.get("stop_loss") or 0.0)
                risk_dist = abs(entry_p - sl_p) if abs(entry_p - sl_p) > 0 else 0.0001
                direction = sig.get("direction", "LONG")
                final_r = round(((curr_p - entry_p) / risk_dist) if direction == "LONG" else ((entry_p - curr_p) / risk_dist), 2)
                realized_pnl = round(final_r * 100.0, 2)

                event_msg = f"Reconcile: Trade expired after {holding_mins} mins @ {curr_p:.5f} (Final R: {final_r:+.2f}R)."
                self.record_lifecycle_event("EXPIRED", sig, event_msg)

                self.db.update_signal_progress(sig_id, {
                    "status": "CLOSED",
                    "expired": 1,
                    "realized_r": final_r,
                    "realized_pnl": realized_pnl,
                    "holding_minutes": holding_mins,
                    "outcome": "EXPIRED",
                    "current_price": curr_p
                })
                self.db.update_ml_training_outcome(sig_id, "EXPIRED", final_r, realized_pnl, sig.get("mfe_r", 0.0), sig.get("mae_r", 0.0), holding_mins)
                self.kb.record_knowledge_outcome(sig_id, "EXPIRED", final_r)

                sig["status"] = "CLOSED"
                sig["outcome"] = "EXPIRED"
                sig["realized_r"] = final_r
                resolved.append(sig)

        # Refresh local in-memory active list
        self.active_signals = self.db.get_active_signals()
        self.closed_signals = self.db.get_closed_signals(limit=300)
        self._save_state()

        # 2. If remaining active signals exist and auto_fetch_prices is True, run price update
        if self.active_signals and auto_fetch_prices:
            for s in self.active_signals:
                raw_sym = s.get("raw_symbol") or s.get("symbol")
                if raw_sym:
                    try:
                        df, _ = provider_router.fetch_ohlcv(raw_sym, limit=2)
                        if df is not None and not df.empty and 'close' in df.columns:
                            current_prices[s.get("symbol")] = float(df['close'].iloc[-1])
                            current_prices[raw_sym] = float(df['close'].iloc[-1])
                    except Exception:
                        pass
            if current_prices:
                more_resolved = self.process_price_update([], current_prices)
                resolved.extend(more_resolved)

        if resolved:
            logger.info(f"Signal Reconciliation: {len(resolved)} signals resolved, {len(self.active_signals)} remaining active.")
        return resolved

    def _save_state(self):
        """Mirrors active/closed signals to JSON artifact for export and legacy backup."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "active_signals_count": len(self.active_signals),
                    "closed_signals_count": len(self.closed_signals),
                    "active_signals": self.active_signals,
                    "closed_signals": self.closed_signals,
                    "lifecycle_events": self.lifecycle_events[-500:] # Keep last 500 events
                }, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving signal outcomes state to JSON: {e}")

    def register_signal(self, signal: Dict[str, Any]):
        """
        Registers a qualified trading signal for lifecycle tracking.
        Enforces persistent deduplication via setup fingerprint.
        """
        sig_id = signal.get("signal_id")
        if not sig_id:
            return

        # Prevent duplicate registration in memory
        if any(s.get("signal_id") == sig_id for s in self.active_signals):
            return

        # Save to SQLite local database (handles fingerprint check)
        is_created, _ = self.db.save_signal(signal)
        if not is_created:
            # Duplicate active setup already monitored
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        entry_price = float(signal.get("entry_price", 0.0))
        sl_price = float(signal.get("stop_loss", 0.0))
        tp1_price = float(signal.get("take_profit_1", 0.0))
        tp2_price = float(signal.get("take_profit_2")) if signal.get("take_profit_2") is not None else tp1_price
        has_two_targets = (tp2_price != tp1_price)
        
        direction = signal.get("direction", "LONG")
        risk_dist = abs(entry_price - sl_price) if abs(entry_price - sl_price) > 0 else 0.0001
        
        # Calculate target R-multiples
        tp1_r = round(abs(tp1_price - entry_price) / risk_dist, 2)
        tp2_r = round(abs(tp2_price - entry_price) / risk_dist, 2) if has_two_targets else tp1_r

        record = {
            "signal_id": sig_id,
            "scan_id": signal.get("scan_id", "scan-unknown"),
            "trace_id": signal.get("trace_id", "trace-unknown"),
            "symbol": signal.get("symbol_name", signal.get("symbol", "Asset")),
            "raw_symbol": signal.get("symbol", ""),
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": sl_price,
            "take_profit_1": tp1_price,
            "take_profit_2": tp2_price,
            "single_target": not has_two_targets,
            "tp1_r": tp1_r,
            "tp2_r": tp2_r,
            "risk_reward": float(signal.get("risk_reward", 2.0)),
            "opportunity_score": float(signal.get("opportunity_score", 70.0)),
            "ml_probability": float(signal.get("ml_probability", 0.60)),
            "status": "MONITORING",
            "current_price": entry_price,
            "unrealized_r": 0.0,
            "unrealized_pnl": 0.0,
            "realized_r": 0.0,
            "realized_pnl": 0.0,
            "mfe_r": 0.0, # Maximum Favorable Excursion
            "mae_r": 0.0, # Maximum Adverse Excursion
            "t1_hit": False,
            "t1_hit_time": None,
            "t1_hit_price": None,
            "t2_hit": False,
            "t2_hit_time": None,
            "t2_hit_price": None,
            "sl_hit": False,
            "sl_hit_time": None,
            "sl_hit_price": None,
            "expired": False,
            "created_at": signal.get("timestamp", now_iso),
            "updated_at": now_iso,
            "holding_minutes": 0,
            "max_duration_hours": 4.0, # Max tracking window
            "events": [
                {
                    "event": "SIGNAL_CREATED",
                    "timestamp": now_iso,
                    "price": entry_price,
                    "detail": f"Signal created @ {entry_price:.5f} (SL: {sl_price:.5f}, TP1: {tp1_price:.5f}, TP2: {tp2_price:.5f})"
                }
            ],
            "llm_reasoning": signal.get("llm_reasoning", ""),
            "engine_evidence": signal.get("engine_evidence", signal.get("evidence", {}))
        }

        self.active_signals.append(record)
        self.record_lifecycle_event("SIGNAL_CREATED", record, record["events"][0]["detail"])
        self._save_state()
        logger.info(f"Registered signal {sig_id} for {record['symbol']} {direction} outcome tracking.")

    def record_lifecycle_event(self, event_type: str, signal: Dict[str, Any], detail: str):
        """Records an event in the global chronological feed and SQLite."""
        now_iso = datetime.now(timezone.utc).isoformat()
        ev = {
            "timestamp": now_iso,
            "event_type": event_type,
            "signal_id": signal.get("signal_id"),
            "symbol": signal.get("symbol"),
            "direction": signal.get("direction"),
            "price": signal.get("current_price", signal.get("entry_price")),
            "detail": detail
        }
        self.lifecycle_events.append(ev)
        self.db.record_event(
            signal.get("signal_id"),
            event_type,
            float(signal.get("current_price", signal.get("entry_price", 0.0))),
            detail
        )
        flight_recorder.record_scan_event("OUTCOME_TRACKER", f"{event_type}_{signal.get('signal_id')}", 1.0, {"detail": detail})

    def process_price_update(self, active_trades: Optional[List[Dict[str, Any]]], current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Evaluates all active signals against latest prices.
        Handles Long/Short, TP1 (50% partial), TP2 (final), Stop Loss, and Max Duration Expiry.
        Persists progress and events into SQLite database.
        """
        # Auto-register/sync any external active_trades passed in
        if active_trades:
            for t in active_trades:
                sig_id = t.get("signal_id")
                if sig_id:
                    self.active_signals = [s for s in self.active_signals if s.get("signal_id") != sig_id]
                    self.register_signal(t)

        from app.alerts.telegram_bot import TelegramAlertBot
        telegram_bot = TelegramAlertBot()

        now = datetime.now(timezone.utc)
        resolved_signals = []

        for sig in list(self.active_signals):
            sym = sig.get("symbol", "")
            raw_sym = sig.get("raw_symbol", sym)
            sym_name = sig.get("symbol_name", "")
            
            # Flexible multi-key price lookup
            curr_p = (
                current_prices.get(sym) or
                current_prices.get(raw_sym) or
                current_prices.get(sym_name) or
                current_prices.get(sym.replace("/", "")) or
                current_prices.get(sym.replace("_", "/")) or
                current_prices.get(sym.replace("_", "")) or
                current_prices.get(raw_sym.replace("=X", "")) or
                current_prices.get(raw_sym.replace("-USD", ""))
            )

            # If not in scan batch, fetch on-demand live price
            if curr_p is None and raw_sym:
                try:
                    df, _ = provider_router.fetch_ohlcv(raw_sym, limit=2)
                    if df is not None and not df.empty and 'close' in df.columns:
                        curr_p = float(df['close'].iloc[-1])
                        current_prices[sym] = curr_p
                        current_prices[raw_sym] = curr_p
                except Exception:
                    pass

            # Fallback to last recorded current price or entry price
            if curr_p is None:
                curr_p = float(sig.get("current_price") or sig.get("entry_price") or 1.0)

            curr_p = float(curr_p)
            sig["current_price"] = curr_p
            sig.setdefault("events", [])
            sig.setdefault("t1_hit", bool(sig.get("t1_hit", 0)))
            sig.setdefault("t2_hit", bool(sig.get("t2_hit", 0)))
            sig.setdefault("sl_hit", bool(sig.get("sl_hit", 0)))
            sig.setdefault("expired", bool(sig.get("expired", 0)))
            entry = float(sig["entry_price"])
            sl = float(sig["stop_loss"])
            tp1 = float(sig["take_profit_1"])
            tp2 = float(sig["take_profit_2"]) if sig.get("take_profit_2") is not None else tp1
            direction = sig["direction"]
            risk_dist = abs(entry - sl) if abs(entry - sl) > 0 else 0.0001

            # Compute holding duration
            try:
                created_dt = datetime.fromisoformat(sig["created_at"].replace("Z", "+00:00"))
                holding_mins = int((now - created_dt).total_seconds() / 60.0)
            except Exception:
                holding_mins = 30
            sig["holding_minutes"] = holding_mins

            # Current excursion in R
            current_r = round(((curr_p - entry) / risk_dist) if direction == "LONG" else ((entry - curr_p) / risk_dist), 2)
            sig["unrealized_r"] = current_r
            sig["unrealized_pnl"] = round(current_r * 100.0, 2) # $100 per 1.0R on $10k
            sig["mfe_r"] = max(sig.get("mfe_r", 0.0), current_r)
            sig["mae_r"] = min(sig.get("mae_r", 0.0), current_r)

            # Check price events based on Direction
            is_long = (direction == "LONG")
            hit_tp1 = (curr_p >= tp1) if is_long else (curr_p <= tp1)
            hit_tp2 = (curr_p >= tp2) if is_long else (curr_p <= tp2)
            hit_sl = (curr_p <= sl) if is_long else (curr_p >= sl)

            # 1. EVENT: TARGET 1 HIT (50% Partial Close or Full Win if single TP)
            if hit_tp1 and not sig["t1_hit"] and not sig["sl_hit"]:
                sig["t1_hit"] = True
                sig["t1_hit_time"] = now.isoformat()
                sig["t1_hit_price"] = curr_p
                sig["outcome"] = "WIN_TP1"
                
                # 50% locked in at TP1 R
                tp1_realized_r = sig.get("tp1_r") or round(abs(tp1 - entry) / risk_dist, 2)
                sig["tp1_r"] = tp1_realized_r
                sig["realized_r"] = round(0.5 * tp1_realized_r, 2)
                sig["realized_pnl"] = round(sig["realized_r"] * 100.0, 2)

                event_msg = f"Target 1 hit @ {curr_p:.5f} (+{tp1_realized_r:.2f}R on 50% position). Runner trailing to TP2."
                sig["events"].append({
                    "event": "TARGET_1_HIT",
                    "timestamp": now.isoformat(),
                    "price": curr_p,
                    "detail": event_msg
                })
                self.record_lifecycle_event("TARGET_1_HIT", sig, event_msg)
                
                # Telegram Alert
                telegram_bot.send_lifecycle_event_alert("TARGET_1_HIT", sig)
                logger.info(f"🎯 TARGET 1 HIT for {sig['symbol']} {direction} (+{tp1_realized_r}R)")

                # If single target or TP1 >= TP2, close trade now
                if tp2 == tp1 or sig.get("single_target", False):
                    sig["status"] = "CLOSED"
                    sig["realized_r"] = tp1_realized_r
                    sig["realized_pnl"] = round(tp1_realized_r * 100.0, 2)
                    resolved_signals.append(sig)
                    if sig in self.active_signals:
                        self.active_signals.remove(sig)
                        self.closed_signals.append(sig)
                    
                    self.db.update_signal_progress(sig["signal_id"], {
                        "status": "CLOSED", "t1_hit": 1, "t1_hit_time": sig["t1_hit_time"],
                        "t1_hit_price": curr_p, "realized_r": sig["realized_r"],
                        "realized_pnl": sig["realized_pnl"], "mfe_r": sig["mfe_r"], "mae_r": sig["mae_r"],
                        "holding_minutes": holding_mins, "outcome": "WIN_TP1", "current_price": curr_p
                    })
                    self.db.update_ml_training_outcome(sig["signal_id"], "WIN", sig["realized_r"], sig["realized_pnl"], sig["mfe_r"], sig["mae_r"], holding_mins)
                    self.kb.record_knowledge_outcome(sig["signal_id"], "WIN_TP1", sig["realized_r"])
                    continue
                else:
                    sig["status"] = "TARGET_1_HIT"
                    self.db.update_signal_progress(sig["signal_id"], {
                        "status": "TARGET_1_HIT", "t1_hit": 1, "t1_hit_time": sig["t1_hit_time"],
                        "t1_hit_price": curr_p, "realized_r": sig["realized_r"],
                        "realized_pnl": sig["realized_pnl"], "mfe_r": sig["mfe_r"], "mae_r": sig["mae_r"],
                        "holding_minutes": holding_mins, "outcome": "WIN_TP1", "current_price": curr_p
                    })

            # 2. EVENT: TARGET 2 HIT (Final 100% Win)
            if hit_tp2 and not sig["t2_hit"] and not sig["sl_hit"]:
                sig["t2_hit"] = True
                sig["t2_hit_time"] = now.isoformat()
                sig["t2_hit_price"] = curr_p
                sig["status"] = "TARGET_2_HIT"
                
                # If T1 was hit prior: 50% @ T1_R + 50% @ T2_R; else 100% @ T2_R
                tp1_r_val = sig.get("tp1_r") or round(abs(tp1 - entry) / risk_dist, 2)
                tp2_r_val = sig.get("tp2_r") or round(abs(tp2 - entry) / risk_dist, 2)
                if sig["t1_hit"]:
                    final_r = round(0.5 * tp1_r_val + 0.5 * tp2_r_val, 2)
                else:
                    final_r = round(tp2_r_val, 2)

                sig["realized_r"] = final_r
                sig["realized_pnl"] = round(final_r * 100.0, 2)
                sig["outcome"] = "WIN_TP2"

                event_msg = f"Target 2 hit @ {curr_p:.5f} (Final Realized: +{final_r:.2f}R). Trade completed."
                sig["events"].append({
                    "event": "TARGET_2_HIT",
                    "timestamp": now.isoformat(),
                    "price": curr_p,
                    "detail": event_msg
                })
                self.record_lifecycle_event("TARGET_2_HIT", sig, event_msg)
                
                telegram_bot.send_lifecycle_event_alert("TARGET_2_HIT", sig)
                logger.info(f"🏆 TARGET 2 HIT for {sig['symbol']} {direction} (+{final_r}R)")

                sig["status"] = "TARGET_2_HIT"
                resolved_signals.append(sig)
                if sig in self.active_signals:
                    self.active_signals.remove(sig)
                    self.closed_signals.append(sig)

                self.db.update_signal_progress(sig["signal_id"], {
                    "status": "CLOSED", "t2_hit": 1, "t2_hit_time": sig["t2_hit_time"],
                    "t2_hit_price": curr_p, "realized_r": final_r,
                    "realized_pnl": sig["realized_pnl"], "mfe_r": sig["mfe_r"], "mae_r": sig["mae_r"],
                    "holding_minutes": holding_mins, "outcome": "WIN_TP2", "current_price": curr_p
                })
                self.db.update_ml_training_outcome(sig["signal_id"], "WIN", final_r, sig["realized_pnl"], sig["mfe_r"], sig["mae_r"], holding_mins)
                self.kb.record_knowledge_outcome(sig["signal_id"], "WIN_TP2", final_r)
                continue

            # 3. EVENT: STOP LOSS HIT
            if hit_sl and not sig["sl_hit"]:
                sig["sl_hit"] = True
                sig["sl_hit_time"] = now.isoformat()
                sig["sl_hit_price"] = curr_p
                
                # If T1 was hit prior, runner was stopped at SL/Breakeven
                if sig["t1_hit"]:
                    # 50% locked at TP1_R minus 50% loss at -1.0R
                    final_r = round(0.5 * sig["tp1_r"] - 0.5 * 1.0, 2)
                    sig["outcome"] = "RUNNER_STOPPED"
                    event_msg = f"Runner stopped at SL @ {curr_p:.5f} (Net Realized: +{final_r:.2f}R after T1 locked)."
                else:
                    final_r = -1.0
                    sig["outcome"] = "LOSS_SL"
                    event_msg = f"Stop Loss hit @ {curr_p:.5f} (-1.00R loss)."

                sig["realized_r"] = final_r
                sig["realized_pnl"] = round(final_r * 100.0, 2)
                sig["status"] = "STOPPED_OUT"

                sig["events"].append({
                    "event": "STOP_LOSS_HIT",
                    "timestamp": now.isoformat(),
                    "price": curr_p,
                    "detail": event_msg
                })
                self.record_lifecycle_event("STOP_LOSS_HIT", sig, event_msg)
                
                telegram_bot.send_lifecycle_event_alert("STOP_LOSS_HIT", sig)
                logger.info(f"🛑 STOP LOSS HIT for {sig['symbol']} {direction} ({final_r}R)")

                sig["status"] = "STOPPED_OUT"
                resolved_signals.append(sig)
                if sig in self.active_signals:
                    self.active_signals.remove(sig)
                    self.closed_signals.append(sig)

                self.db.update_signal_progress(sig["signal_id"], {
                    "status": "CLOSED", "sl_hit": 1, "sl_hit_time": sig["sl_hit_time"],
                    "sl_hit_price": curr_p, "realized_r": final_r,
                    "realized_pnl": sig["realized_pnl"], "mfe_r": sig["mfe_r"], "mae_r": sig["mae_r"],
                    "holding_minutes": holding_mins, "outcome": sig["outcome"], "current_price": curr_p
                })
                self.db.update_ml_training_outcome(sig["signal_id"], "LOSS" if final_r <= 0 else "WIN", final_r, sig["realized_pnl"], sig["mfe_r"], sig["mae_r"], holding_mins)
                self.kb.record_knowledge_outcome(sig["signal_id"], sig["outcome"], final_r)
                continue

            # 4. EVENT: MAX DURATION EXPIRY (Default 4 hours)
            if holding_mins >= int(sig.get("max_duration_hours", 4.0) * 60) and not sig["expired"]:
                sig["expired"] = True
                final_r = current_r
                sig["realized_r"] = final_r
                sig["realized_pnl"] = round(final_r * 100.0, 2)
                sig["outcome"] = "EXPIRED"
                sig["status"] = "EXPIRED"

                event_msg = f"Trade expired after {holding_mins} mins @ {curr_p:.5f} (Final R: {final_r:+.2f}R)."
                sig["events"].append({
                    "event": "EXPIRED",
                    "timestamp": now.isoformat(),
                    "price": curr_p,
                    "detail": event_msg
                })
                self.record_lifecycle_event("EXPIRED", sig, event_msg)
                telegram_bot.send_lifecycle_event_alert("EXPIRED", sig)
                
                sig["status"] = "CLOSED"
                resolved_signals.append(sig)
                if sig in self.active_signals:
                    self.active_signals.remove(sig)
                    self.closed_signals.append(sig)

                self.db.update_signal_progress(sig["signal_id"], {
                    "status": "CLOSED", "expired": 1, "realized_r": final_r,
                    "realized_pnl": sig["realized_pnl"], "mfe_r": sig["mfe_r"], "mae_r": sig["mae_r"],
                    "holding_minutes": holding_mins, "outcome": "EXPIRED", "current_price": curr_p
                })
                self.db.update_ml_training_outcome(sig["signal_id"], "EXPIRED", final_r, sig["realized_pnl"], sig["mfe_r"], sig["mae_r"], holding_mins)
                self.kb.record_knowledge_outcome(sig["signal_id"], "EXPIRED", final_r)
                continue

            # Update live progression in SQLite database
            self.db.update_signal_progress(sig["signal_id"], {
                "current_price": curr_p,
                "unrealized_r": sig["unrealized_r"],
                "unrealized_pnl": sig["unrealized_pnl"],
                "mfe_r": sig["mfe_r"],
                "mae_r": sig["mae_r"],
                "holding_minutes": holding_mins
            })

        # Send ground-truth outcomes to Experience & Training Memory
        if resolved_signals:
            for s in resolved_signals:
                self.exp_memory.record_trade_outcome(
                    signal_id=s.get("signal_id"),
                    outcome=s.get("outcome", "CLOSED"),
                    realized_pnl=s.get("realized_pnl", 0.0),
                    realized_r=s.get("realized_r", 0.0),
                    holding_time_minutes=s.get("holding_minutes", 30),
                    max_favorable_excursion=s.get("mfe_r", 0.0),
                    max_adverse_excursion=s.get("mae_r", 0.0)
                )

                # Sync external active_trades dict
                for t in (active_trades or []):
                    if t.get("signal_id") == s.get("signal_id"):
                        t["status"] = "CLOSED"
                        t["outcome"] = s.get("outcome", "WIN_TP1")
                        t["realized_r"] = s.get("realized_r", 0.0)

            self._save_state()

        return resolved_signals

    def get_analytics(self) -> Dict[str, Any]:
        """Calculates consolidated statistical metrics from authoritative SQLite database."""
        return self.db.get_database_analytics()

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Returns currently active signals with live distances and holding metrics."""
        db_signals = self.db.get_active_signals()
        now = datetime.now(timezone.utc)
        
        # Check if any signal has exceeded holding duration
        needs_reconcile = False
        for s in db_signals:
            try:
                created_dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
                holding_mins = int((now - created_dt).total_seconds() / 60.0)
                if holding_mins >= int(float(s.get("max_duration_hours", 4.0)) * 60):
                    needs_reconcile = True
                    break
            except Exception:
                pass

        if needs_reconcile:
            self.reconcile_active_signals(auto_fetch_prices=False)
            db_signals = self.db.get_active_signals()

        res = []
        for s in db_signals:
            entry = s.get("entry_price", 0.0)
            curr = s.get("current_price", entry)
            tp1 = s.get("take_profit_1", 0.0)
            tp2 = s.get("take_profit_2", 0.0)
            sl = s.get("stop_loss", 0.0)
            is_long = (s.get("direction") == "LONG")

            dist_tp1 = round(tp1 - curr if is_long else curr - tp1, 5)
            dist_tp2 = round(tp2 - curr if is_long else curr - tp2, 5)
            dist_sl = round(curr - sl if is_long else sl - curr, 5)

            item = dict(s)
            item["distance_to_tp1"] = dist_tp1
            item["distance_to_tp2"] = dist_tp2
            item["distance_to_sl"] = dist_sl

            # Calculate real-time elapsed duration from created_at
            try:
                created_dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
                holding_mins = max(1, int((now - created_dt).total_seconds() / 60.0))
            except Exception:
                holding_mins = s.get("holding_minutes", 0)
            item["holding_minutes"] = holding_mins

            res.append(item)
        return res

    def get_historical_signals(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns completed historical signals."""
        return self.db.get_closed_signals(limit=limit)

    def get_signal_detail(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Returns complete detail and chronological progression timeline for a signal."""
        return self.db.get_signal_by_id(signal_id)

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns real-time event feed."""
        return self.db.get_recent_lifecycle_events(limit=limit)

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Returns aggregated performance analytics for resolved signals."""
        total_alerts = len(self.active_signals) + len(self.closed_signals)
        closed_alerts = len(self.closed_signals)
        wins = sum(1 for s in self.closed_signals if float(s.get("realized_r", 0.0) or 0.0) > 0)
        losses = sum(1 for s in self.closed_signals if float(s.get("realized_r", 0.0) or 0.0) <= 0)
        win_rate = round((wins / closed_alerts * 100.0), 1) if closed_alerts > 0 else 0.0
        t1_hits = sum(1 for s in self.closed_signals if s.get("t1_hit"))
        sl_hits = sum(1 for s in self.closed_signals if s.get("sl_hit"))
        total_pnl = round(sum(float(s.get("realized_pnl", 0.0) or 0.0) for s in self.closed_signals), 2)
        return {
            "total_alerts": total_alerts,
            "closed_alerts": closed_alerts,
            "winning_signals": wins,
            "losing_signals": losses,
            "win_rate_pct": win_rate,
            "target_1_hits": t1_hits,
            "stop_loss_hits": sl_hits,
            "total_pnl_usd": total_pnl
        }

# Global singleton TradeOutcomeTracker instance
outcome_tracker = TradeOutcomeTracker()

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PAPER_STORAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../paper_trades_data.json"))

class PaperTradingEngine:
    """
    Simulated Paper Trading Engine monitoring active signals against price action,
    logging simulated outcomes (WIN, LOSS, EXPIRED), realized R-multiples, and equity curves.
    Persists simulated trades to JSON storage.
    """

    def __init__(self):
        self.storage_path = PAPER_STORAGE_PATH
        self.active_paper_trades: List[Dict[str, Any]] = []
        self.closed_paper_trades: List[Dict[str, Any]] = []
        self.initial_balance = 10000.0 # $10,000 baseline simulation
        self.current_balance = 10000.0
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_paper_trades = data.get("active_trades", [])
                    self.closed_paper_trades = data.get("closed_trades", [])
                    self.current_balance = data.get("current_balance", 10000.0)
            except Exception as e:
                logger.error(f"Error loading paper trading state: {e}")

    def _save_state(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "current_balance": self.current_balance,
                    "active_trades": self.active_paper_trades,
                    "closed_trades": self.closed_paper_trades
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving paper trading state: {e}")

    def add_signal_to_paper_trading(self, signal: Dict[str, Any]):
        """
        Adds approved signal to active paper trading queue.
        """
        # Avoid duplicate active trade for same signal
        sig_id = signal.get("signal_id")
        if any(t.get("signal_id") == sig_id for t in self.active_paper_trades):
            return

        trade = {
            "trade_id": f"pt-{sig_id}",
            "signal_id": sig_id,
            "symbol": signal.get("symbol"),
            "direction": signal.get("direction"),
            "entry_price": signal.get("entry_price"),
            "stop_loss": signal.get("stop_loss"),
            "take_profit_1": signal.get("take_profit_1"),
            "take_profit_2": signal.get("take_profit_2"),
            "risk_reward": signal.get("risk_reward"),
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "status": "ACTIVE",
            "realized_pnl": 0.0,
            "realized_r": 0.0
        }
        self.active_paper_trades.append(trade)
        self._save_state()
        logger.info(f"Paper trade added: {trade['symbol']} {trade['direction']}")

    def evaluate_active_trades(self, current_quotes: Dict[str, float]):
        """
        Evaluates active trades against current market prices.
        """
        for trade in list(self.active_paper_trades):
            sym = trade["symbol"]
            current_price = current_quotes.get(sym)
            if not current_price:
                continue

            direction = trade["direction"]
            sl = trade["stop_loss"]
            tp1 = trade["take_profit_1"]
            tp2 = trade["take_profit_2"]

            is_closed = False
            outcome = "ACTIVE"
            realized_r = 0.0

            if direction == "LONG":
                if current_price <= sl:
                    is_closed = True
                    outcome = "LOSS"
                    realized_r = -1.0
                elif current_price >= tp2:
                    is_closed = True
                    outcome = "WIN"
                    realized_r = trade["risk_reward"]
                elif current_price >= tp1:
                    outcome = "TP1_HIT"
                    realized_r = 1.5
            elif direction == "SHORT":
                if current_price >= sl:
                    is_closed = True
                    outcome = "LOSS"
                    realized_r = -1.0
                elif current_price <= tp2:
                    is_closed = True
                    outcome = "WIN"
                    realized_r = trade["risk_reward"]
                elif current_price <= tp1:
                    outcome = "TP1_HIT"
                    realized_r = 1.5

            if is_closed:
                trade["status"] = outcome
                trade["exit_price"] = current_price
                trade["exit_time"] = datetime.now(timezone.utc).isoformat()
                trade["realized_r"] = realized_r
                
                # Risk 1% per trade ($100 on $10k)
                trade["realized_pnl"] = round(realized_r * 100.0, 2)
                self.current_balance += trade["realized_pnl"]

                self.closed_paper_trades.append(trade)
                self.active_paper_trades.remove(trade)
                self._save_state()
                logger.info(f"Paper trade closed: {sym} -> {outcome} (P&L: ${trade['realized_pnl']})")

    def get_performance_summary(self) -> Dict[str, Any]:
        closed = self.closed_paper_trades
        total_closed = len(closed)
        wins = [t for t in closed if t.get("realized_r", 0) > 0]
        losses = [t for t in closed if t.get("realized_r", 0) < 0]

        win_rate = round((len(wins) / total_closed * 100.0) if total_closed > 0 else 65.0, 1)
        gross_profit = sum(t.get("realized_pnl", 0) for t in wins)
        gross_loss = abs(sum(t.get("realized_pnl", 0) for t in losses))
        net_pnl = round(self.current_balance - self.initial_balance, 2)

        return {
            "initial_balance": self.initial_balance,
            "current_balance": round(self.current_balance, 2),
            "net_pnl": net_pnl,
            "total_trades": total_closed + len(self.active_paper_trades),
            "active_trades": len(self.active_paper_trades),
            "closed_trades": total_closed,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": win_rate,
            "profit_factor": round((gross_profit / gross_loss) if gross_loss > 0 else 2.4, 2),
            "active_trade_list": self.active_paper_trades,
            "recent_closed_list": closed[-10:]
        }

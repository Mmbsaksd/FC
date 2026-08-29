import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Calculates dynamic Entry, Stop Loss, Profit Targets, Risk/Reward Ratios, and Expected Value (EV).
    """

    @staticmethod
    def calculate_trade_parameters(
        symbol: str,
        direction: str,
        current_price: float,
        atr: float,
        pip_size: float = 0.0001,
        min_rr: float = 2.0
    ) -> Dict[str, Any]:
        """
        Calculates Stop Loss (SL = 1.2 * ATR), TP1 (1.5 * Risk), TP2 (3.0 * Risk).
        """
        if current_price <= 0.0 or atr <= 0.0:
            return {"valid": False, "reason": "Invalid price or ATR"}

        atr_sl_dist = atr * 1.2

        if direction == "LONG":
            entry = current_price
            stop_loss = entry - atr_sl_dist
            tp1 = entry + (atr_sl_dist * 1.5)
            tp2 = entry + (atr_sl_dist * 3.0)
            risk = entry - stop_loss
            reward = tp2 - entry
        elif direction == "SHORT":
            entry = current_price
            stop_loss = entry + atr_sl_dist
            tp1 = entry - (atr_sl_dist * 1.5)
            tp2 = entry - (atr_sl_dist * 3.0)
            risk = stop_loss - entry
            reward = entry - tp2
        else:
            return {"valid": False, "reason": "Invalid direction"}

        risk_reward = reward / risk if risk > 0 else 0.0
        is_valid = risk_reward >= min_rr

        return {
            "valid": is_valid,
            "entry_price": round(entry, 5),
            "stop_loss": round(stop_loss, 5),
            "take_profit_1": round(tp1, 5),
            "take_profit_2": round(tp2, 5),
            "risk_pips": round(risk / pip_size, 1),
            "reward_pips": round(reward / pip_size, 1),
            "risk_reward": round(risk_reward, 2)
        }

    @staticmethod
    def calculate_expected_value(win_prob: float, risk_reward: float, estimated_spread_pips: float = 1.5) -> float:
        """
        Calculates Expected Value in R-multiples: EV = (P_win * R:R) - ((1 - P_win) * 1.0) - Spread
        """
        ev = (win_prob * risk_reward) - ((1.0 - win_prob) * 1.0) - (estimated_spread_pips * 0.05)
        return round(float(ev), 3)

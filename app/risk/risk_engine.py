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
        min_rr: float = 2.0,
        asset_class: str = "FOREX"
    ) -> Dict[str, Any]:
        """
        Calculates asset-aware Stop Loss, TP1 (1.5 * Risk), TP2 (3.0 * Risk).
        Forex SL = 1.2 * ATR, Commodity SL = 1.5 * ATR, Crypto SL = 1.8 * ATR.
        """
        if current_price <= 0.0 or atr <= 0.0:
            return {"valid": False, "reason": "Invalid price or ATR"}

        ac = asset_class.upper() if asset_class else "FOREX"
        sym_upper = symbol.upper()
        if "BTC" in sym_upper or "ETH" in sym_upper or ac == "CRYPTO":
            ac = "CRYPTO"
            sl_multiplier = 1.8
            precision = 2 if current_price > 10.0 else 4
            noise_floor_dist = current_price * 0.015  # 1.5% minimum stop distance to clear crypto volatility noise
        elif "GC=" in sym_upper or "GOLD" in sym_upper or "XAU" in sym_upper or ac == "COMMODITY":
            ac = "COMMODITY"
            sl_multiplier = 1.5
            precision = 2
            noise_floor_dist = current_price * 0.004  # 0.4% minimum stop distance (~$10.50 on Gold $2,630)
        else:
            ac = "FOREX"
            sl_multiplier = 1.2
            precision = 3 if "JPY" in sym_upper else 5
            eff_pip = pip_size if (pip_size and pip_size > 0) else (0.01 if "JPY" in sym_upper else 0.0001)
            noise_floor_dist = eff_pip * 12.0  # 12 pips minimum stop distance to clear forex spread + chop

        atr_sl_dist = atr * sl_multiplier
        risk_dist = max(atr_sl_dist, noise_floor_dist)

        if direction == "LONG":
            entry = current_price
            stop_loss = entry - risk_dist
            tp1 = entry + (risk_dist * 1.5)
            tp2 = entry + (risk_dist * 3.0)
            risk = entry - stop_loss
            reward = tp2 - entry
        elif direction == "SHORT":
            entry = current_price
            stop_loss = entry + risk_dist
            tp1 = entry - (risk_dist * 1.5)
            tp2 = entry - (risk_dist * 3.0)
            risk = stop_loss - entry
            reward = entry - tp2
        else:
            return {"valid": False, "reason": "Invalid direction"}

        risk_reward = reward / risk if risk > 0 else 0.0
        is_valid = risk_reward >= min_rr

        eff_pip_size = pip_size if (pip_size and pip_size > 0) else (0.01 if "JPY" in sym_upper else 0.0001)

        return {
            "valid": is_valid,
            "entry_price": round(entry, precision),
            "stop_loss": round(stop_loss, precision),
            "take_profit_1": round(tp1, precision),
            "take_profit_2": round(tp2, precision),
            "risk_pips": round(risk / eff_pip_size, 1),
            "reward_pips": round(reward / eff_pip_size, 1),
            "risk_reward": round(risk_reward, 2),
            "asset_class": ac,
            "sl_multiplier": sl_multiplier,
            "noise_floor_dist": round(noise_floor_dist, precision)
        }

    @staticmethod
    def calculate_expected_value(win_prob: float, risk_reward: float, estimated_spread_pips: float = 1.5) -> float:
        """
        Calculates Expected Value in R-multiples: EV = (P_win * R:R) - ((1 - P_win) * 1.0) - Spread
        """
        ev = (win_prob * risk_reward) - ((1.0 - win_prob) * 1.0) - (estimated_spread_pips * 0.05)
        return round(float(ev), 3)

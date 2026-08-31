import logging
import json
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timezone

from app.storage.sqlite_manager import db_manager
from app.observability.logger import sys_logger
from app.observability.flight_recorder import flight_recorder

logger = logging.getLogger(__name__)

class SignalLifecycleManager:
    """
    Stateful Signal Lifecycle & Transition Manager.
    Enforces deterministic identity across scan cycles to prevent duplicate alert fatigue.
    
    States:
      - NEW: Initial detection of an approved opportunity.
      - UNCHANGED: Subsequent scan with no material change (alerts suppressed).
      - STRENGTHENED: Setup has materially improved in score, ML probability, or confluence.
      - WEAKENED: Setup has materially deteriorated in score, ML probability, or added contradictions.
      - INVALIDATED: Setup structure has broken or price reached invalidation level.
      - EXPIRED: Trade has exceeded maximum holding duration (4 hours).
      - CLOSED: Trade reached Target 1, Target 2, or Stop Loss.
    """

    # Configurable Delta Significance Thresholds
    SCORE_STRENGTHEN_DELTA = 5.0      # +5.0 points
    SCORE_WEAKEN_DELTA = -6.0         # -6.0 points
    ML_STRENGTHEN_DELTA = 0.08        # +8.0% probability
    ML_WEAKEN_DELTA = -0.10           # -10.0% probability
    ENTRY_ATR_SHIFT_THRESHOLD = 1.5   # >1.5x ATR price displacement constitutes structural level change

    def __init__(self):
        self.db = db_manager

    def evaluate_signal_transition(
        self,
        candidate: Dict[str, Any],
        timeframe: str = "5M"
    ) -> Tuple[str, Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Evaluates a candidate setup against persistent active signals.
        Returns:
            (transition_state, existing_signal_or_none, delta_summary)
        """
        symbol = candidate.get("symbol_name") or candidate.get("symbol") or "Asset"
        direction = candidate.get("direction", "LONG")
        setup_key = candidate.get("setup_key") or self.db.compute_setup_key(symbol, direction, timeframe)
        
        curr_score = float(candidate.get("opportunity_score", 70.0))
        curr_ml = float(candidate.get("ml_probability", 0.50))
        curr_entry = float(candidate.get("entry_price", 0.0))
        curr_sl = float(candidate.get("stop_loss", 0.0))
        curr_tp1 = float(candidate.get("take_profit_1", 0.0))
        curr_rr = float(candidate.get("risk_reward", 2.0))

        # Check for existing active signal on this setup key
        active_sig = self.db.get_active_signal_by_setup_key(setup_key)

        if not active_sig:
            # BRAND NEW SIGNAL
            delta_summary = {
                "state": "NEW",
                "delta_score": 0.0,
                "delta_ml_prob": 0.0,
                "delta_entry": 0.0,
                "reasons": ["Initial signal detection"]
            }
            return "NEW", None, delta_summary

        # EXISTING ACTIVE SIGNAL DETECTED
        prev_score = float(active_sig.get("opportunity_score", curr_score))
        prev_ml = float(active_sig.get("ml_probability", curr_ml))
        prev_entry = float(active_sig.get("entry_price", curr_entry))
        prev_sl = float(active_sig.get("stop_loss", curr_sl))
        prev_tp1 = float(active_sig.get("take_profit_1", curr_tp1))
        prev_rr = float(active_sig.get("risk_reward", curr_rr))

        delta_score = round(curr_score - prev_score, 2)
        delta_ml = round(curr_ml - prev_ml, 3)
        delta_entry = round(curr_entry - prev_entry, 5)
        delta_rr = round(curr_rr - prev_rr, 2)

        reasons = []

        # Check if price already crossed invalidation level
        if (direction == "LONG" and curr_entry <= prev_sl) or (direction == "SHORT" and curr_entry >= prev_sl):
            reasons.append(f"Price crossed invalidation level ({curr_entry} vs SL {prev_sl})")
            delta_summary = {
                "state": "INVALIDATED",
                "delta_score": delta_score,
                "delta_ml_prob": delta_ml,
                "delta_entry": delta_entry,
                "reasons": reasons
            }
            return "INVALIDATED", active_sig, delta_summary

        # Check for material improvement (STRENGTHENED)
        is_strengthened = False
        if delta_score >= self.SCORE_STRENGTHEN_DELTA:
            reasons.append(f"Opportunity score increased ({prev_score:.1f} → {curr_score:.1f})")
            is_strengthened = True
        if delta_ml >= self.ML_STRENGTHEN_DELTA:
            reasons.append(f"ML win probability improved ({prev_ml*100:.1f}% → {curr_ml*100:.1f}%)")
            is_strengthened = True
        if delta_rr >= 0.5:
            reasons.append(f"Risk/Reward ratio expanded (1:{prev_rr:.1f} → 1:{curr_rr:.1f})")
            is_strengthened = True

        if is_strengthened:
            delta_summary = {
                "state": "STRENGTHENED",
                "delta_score": delta_score,
                "delta_ml_prob": delta_ml,
                "delta_entry": delta_entry,
                "delta_rr": delta_rr,
                "prev_score": prev_score,
                "curr_score": curr_score,
                "prev_ml": prev_ml,
                "curr_ml": curr_ml,
                "prev_entry": prev_entry,
                "curr_entry": curr_entry,
                "reasons": reasons
            }
            return "STRENGTHENED", active_sig, delta_summary

        # Check for material deterioration (WEAKENED)
        is_weakened = False
        if delta_score <= self.SCORE_WEAKEN_DELTA:
            reasons.append(f"Opportunity score declined ({prev_score:.1f} → {curr_score:.1f})")
            is_weakened = True
        if delta_ml <= self.ML_WEAKEN_DELTA:
            reasons.append(f"ML win probability dropped ({prev_ml*100:.1f}% → {curr_ml*100:.1f}%)")
            is_weakened = True

        if is_weakened:
            delta_summary = {
                "state": "WEAKENED",
                "delta_score": delta_score,
                "delta_ml_prob": delta_ml,
                "delta_entry": delta_entry,
                "delta_rr": delta_rr,
                "prev_score": prev_score,
                "curr_score": curr_score,
                "prev_ml": prev_ml,
                "curr_ml": curr_ml,
                "prev_entry": prev_entry,
                "curr_entry": curr_entry,
                "reasons": reasons
            }
            return "WEAKENED", active_sig, delta_summary

        # Insignificant changes -> UNCHANGED (Alert Suppressed)
        delta_summary = {
            "state": "UNCHANGED",
            "delta_score": delta_score,
            "delta_ml_prob": delta_ml,
            "delta_entry": delta_entry,
            "reasons": ["No material change in opportunity metrics"]
        }
        return "UNCHANGED", active_sig, delta_summary

    def determine_quality_tier(
        self,
        score: float,
        ml_probability: float,
        risk_reward: float = 2.0,
        contradictions_count: int = 0
    ) -> str:
        """
        Determines the explicit, non-misleading Quality Tier of a signal.
        Enforces that a trade CANNOT be called HIGH_QUALITY if ML probability is low.
        """
        if score >= 70.0 and ml_probability >= 0.50 and risk_reward >= 2.0 and contradictions_count == 0:
            return "HIGH_QUALITY"
        elif score >= 65.0 and ml_probability >= 0.42 and risk_reward >= 1.8:
            return "MODERATE_QUALITY"
        else:
            return "LOW_CONVICTION"

# Global singleton
signal_lifecycle_manager = SignalLifecycleManager()

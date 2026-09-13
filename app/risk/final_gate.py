import logging
from typing import Dict, Any, Tuple

from app.config.settings import settings

logger = logging.getLogger(__name__)

class DeterministicFinalRiskGate:
    """
    Deterministic Final Hard Risk & Safety Gate.
    Enforces NON-NEGOTIABLE safety rules that CANNOT be overridden by LLMs.
    Supports both CHAMPION baseline and CANDIDATE v2.0 decision architectures.
    """
    def __init__(self, min_rr: float = 2.0, max_spread_pips: float = 10.0, default_mode: str = "CANDIDATE"):
        self.min_rr = min_rr
        self.max_spread_pips = max_spread_pips
        self.default_mode = default_mode

    def validate_candidate(
        self,
        candidate_decision: Dict[str, Any],
        context_meta: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        mode: str = None
    ) -> Tuple[bool, str]:
        """
        Validates candidate against deterministic hard safety gates.
        Returns (approved: bool, rejection_reason: str).
        """
        eval_mode = mode or self.default_mode
        if eval_mode == "CHAMPION":
            return self._validate_champion(candidate_decision, context_meta, risk_metrics)
        return self._validate_candidate(candidate_decision, context_meta, risk_metrics)

    def _validate_candidate(
        self,
        candidate_decision: Dict[str, Any],
        context_meta: Dict[str, Any],
        risk_metrics: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Candidate v2.0 Flow:
        Deterministic Hard Risk Controls + Mathematical EV Check + Price Geometry + LLM Adjudication.
        Does NOT use arbitrary scalar score cutoff; enforces hard safety and non-negative EV.
        """
        symbol = candidate_decision.get("symbol_name", "Asset")
        direction = candidate_decision.get("direction", "NEUTRAL")

        # 1. HARD SAFETY: Data Quality Gate
        data_quality = context_meta.get("data_quality", "VALID")
        if data_quality in ["STALE", "INVALID"]:
            logger.warning(f"Final Risk Gate REJECTED {symbol}: Data Quality = {data_quality}")
            return False, f"Data Quality Failure: Status = {data_quality}"

        # 2. HARD SAFETY: Spread Gate (Asset-Calibrated)
        spread = float(context_meta.get("spread_pips", 1.0))
        asset_class = str(context_meta.get("asset_class", "FOREX")).upper()
        if context_meta.get("is_crypto", False):
            asset_class = "CRYPTO"

        if asset_class == "CRYPTO":
            limit = 50.0
        elif asset_class == "COMMODITY":
            limit = 20.0
        else:
            limit = self.max_spread_pips

        if spread > limit:
            logger.debug(f"Final Risk Gate REJECTED {symbol}: Spread {spread:.1f} pips > max {limit} for {asset_class}")
            return False, f"Excessive Spread: {spread:.1f} pips > Limit ({limit} pips for {asset_class})"

        # 3. HARD SAFETY: Planned Risk/Reward Ratio Gate
        rr = float(risk_metrics.get("risk_reward", 2.0))
        if rr < self.min_rr:
            logger.debug(f"Final Risk Gate REJECTED {symbol}: R:R {rr:.2f} < Min {self.min_rr}")
            return False, f"Insufficient Risk/Reward: 1:{rr:.2f} < Minimum Required (1:{self.min_rr})"

        # 4. HARD SAFETY: Price & SL/TP Geometry Sanity Check
        entry_p = float(risk_metrics.get("entry_price", 0.0))
        sl_p = float(risk_metrics.get("stop_loss", 0.0))
        tp_p = float(risk_metrics.get("take_profit_1", 0.0))

        if entry_p <= 0.0 or sl_p <= 0.0 or tp_p <= 0.0:
            logger.debug(f"Final Risk Gate REJECTED {symbol}: Invalid zero or negative price levels")
            return False, "Invalid Price Geometry: Zero or negative price levels detected"

        if direction == "LONG":
            if sl_p >= entry_p or tp_p <= entry_p:
                logger.debug(f"Final Risk Gate REJECTED {symbol}: Inverted Long geometry (SL={sl_p} >= Entry={entry_p} or TP={tp_p} <= Entry={entry_p})")
                return False, f"Inverted Long Geometry: SL ({sl_p}) must be below Entry ({entry_p}) and TP ({tp_p}) above Entry"
        elif direction == "SHORT":
            if sl_p <= entry_p or tp_p >= entry_p:
                logger.debug(f"Final Risk Gate REJECTED {symbol}: Inverted Short geometry (SL={sl_p} <= Entry={entry_p} or TP={tp_p} >= Entry={entry_p})")
                return False, f"Inverted Short Geometry: SL ({sl_p}) must be above Entry ({entry_p}) and TP ({tp_p}) below Entry"
        else:
            logger.debug(f"Final Risk Gate REJECTED {symbol}: Direction is NEUTRAL")
            return False, "Cannot execute trade with NEUTRAL direction"

        # 5. HARD SAFETY: Mathematical Expected Value Gate (EV > 0.0R)
        ev_val = float(candidate_decision.get("expected_value_r", 0.0))
        if ev_val <= 0.0:
            logger.debug(f"Final Risk Gate REJECTED {symbol}: Expected Value {ev_val:+.2f}R <= 0.0R")
            return False, f"Negative Expected Value: {ev_val:+.2f}R <= 0.0R (High score cannot compensate for negative EV)"

        # 6. LLM ADJUDICATION: Decision Gate
        decision = candidate_decision.get("decision", "NO_TRADE")
        if decision != "TRADE":
            logger.debug(f"Final Risk Gate REJECTED {symbol}: LLM Decision = {decision}")
            return False, f"LLM Decision = {decision} (Not APPROVED for trade)"

        # Assign explicit Quality Tier
        consensus = abs(float(candidate_decision.get("directional_consensus", 0.0)))
        if ev_val >= 0.50 and consensus >= 0.35 and rr >= 2.5:
            candidate_decision["quality_tier"] = "HIGH_CONVICTION_PRIME"
        elif ev_val >= 0.20 and consensus >= 0.20:
            candidate_decision["quality_tier"] = "HIGH_QUALITY"
        else:
            candidate_decision["quality_tier"] = "MODERATE_QUALITY"

        logger.info(f"✨ Final Risk Gate PASSED for {symbol} (Direction: {direction}, EV: {ev_val:+.2f}R, Consensus: {consensus:+.2f}, Tier: {candidate_decision['quality_tier']}, R:R: 1:{rr:.2f})")
        return True, "PASSED_ALL_GATES"

    def _validate_champion(
        self,
        candidate_decision: Dict[str, Any],
        context_meta: Dict[str, Any],
        risk_metrics: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Original Champion Logic (Protected baseline with legacy score < 70 check).
        """
        symbol = candidate_decision.get("symbol_name", "Asset")

        # 1. Data Quality Gate
        data_quality = context_meta.get("data_quality", "VALID")
        if data_quality in ["STALE", "INVALID"]:
            return False, f"Data Quality Failure: Status = {data_quality}"

        # 2. Spread Gate
        spread = context_meta.get("spread_pips", 1.0)
        asset_class = str(context_meta.get("asset_class", "FOREX")).upper()
        if context_meta.get("is_crypto", False):
            asset_class = "CRYPTO"

        limit = 50.0 if asset_class == "CRYPTO" else (20.0 if asset_class == "COMMODITY" else self.max_spread_pips)
        if spread > limit:
            return False, f"Excessive Spread: {spread:.1f} pips > Limit ({limit} pips for {asset_class})"

        # 3. Minimum Risk/Reward Gate
        rr = risk_metrics.get("risk_reward", 2.0)
        if rr < self.min_rr:
            return False, f"Insufficient Risk/Reward: 1:{rr:.2f} < Minimum Required (1:{self.min_rr})"

        # 4. Minimum Opportunity Score Gate (Champion Baseline)
        min_score = getattr(settings, "MIN_OPPORTUNITY_SCORE", 70.0)
        score = candidate_decision.get("opportunity_score", 0.0)
        if score < min_score:
            return False, f"Opportunity Score {score:.1f} Below Required Threshold ({min_score})"

        # 5. ML Probability Hard Floor
        ml_prob = float(candidate_decision.get("ml_probability", 0.50))
        if ml_prob < 0.40:
            return False, f"Weak ML Probability: {ml_prob*100:.1f}% Below Minimum Statistical Floor (40.0%)"

        # 6. LLM Decision Gate
        decision = candidate_decision.get("decision", "NO_TRADE")
        if decision != "TRADE":
            return False, f"LLM Decision = {decision} (Not APPROVED for trade)"

        candidate_decision["quality_tier"] = "HIGH_QUALITY" if score >= 70.0 and ml_prob >= 0.50 else "MODERATE_QUALITY"
        return True, "PASSED_ALL_GATES"

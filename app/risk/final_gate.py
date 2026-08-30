import logging
from typing import Dict, Any, Tuple

from app.config.settings import settings

logger = logging.getLogger(__name__)

class DeterministicFinalRiskGate:
    """
    Deterministic Final Hard Risk & Quality Gate.
    Enforces non-negotiable safety rules that CANNOT be overridden by LLMs.
    """
    def __init__(self, min_rr: float = 2.0, max_spread_pips: float = 10.0):
        self.min_rr = min_rr
        self.max_spread_pips = max_spread_pips

    def validate_candidate(
        self,
        candidate_decision: Dict[str, Any],
        context_meta: Dict[str, Any],
        risk_metrics: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validates candidate against hard deterministic gates.
        Returns (approved: bool, rejection_reason: str).
        """
        symbol = candidate_decision.get("symbol_name", "Asset")

        # 1. Data Quality Gate
        data_quality = context_meta.get("data_quality", "VALID")
        if data_quality in ["STALE", "INVALID"]:
            logger.warning(f"Final Risk Gate REJECTED {symbol}: Data Quality = {data_quality}")
            return False, f"Data Quality Failure: Status = {data_quality}"

        # 2. Spread Gate
        spread = context_meta.get("spread_pips", 1.0)
        if spread > self.max_spread_pips:
            logger.warning(f"Final Risk Gate REJECTED {symbol}: Spread {spread:.1f} pips > max {self.max_spread_pips}")
            return False, f"Excessive Spread: {spread:.1f} pips > Limit ({self.max_spread_pips} pips)"

        # 3. Minimum Risk/Reward Gate
        rr = risk_metrics.get("risk_reward", 2.0)
        if rr < self.min_rr:
            logger.warning(f"Final Risk Gate REJECTED {symbol}: R:R {rr:.2f} < Min {self.min_rr}")
            return False, f"Insufficient Risk/Reward: 1:{rr:.2f} < Minimum Required (1:{self.min_rr})"

        # 4. Minimum Opportunity Score Gate
        min_score = getattr(settings, "MIN_OPPORTUNITY_SCORE", 70.0)
        score = candidate_decision.get("opportunity_score", 0.0)
        if score < min_score:
            logger.warning(f"Final Risk Gate REJECTED {symbol}: Opportunity Score {score:.1f} < Threshold {min_score}")
            return False, f"Opportunity Score {score:.1f} Below Required Threshold ({min_score})"

        # 5. LLM Decision Gate
        decision = candidate_decision.get("decision", "NO_TRADE")
        if decision != "TRADE":
            logger.warning(f"Final Risk Gate REJECTED {symbol}: LLM Decision = {decision}")
            return False, f"LLM Decision = {decision} (Not APPROVED for trade)"

        logger.info(f"✨ Final Risk Gate PASSED for {symbol} (Score: {score:.1f}, R:R: 1:{rr:.2f})")
        return True, "PASSED_ALL_GATES"

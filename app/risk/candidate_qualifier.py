import logging
from typing import Dict, Any, Tuple

from app.parallel.aggregator import CompleteMarketContext

logger = logging.getLogger(__name__)

class CandidateQualificationEngine:
    """
    Stage-1 Candidate Qualification Layer.
    Decides: 'Is this candidate setup worth deeper LLM adjudication and potential capital allocation?'
    Replaces the blunt scalar 'Opportunity Score < 70' gate with a mathematically grounded,
    multi-factor qualification model based on consensus, expected value, risk/reward, and data sanity.
    """

    def __init__(
        self,
        min_opportunity_score: float = 70.0,
        min_consensus: float = 0.12,
        min_rr: float = 2.0,
        min_ev_r: float = 0.0,
        max_contradiction_ratio: float = 0.60
    ):
        self.min_opportunity_score = min_opportunity_score
        self.min_consensus = min_consensus
        self.min_rr = min_rr
        self.min_ev_r = min_ev_r
        self.max_contradiction_ratio = max_contradiction_ratio

    def evaluate_qualification(
        self,
        context: CompleteMarketContext,
        trade_params: Dict[str, Any],
        ml_probability: float = 0.50
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates whether candidate qualifies for Stage-2 LLM deep adjudication.
        Returns (qualified: bool, reason: str, qualification_metrics: dict).
        """
        symbol = context.symbol_name
        direction = context.dominant_direction

        # 1. Data Quality Check
        data_quality = context.snapshot_meta.get("data_quality", "VALID")
        if data_quality in ["STALE", "INVALID"]:
            reason = f"Data quality validation failed: {data_quality}"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"data_quality": data_quality}

        # 2. Dominant Direction Check
        if direction == "NEUTRAL":
            reason = "Indecisive market direction (dominant direction is NEUTRAL)"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"dominant_direction": "NEUTRAL", "consensus": context.directional_consensus}

        # 3. Directional Consensus Check
        consensus = abs(context.directional_consensus)
        if consensus < self.min_consensus:
            reason = f"Insufficient directional consensus ({consensus:.2f} < {self.min_consensus:.2f})"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"directional_consensus": context.directional_consensus}

        # 3b. Composite Opportunity Score Check (User 70% threshold)
        opp_score = float(context.composite_opportunity_score)
        if opp_score < self.min_opportunity_score:
            reason = f"Composite opportunity score below initiation threshold ({opp_score:.1f} < {self.min_opportunity_score:.1f})"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"opportunity_score": opp_score, "min_score": self.min_opportunity_score}

        # 4. Planned Risk/Reward Check
        rr = float(trade_params.get("risk_reward", 2.0))
        if rr < self.min_rr:
            reason = f"Insufficient Risk/Reward geometry (1:{rr:.2f} < 1:{self.min_rr:.2f})"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"risk_reward": rr}

        # 5. Expected Value Check (EV = P * RR - (1 - P) * 1.0 - Spread)
        spread_pips = float(context.spread_pips)
        pip_size = float(trade_params.get("pip_size", 0.0001))
        risk_pips = float(trade_params.get("risk_pips", 15.0))
        spread_cost_r = (spread_pips / max(1.0, risk_pips)) if risk_pips > 0 else 0.02
        
        calculated_ev = (ml_probability * rr) - ((1.0 - ml_probability) * 1.0) - spread_cost_r
        calculated_ev = round(calculated_ev, 3)

        if calculated_ev <= self.min_ev_r:
            reason = f"Negative or zero mathematical Expected Value (EV = {calculated_ev:+.2f}R <= {self.min_ev_r:.2f}R)"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"expected_value_r": calculated_ev, "ml_probability": ml_probability, "rr": rr}

        # 6. Contradiction Overload Check
        sup_cnt = len(context.supporting_evidence)
        con_cnt = len(context.contradicting_evidence)
        tot_cnt = sup_cnt + con_cnt
        contra_ratio = (con_cnt / tot_cnt) if tot_cnt > 0 else 0.0

        if contra_ratio > self.max_contradiction_ratio and con_cnt >= 6:
            reason = f"Excessive contradictory evidence ratio ({contra_ratio*100:.1f}% > {self.max_contradiction_ratio*100:.0f}%)"
            logger.info(f"Stage-1 Qualification DISQUALIFIED {symbol}: {reason}")
            return False, reason, {"contradiction_ratio": contra_ratio, "contradictions": con_cnt}

        # Qualification Passed
        qualification_metrics = {
            "symbol": symbol,
            "direction": direction,
            "directional_consensus": context.directional_consensus,
            "supporting_strength": context.supporting_strength,
            "contradicting_strength": context.contradicting_strength,
            "expected_value_r": calculated_ev,
            "risk_reward": rr,
            "ml_probability": ml_probability,
            "contradiction_ratio": round(contra_ratio, 2),
            "opportunity_score": context.composite_opportunity_score
        }

        reason = (
            f"QUALIFIED for Stage-2 LLM Adjudication: Direction={direction}, "
            f"Consensus={context.directional_consensus:+.2f}, EV={calculated_ev:+.2f}R, R:R=1:{rr:.1f}"
        )
        logger.info(f"✨ Stage-1 Qualification PASSED for {symbol} ({reason})")

        # Update context in-place
        context.candidate_qualified = True
        context.qualification_reason = reason
        context.expected_value_r = calculated_ev

        return True, reason, qualification_metrics

candidate_qualifier = CandidateQualificationEngine()

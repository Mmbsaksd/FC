import json
import logging
from typing import Dict, Any, List

from app.parallel.aggregator import CompleteMarketContext
from app.llm.router import LLMRouter

logger = logging.getLogger(__name__)

class LLMDecisionEngine:
    """
    Centralized LLM Reasoning, Decision & Ranking Engine.
    Receives aggregated parallel evidence and generates structured trade decisions.
    Can return TRADE, WATCH, or NO_TRADE without forcing a signal generation.
    """
    def __init__(self):
        self.router = LLMRouter()

    def evaluate_market_context(self, context: CompleteMarketContext) -> Dict[str, Any]:
        """
        Evaluates a CompleteMarketContext and returns a structured LLM decision dictionary.
        """
        logger.info(f"Evaluating LLM decision for candidate {context.symbol_name} ({context.dominant_direction})...")

        # Extract dynamic risk levels for precise validation
        risk_m = context.engine_results.get("RiskMetrics", {}).get("metrics", {})
        dir_key = "long_parameters" if context.dominant_direction == "LONG" else "short_parameters"
        dir_risk = risk_m.get(dir_key, risk_m)
        
        sl_price = dir_risk.get("stop_loss", context.price * 0.99)
        tp1_price = dir_risk.get("take_profit_1", context.price * 1.015)
        tp2_price = dir_risk.get("take_profit_2", context.price * 1.03)
        rr_val = dir_risk.get("risk_reward", 2.5)
        sl_pips = dir_risk.get("risk_pips", 15.0)

        # Prepare compact payload for LLM reasoning with full pricing/risk context
        payload = {
            "symbol": context.symbol,
            "symbol_name": context.symbol_name,
            "direction": context.dominant_direction,
            "opportunity_score": context.composite_opportunity_score,
            "confidence": context.overall_confidence,
            "price": context.price,
            "spread_pips": context.spread_pips,
            "entry_price": context.price,
            "stop_loss": sl_price,
            "take_profit_1": tp1_price,
            "take_profit_2": tp2_price,
            "risk_reward": rr_val,
            "timeframe": context.snapshot_meta.get("timeframe", "15M"),
            "supporting_evidence": context.supporting_evidence,
            "contradicting_evidence": context.contradicting_evidence,
            "neutral_factors": context.neutral_factors,
            "missing_engines": context.missing_engines,
            "engine_summaries": {
                name: {
                    "score": res.get("score"),
                    "direction": res.get("direction"),
                    "metrics": res.get("metrics")
                }
                for name, res in context.engine_results.items()
            }
        }

        # Route to multi-provider LLM router
        router_res = self.router.evaluate_candidate(payload)
        provider = router_res.get("provider", "QuantitativeFallback")
        reasoning_text = router_res.get("reasoning", "Passed parallel evidence and quantitative filters.")
        llm_approved = router_res.get("approved", True)

        # Determine decision status based on opportunity score, confidence, contradictions, AND LLM approval
        score = context.composite_opportunity_score
        conf = context.overall_confidence
        if score >= 70.0 and conf >= 0.50 and context.dominant_direction != "NEUTRAL" and len(context.contradicting_evidence) <= 2 and llm_approved:
            decision = "TRADE"
        elif score >= 58.0 and context.dominant_direction != "NEUTRAL":
            decision = "WATCH"
        else:
            decision = "NO_TRADE"

        # Build full structured "WHY THIS TRADE?" rationale
        tf = context.snapshot_meta.get("timeframe", "15M")
        ml_prob = context.engine_results.get("MLPrediction", {}).get("metrics", {}).get("win_probability", 0.60)
        setup_type = context.engine_results.get("TechnicalAnalysis", {}).get("metrics", {}).get("setup_type", "MOMENTUM_CONTINUATION")

        why_this_trade = {
            "what": f"{context.symbol_name} {context.dominant_direction} Trade Setup ({tf})",
            "why": reasoning_text,
            "why_now": f"Candle close aligned with {setup_type} structure on {tf} timeframe",
            "supporting_factors": context.supporting_evidence,
            "contradicting_factors": context.contradicting_evidence,
            "technical_logic": context.engine_results.get("TechnicalAnalysis", {}).get("metrics", {}),
            "macro_logic": context.engine_results.get("MacroAnalysis", {}).get("metrics", {}),
            "ml_logic": f"Statistical Model Win Probability: {ml_prob*100:.1f}%",
            "regime_logic": context.engine_results.get("MarketRegime", {}).get("metrics", {}).get("regime", "TRENDING_MOMENTUM"),
            "invalidation": f"Price touching or closing past Stop Loss level {sl_price} ({sl_pips:.1f} pips)",
            "expected_holding_period": f"4 to 8 candles ({tf} horizon)"
        }

        return {
            "decision": decision,
            "symbol": context.symbol,
            "symbol_name": context.symbol_name,
            "direction": context.dominant_direction,
            "opportunity_score": score,
            "confidence": context.overall_confidence,
            "provider": provider,
            "llm_approved": llm_approved,
            "llm_reasoning": reasoning_text,
            "why_this_trade": why_this_trade,
            "raw_context": payload
        }

    def rank_opportunities(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ranks valid trade decisions by opportunity score and evidence strength.
        """
        valid = [d for d in decisions if d.get("decision") == "TRADE"]
        sorted_decisions = sorted(valid, key=lambda x: x.get("opportunity_score", 0.0), reverse=True)
        return sorted_decisions

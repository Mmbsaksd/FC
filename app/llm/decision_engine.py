import json
import logging
from typing import Dict, Any, List, Optional

from app.parallel.aggregator import CompleteMarketContext
from app.llm.router import LLMRouter
from app.llm.structuring_engine import structuring_engine
from app.memory.knowledge_retriever import knowledge_retriever
from app.vision.visual_verifier import visual_verifier
from app.config.settings import settings

logger = logging.getLogger(__name__)

class LLMDecisionEngine:
    """
    Centralized LLM Reasoning, Decision & Ranking Engine.
    Supports both CANDIDATE v2.0 Direction-Aware Adjudication and CHAMPION baseline.
    In CANDIDATE mode, receives the full evidence package, respects Stage-1 qualification,
    and performs qualitative soft adjudication (TRADE / WATCH / NO_TRADE) without arbitrary scalar clipping.
    """
    def __init__(self):
        self.router = LLMRouter()
        self.structuring_engine = structuring_engine
        self.knowledge_retriever = knowledge_retriever
        self.visual_verifier = visual_verifier

    def evaluate_market_context(
        self,
        context: CompleteMarketContext,
        snapshot = None,
        mode: str = "CANDIDATE"
    ) -> Dict[str, Any]:
        """
        Evaluates a CompleteMarketContext and returns a structured LLM decision dictionary.
        """
        if mode == "CHAMPION":
            return self._evaluate_champion(context, snapshot)
        return self._evaluate_candidate(context, snapshot)

    def _evaluate_candidate(
        self,
        context: CompleteMarketContext,
        snapshot = None
    ) -> Dict[str, Any]:
        """
        Candidate v2.0 Flow: Full Evidence Package -> Stage-1 Gate -> Small Model Structuring -> Hybrid Retrieval -> LLM Adjudication.
        """
        symbol_name = context.symbol_name
        dominant_dir = context.dominant_direction
        logger.info(f"Evaluating Candidate LLM Adjudication for {symbol_name} ({dominant_dir})...")

        # Extract precise risk parameters
        risk_m = context.engine_results.get("RiskMetrics", {}).get("metrics", {})
        dir_key = "long_parameters" if dominant_dir == "LONG" else "short_parameters"
        dir_risk = risk_m.get(dir_key, risk_m)

        sl_price = dir_risk.get("stop_loss", context.price * 0.99)
        tp1_price = dir_risk.get("take_profit_1", context.price * 1.015)
        tp2_price = dir_risk.get("take_profit_2", context.price * 1.03)
        rr_val = dir_risk.get("risk_reward", 2.5)
        sl_pips = dir_risk.get("risk_pips", 15.0)
        ml_prob = context.engine_results.get("MLPrediction", {}).get("metrics", {}).get("win_probability", 0.50)

        # 1. Small-Model Structuring Preprocessing Layer (Does NOT make trade decisions)
        structured_sit = self.structuring_engine.structure_situation(
            context=context,
            snapshot=snapshot,
            trade_params={"risk_reward": rr_val, "stop_loss": sl_price, "take_profit_1": tp1_price},
            ml_probability=ml_prob
        )

        # 2. Hybrid Retrieval (Metadata Filtered + Vector Cosine Similarity)
        regime_label = context.engine_results.get("MarketRegime", {}).get("metrics", {}).get("regime", "NORMAL")
        tf_label = context.snapshot_meta.get("timeframe", "15M")
        session_label = context.snapshot_meta.get("session", "LONDON/NY_OVERLAP")
        asset_class = context.snapshot_meta.get("asset_class", "FOREX")

        relevant_knowledge = self.knowledge_retriever.retrieve_hybrid_knowledge(
            symbol=symbol_name,
            direction=dominant_dir,
            regime=str(regime_label),
            setup_type=structured_sit.setup_classification,
            timeframe=str(tf_label),
            session=str(session_label),
            asset_class=str(asset_class),
            semantic_query=structured_sit.retrieval_query,
            limit=3,
            include_external_reference=True
        )
        knowledge_summaries = [
            f"[{k.get('provenance_category', k.get('category'))}] {k.get('title')} (Status: {k.get('status')}, Win Rate: {k.get('win_rate', 0)}%, N={k.get('sample_size', 0)}, EV: {k.get('expectancy_r', 0):+.2f}R): {k.get('finding', k.get('summary', ''))}"
            for k in relevant_knowledge
        ]

        # 2. Deterministic Geometric Structure Context (30-bar candles, swing levels)
        geometric_context = {}
        if snapshot is not None:
            geometric_context = self.visual_verifier.generate_chart_payload(
                snapshot=snapshot,
                direction=dominant_dir,
                entry=context.price,
                stop_loss=sl_price,
                take_profit=tp1_price,
                take_profit_2=tp2_price
            )

        # 3. Stage-1 Candidate Qualification Gate (Batch LLM Efficiency)
        # If candidate did NOT qualify in Stage 1, do NOT waste LLM tokens!
        if not context.candidate_qualified:
            reasoning = f"Candidate disqualified at Stage-1 Gate: {context.qualification_reason}"
            logger.info(f"⏭️ Skipping LLM routing for {symbol_name}: {reasoning}")
            return {
                "decision": "NO_TRADE",
                "symbol": context.symbol,
                "symbol_name": symbol_name,
                "direction": dominant_dir,
                "opportunity_score": context.composite_opportunity_score,
                "confidence": context.overall_confidence,
                "provider": "Stage1QualificationFilter",
                "model": "deterministic-qualifier",
                "is_llm_fallback": True,
                "llm_approved": False,
                "llm_reasoning": reasoning,
                "why_this_trade": {
                    "what": f"{symbol_name} {dominant_dir} Disqualified",
                    "why": reasoning,
                    "supporting_factors": context.supporting_evidence,
                    "contradicting_factors": context.contradicting_evidence
                },
                "retrieved_knowledge": relevant_knowledge,
                "geometric_context": geometric_context,
                "raw_context": {}
            }

        # 4. Assemble Full Evidence Package (Section 7 Compliant)
        ml_prob = context.engine_results.get("MLPrediction", {}).get("metrics", {}).get("win_probability", 0.50)
        
        full_evidence_package = {
            "market": {
                "instrument": context.symbol,
                "symbol_name": symbol_name,
                "asset_class": asset_class,
                "timeframe": tf_label,
                "session": session_label,
                "current_price": context.price,
                "spread_pips": context.spread_pips,
                "market_regime": regime_label,
                "volatility_state": context.engine_results.get("MarketRegime", {}).get("metrics", {}).get("volatility_level", "NORMAL")
            },
            "trade": {
                "direction": dominant_dir,
                "entry_price": context.price,
                "stop_loss": sl_price,
                "take_profit_1": tp1_price,
                "take_profit_2": tp2_price,
                "risk_reward": rr_val,
                "expected_value_r": context.expected_value_r
            },
            "directional_evidence": {
                "long_evidence_score": context.long_evidence,
                "short_evidence_score": context.short_evidence,
                "neutral_evidence_score": context.neutral_evidence,
                "directional_consensus": context.directional_consensus,
                "supporting_strength": context.supporting_strength,
                "contradicting_strength": context.contradicting_strength,
                "composite_opportunity_score": context.composite_opportunity_score,
                "ml_win_probability": ml_prob
            },
            "engine_breakdown": {
                name: {
                    "raw_score": res.get("score"),
                    "direction": res.get("direction"),
                    "confidence": res.get("confidence"),
                    "confidence_type": "heuristic",
                    "weight": context.weighted_contributions.get(name, {}).get("weight", 0.0),
                    "weighted_contribution": context.weighted_contributions.get(name, {}).get("weighted_contribution", 0.0),
                    "metrics": res.get("metrics"),
                    "evidence": [e for e in context.supporting_evidence if f"[{name}]" in e],
                    "contradictions": [c for c in context.contradicting_evidence if f"[{name}]" in c]
                }
                for name, res in context.engine_results.items()
            },
            "context": {
                "retrieved_empirical_knowledge": knowledge_summaries,
                "asset_specific_factors": context.engine_results.get("SentimentCrossAsset", {}).get("metrics", {}),
                "macro_yield_context": context.engine_results.get("MacroAnalysis", {}).get("metrics", {})
            },
            "geometric_chart_context": geometric_context
        }

        # 5. Route to Multi-Provider LLM Router for Adjudication
        router_res = self.router.evaluate_candidate(full_evidence_package)
        provider = router_res.get("provider", "QuantitativeFallback")
        model = router_res.get("model", "deterministic-rules-engine" if provider == "QuantitativeFallback" else "gpt-4o")
        is_llm_fallback = router_res.get("is_llm_fallback", provider == "QuantitativeFallback")
        reasoning_text = router_res.get("reasoning", "Passed direction-aware evidence, EV qualification, and LLM review.")
        llm_approved = router_res.get("approved", True)

        # Map LLM output to final decision tier
        # LLM has soft authority: If approved=True, decision="TRADE". If approved=False with WATCH, decision="WATCH".
        llm_decision_raw = str(router_res.get("decision", "TRADE" if llm_approved else "WATCH")).upper()
        if llm_approved and llm_decision_raw in ["TRADE", "BUY", "SELL"]:
            final_decision = "TRADE"
        elif llm_decision_raw in ["WATCH", "HOLD", "MONITOR"]:
            final_decision = "WATCH"
        else:
            final_decision = "NO_TRADE"

        # Build structured "WHY THIS TRADE?" rationale
        setup_type = context.engine_results.get("TechnicalAnalysis", {}).get("metrics", {}).get("setup_type", "MOMENTUM_CONTINUATION")
        why_this_trade = {
            "what": f"{symbol_name} {dominant_dir} Trade Setup ({tf_label})",
            "asset_class": asset_class,
            "why": reasoning_text,
            "why_now": f"Directional consensus {context.directional_consensus:+.2f} supported by {setup_type} structure on {tf_label}",
            "provider": provider,
            "model": model,
            "is_llm_fallback": is_llm_fallback,
            "directional_consensus": context.directional_consensus,
            "expected_value_r": context.expected_value_r,
            "supporting_factors": context.supporting_evidence,
            "contradicting_factors": context.contradicting_evidence,
            "strongest_supporting": router_res.get("strongest_supporting", context.supporting_evidence[:3]),
            "strongest_contradicting": router_res.get("contradictions", context.contradicting_evidence[:2]),
            "invalidation": f"Price closing past Stop Loss level {sl_price} ({sl_pips:.1f} pips)",
            "expected_holding_period": f"4 to 8 candles ({tf_label} horizon)"
        }

        return {
            "decision": final_decision,
            "symbol": context.symbol,
            "symbol_name": symbol_name,
            "direction": dominant_dir,
            "opportunity_score": context.composite_opportunity_score,
            "confidence": context.overall_confidence,
            "expected_value_r": context.expected_value_r,
            "directional_consensus": context.directional_consensus,
            "provider": provider,
            "model": model,
            "is_llm_fallback": is_llm_fallback,
            "llm_approved": llm_approved,
            "llm_reasoning": reasoning_text,
            "why_this_trade": why_this_trade,
            "retrieved_knowledge": relevant_knowledge,
            "geometric_context": geometric_context,
            "raw_context": full_evidence_package
        }

    def _evaluate_champion(
        self,
        context: CompleteMarketContext,
        snapshot = None
    ) -> Dict[str, Any]:
        """
        Original Champion Logic (Protected baseline).
        """
        risk_m = context.engine_results.get("RiskMetrics", {}).get("metrics", {})
        dir_key = "long_parameters" if context.dominant_direction == "LONG" else "short_parameters"
        dir_risk = risk_m.get(dir_key, risk_m)
        
        sl_price = dir_risk.get("stop_loss", context.price * 0.99)
        tp1_price = dir_risk.get("take_profit_1", context.price * 1.015)
        tp2_price = dir_risk.get("take_profit_2", context.price * 1.03)
        rr_val = dir_risk.get("risk_reward", 2.5)
        sl_pips = dir_risk.get("risk_pips", 15.0)

        regime_label = context.engine_results.get("MarketRegime", {}).get("metrics", {}).get("regime", "NORMAL")
        tf_label = context.snapshot_meta.get("timeframe", "15M")
        session_label = context.snapshot_meta.get("session", "LONDON/NY_OVERLAP")
        asset_class = context.snapshot_meta.get("asset_class", "FOREX")

        relevant_knowledge = self.knowledge_retriever.retrieve_relevant_knowledge(
            symbol=context.symbol_name,
            regime=str(regime_label),
            setup_type="MOMENTUM_BREAKOUT",
            timeframe=str(tf_label),
            session=str(session_label),
            asset_class=str(asset_class),
            limit=3
        )
        knowledge_summaries = [
            f"[{k.get('category')}] {k.get('title')} (Win Rate: {k.get('win_rate', 0)}%, N={k.get('sample_size', 0)}, EV: {k.get('expectancy_r', 0)}R): {k.get('finding')}"
            for k in relevant_knowledge
        ]

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
            "retrieved_empirical_knowledge": knowledge_summaries,
            "engine_summaries": {
                name: {
                    "score": res.get("score"),
                    "direction": res.get("direction"),
                    "metrics": res.get("metrics")
                }
                for name, res in context.engine_results.items()
            }
        }

        router_res = self.router.evaluate_candidate(payload)
        provider = router_res.get("provider", "QuantitativeFallback")
        model = router_res.get("model", "deterministic-rules-engine" if provider == "QuantitativeFallback" else "gpt-4o")
        is_llm_fallback = router_res.get("is_llm_fallback", provider == "QuantitativeFallback")
        reasoning_text = router_res.get("reasoning", "Passed parallel evidence, meta-model, and empirical validation.")
        llm_approved = router_res.get("approved", True)

        score = context.composite_opportunity_score
        conf = context.overall_confidence
        min_score = float(getattr(settings, "MIN_OPPORTUNITY_SCORE", 70.0))
        watch_threshold = max(40.0, min_score - 12.0)

        if score >= min_score and conf >= 0.50 and context.dominant_direction != "NEUTRAL" and len(context.contradicting_evidence) <= 2 and llm_approved:
            decision = "TRADE"
        elif score >= watch_threshold and context.dominant_direction != "NEUTRAL":
            decision = "WATCH"
        else:
            decision = "NO_TRADE"

        return {
            "decision": decision,
            "symbol": context.symbol,
            "symbol_name": context.symbol_name,
            "direction": context.dominant_direction,
            "opportunity_score": score,
            "confidence": context.overall_confidence,
            "provider": provider,
            "model": model,
            "is_llm_fallback": is_llm_fallback,
            "llm_approved": llm_approved,
            "llm_reasoning": reasoning_text,
            "why_this_trade": {
                "what": f"{context.symbol_name} {context.dominant_direction} Trade Setup ({tf_label})",
                "asset_class": asset_class,
                "why": reasoning_text
            },
            "retrieved_knowledge": relevant_knowledge,
            "raw_context": payload
        }

    def rank_opportunities(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ranks valid trade decisions by expected value, consensus, and opportunity score.
        """
        valid = [d for d in decisions if d.get("decision") == "TRADE"]
        sorted_decisions = sorted(
            valid,
            key=lambda x: (x.get("expected_value_r", 0.0), x.get("directional_consensus", 0.0), x.get("opportunity_score", 0.0)),
            reverse=True
        )
        return sorted_decisions

DecisionEngine = LLMDecisionEngine

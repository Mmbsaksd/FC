import uuid
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime, timezone

from app.parallel.base_engine import MarketSnapshot, AnalysisResult

logger = logging.getLogger(__name__)

@dataclass
class CompleteMarketContext:
    scan_id: str
    trace_id: str
    timestamp: str
    symbol: str
    symbol_name: str
    price: float
    spread_pips: float
    snapshot_meta: Dict[str, Any]
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    neutral_factors: List[str] = field(default_factory=list)
    engine_results: Dict[str, Any] = field(default_factory=dict)
    dominant_direction: str = "NEUTRAL"
    composite_opportunity_score: float = 50.0
    overall_confidence: float = 0.5
    missing_engines: List[str] = field(default_factory=list)

class EvidenceAggregator:
    """
    Aggregates, normalizes, and classifies findings from all parallel analysis engines.
    Applies orthogonal feature weighting, confidence scaling, and separates directional
    alpha from non-directional market regime context.
    """

    # Orthogonal Engine Weights
    ENGINE_WEIGHTS = {
        "TechnicalAnalysis": 0.25,
        "MarketStructure": 0.20,
        "CurrencyStrength": 0.20,
        "MLPrediction": 0.15,
        "RiskMetrics": 0.10,
        "MacroAnalysis": 0.05,
        "SentimentCrossAsset": 0.05
    }

    def aggregate_evidence(
        self,
        snapshot: MarketSnapshot,
        engine_results: Dict[str, AnalysisResult],
        scan_id: str = None
    ) -> CompleteMarketContext:
        scan_id = scan_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        supporting: List[str] = []
        contradicting: List[str] = []
        neutral: List[str] = []
        missing: List[str] = []

        direction_weighted_votes = {"LONG": 0.0, "SHORT": 0.0, "NEUTRAL": 0.0}
        results_dict = {}

        total_weighted_score = 0.0
        total_weight_applied = 0.0
        weighted_conf_sum = 0.0

        # Pass 1: Collect findings, metrics, and direction weights
        for name, res in engine_results.items():
            results_dict[name] = {
                "status": res.status,
                "score": res.score,
                "direction": res.direction,
                "confidence": res.confidence,
                "metrics": res.metrics,
                "latency_ms": res.latency_ms
            }

            if res.status != "SUCCESS":
                missing.append(name)
                continue

            weight = self.ENGINE_WEIGHTS.get(name, 0.05)

            # Accumulate direction votes weighted by engine confidence and weight
            effective_vote = max(0.2, res.confidence) * weight
            direction_weighted_votes[res.direction] = direction_weighted_votes.get(res.direction, 0.0) + effective_vote

            # Collect evidence and caveats
            for ev in res.evidence:
                supporting.append(f"[{name}] {ev}")

            for con in res.contradictions:
                contradicting.append(f"[{name}] {con}")

            if res.direction == "NEUTRAL" and not res.evidence:
                neutral.append(f"[{name}] Output is neutral with no directional bias")

        # Determine dominant direction from weighted votes
        long_vote_weight = direction_weighted_votes.get("LONG", 0.0)
        short_vote_weight = direction_weighted_votes.get("SHORT", 0.0)

        if long_vote_weight > short_vote_weight * 1.15:
            dominant_direction = "LONG"
        elif short_vote_weight > long_vote_weight * 1.15:
            dominant_direction = "SHORT"
        else:
            dominant_direction = "NEUTRAL"

        # Pass 2: Calculate direction-aligned weighted composite score
        for name, res in engine_results.items():
            if res.status != "SUCCESS":
                continue

            weight = self.ENGINE_WEIGHTS.get(name, 0.05)

            # Directional alignment multiplier
            if dominant_direction == "NEUTRAL":
                alignment = 1.0
            elif res.direction == dominant_direction:
                alignment = 1.0
            elif res.direction == "NEUTRAL":
                alignment = 0.70  # Neutral non-directional context
            else:
                alignment = 0.25  # Opposing directional signal

            aligned_score = res.score * alignment
            total_weighted_score += (aligned_score * weight)
            total_weight_applied += weight
            weighted_conf_sum += (res.confidence * weight)

        raw_composite = (total_weighted_score / total_weight_applied) if total_weight_applied > 0 else 50.0

        # Adjust for market regime context
        regime_res = engine_results.get("MarketRegime")
        if regime_res and regime_res.status == "SUCCESS":
            regime_val = regime_res.metrics.get("regime", "")
            if regime_val == "LOW_VOLATILITY_CONSOLIDATION":
                raw_composite = raw_composite * 0.92 # Slight penalty for chop
            elif regime_val == "HIGH_VOLATILITY_EXPANSION" and dominant_direction != "NEUTRAL":
                raw_composite = min(96.0, raw_composite * 1.02) # Trend expansion boost

        # Penalize for true conflicting directional contradictions
        if len(contradicting) > 0 and dominant_direction != "NEUTRAL":
            contradiction_factor = min(20.0, len(contradicting) * 3.0)
            composite_score = max(30.0, raw_composite - contradiction_factor)
        else:
            composite_score = raw_composite

        composite_score = round(float(np.clip(composite_score, 10.0, 98.0)), 2)
        base_confidence = (weighted_conf_sum / total_weight_applied) if total_weight_applied > 0 else 0.5
        overall_confidence = round(float(np.clip(base_confidence * (composite_score / 75.0), 0.1, 0.98)), 2)

        return CompleteMarketContext(
            scan_id=scan_id,
            trace_id=trace_id,
            timestamp=timestamp,
            symbol=snapshot.symbol,
            symbol_name=snapshot.symbol_name,
            price=snapshot.price,
            spread_pips=snapshot.spread_pips,
            snapshot_meta={
                "timeframe": snapshot.timeframe,
                "session": snapshot.session,
                "data_quality": snapshot.data_quality_status,
                "is_crypto": snapshot.is_crypto
            },
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            neutral_factors=neutral,
            engine_results=results_dict,
            dominant_direction=dominant_direction,
            composite_opportunity_score=composite_score,
            overall_confidence=overall_confidence,
            missing_engines=missing
        )

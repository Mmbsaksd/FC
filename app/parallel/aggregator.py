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
    # Direction-Aware Architecture Extensions (v2.0 Candidate)
    long_evidence: float = 0.0
    short_evidence: float = 0.0
    neutral_evidence: float = 0.0
    directional_consensus: float = 0.0
    supporting_strength: float = 0.0
    contradicting_strength: float = 0.0
    weighted_contributions: Dict[str, Any] = field(default_factory=dict)
    confidence_type: str = "heuristic"
    candidate_qualified: bool = False
    qualification_reason: str = ""
    expected_value_r: float = 0.0

    @property
    def composite_score(self) -> float:
        return self.composite_opportunity_score

class EvidenceAggregator:
    """
    Evidence Aggregator supporting both CHAMPION baseline and CANDIDATE direction-aware evidence aggregation.
    """

    # Asset-Aware Engine Weight Profiles (Champion Baseline)
    ASSET_PROFILES = {
        "FOREX": {
            "TechnicalAnalysis": 0.25,
            "MarketStructure": 0.20,
            "CurrencyStrength": 0.20,
            "MLPrediction": 0.15,
            "RiskMetrics": 0.10,
            "MacroAnalysis": 0.05,
            "SentimentCrossAsset": 0.05
        },
        "COMMODITY": {
            "TechnicalAnalysis": 0.25,
            "MarketStructure": 0.20,
            "MacroAnalysis": 0.20,
            "SentimentCrossAsset": 0.15,
            "MLPrediction": 0.10,
            "RiskMetrics": 0.10,
            "CurrencyStrength": 0.00
        },
        "CRYPTO": {
            "TechnicalAnalysis": 0.25,
            "MarketStructure": 0.20,
            "SentimentCrossAsset": 0.20,
            "MLPrediction": 0.20,
            "RiskMetrics": 0.15,
            "MacroAnalysis": 0.00,
            "CurrencyStrength": 0.00
        }
    }

    # Candidate v2.0 Direction-Aware Asset Profiles with Explainability
    CANDIDATE_ASSET_PROFILES = {
        "FOREX": {
            "TechnicalAnalysis": {"weight": 0.15, "reason": "Multi-oscillator momentum & trend alignment"},
            "MarketStructure": {"weight": 0.15, "reason": "Fractal swing structure, BOS, and CHoCH validation"},
            "CurrencyStrength": {"weight": 0.15, "reason": "Fiat currency basket relative divergence"},
            "CandleStructure": {"weight": 0.10, "reason": "Point-in-time price action rejection & engulfing"},
            "MacroAnalysis": {"weight": 0.10, "reason": "DXY trend and sovereign policy rate differentials"},
            "SentimentCrossAsset": {"weight": 0.10, "reason": "VIX, safe-haven flows, and cross-asset risk appetite"},
            "MLPrediction": {"weight": 0.05, "reason": "Calibrated statistical trend continuation probability"},
            "RiskMetrics": {"weight": 0.10, "reason": "ATR stop-loss geometry and payoff efficiency"},
            "FundamentalAnalysis": {"weight": 0.05, "reason": "Economic release surprises and scheduled high-impact events"},
            "MarketRegime": {"weight": 0.05, "reason": "Volatility state and consolidation detection"}
        },
        "COMMODITY": {
            "TechnicalAnalysis": {"weight": 0.20, "reason": "Price momentum and moving average convergence"},
            "MarketStructure": {"weight": 0.20, "reason": "Commodity swing highs/lows and structural liquidity breaks"},
            "CandleStructure": {"weight": 0.15, "reason": "Candle exhaustion and rejection at key levels"},
            "RiskMetrics": {"weight": 0.15, "reason": "Commodity volatility-scaled ATR stops"},
            "SentimentCrossAsset": {"weight": 0.10, "reason": "Safe-haven gold demand and VIX risk sentiment"},
            "MacroAnalysis": {"weight": 0.10, "reason": "US Dollar DXY and Real 10Y Yields contextual pricing"},
            "MLPrediction": {"weight": 0.05, "reason": "Statistical momentum persistence"},
            "MarketRegime": {"weight": 0.05, "reason": "Volatility expansion regime context"},
            "CurrencyStrength": {"weight": 0.00, "reason": "Fiat currency matrix does not apply to single physical commodities"},
            "FundamentalAnalysis": {"weight": 0.00, "reason": "Central bank policy rates do not apply directly"}
        },
        "CRYPTO": {
            "TechnicalAnalysis": {"weight": 0.25, "reason": "Strong 24/7 technical momentum and trend following"},
            "MarketStructure": {"weight": 0.25, "reason": "Liquidity pool breaks and structural trend pivots"},
            "CandleStructure": {"weight": 0.15, "reason": "Intense wick rejection and absorption candles"},
            "RiskMetrics": {"weight": 0.15, "reason": "High-volatility risk bounding and ATR stop calibration"},
            "SentimentCrossAsset": {"weight": 0.10, "reason": "Crypto-wide beta, BTC dominance, and risk-on liquidity"},
            "MLPrediction": {"weight": 0.05, "reason": "Statistical momentum probability"},
            "MarketRegime": {"weight": 0.05, "reason": "Expansion vs consolidation regime context"},
            "MacroAnalysis": {"weight": 0.00, "reason": "Sovereign policy rate differentials not directly applicable"},
            "CurrencyStrength": {"weight": 0.00, "reason": "Fiat currency strength does not apply to crypto tokens"},
            "FundamentalAnalysis": {"weight": 0.00, "reason": "Forex economic releases not directly applicable"}
        }
    }

    ENGINE_WEIGHTS = ASSET_PROFILES["FOREX"]

    def aggregate_evidence(
        self,
        snapshot: MarketSnapshot,
        engine_results: Dict[str, AnalysisResult],
        scan_id: str = None,
        mode: str = "CANDIDATE"
    ) -> CompleteMarketContext:
        """
        Routes evidence aggregation to Champion baseline or Candidate direction-aware mode.
        """
        if mode == "CHAMPION":
            return self._aggregate_champion(snapshot, engine_results, scan_id)
        return self._aggregate_candidate(snapshot, engine_results, scan_id)

    def _aggregate_champion(
        self,
        snapshot: MarketSnapshot,
        engine_results: Dict[str, AnalysisResult],
        scan_id: str = None
    ) -> CompleteMarketContext:
        """
        Original Champion Aggregation Flow (Preserved exactly as protected baseline).
        """
        scan_id = scan_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        asset_class = getattr(snapshot, "asset_class", "FOREX").upper()
        if getattr(snapshot, "is_crypto", False):
            asset_class = "CRYPTO"
        weights_profile = self.ASSET_PROFILES.get(asset_class, self.ENGINE_WEIGHTS)

        supporting: List[str] = []
        contradicting: List[str] = []
        neutral: List[str] = []
        missing: List[str] = []

        direction_weighted_votes = {"LONG": 0.0, "SHORT": 0.0, "NEUTRAL": 0.0}
        results_dict = {}

        total_weighted_score = 0.0
        total_weight_applied = 0.0
        weighted_conf_sum = 0.0

        for name, res in engine_results.items():
            results_dict[name] = {
                "status": res.status,
                "score": res.score,
                "direction": res.direction,
                "confidence": res.confidence,
                "metrics": res.metrics,
                "latency_ms": getattr(res, "latency_ms", 0.0)
            }

            if res.status != "SUCCESS":
                missing.append(name)
                continue

            weight = weights_profile.get(name, 0.0)
            if weight <= 0.0:
                continue

            effective_vote = max(0.2, res.confidence) * weight
            direction_weighted_votes[res.direction] = direction_weighted_votes.get(res.direction, 0.0) + effective_vote

            for ev in res.evidence:
                supporting.append(f"[{name}] {ev}")

            for con in res.contradictions:
                contradicting.append(f"[{name}] {con}")

            if res.direction == "NEUTRAL" and not res.evidence:
                neutral.append(f"[{name}] Output is neutral with no directional bias")

        long_vote_weight = direction_weighted_votes.get("LONG", 0.0)
        short_vote_weight = direction_weighted_votes.get("SHORT", 0.0)

        if long_vote_weight > short_vote_weight * 1.15:
            dominant_direction = "LONG"
        elif short_vote_weight > long_vote_weight * 1.15:
            dominant_direction = "SHORT"
        else:
            dominant_direction = "NEUTRAL"

        for name, res in engine_results.items():
            if res.status != "SUCCESS":
                continue

            weight = weights_profile.get(name, 0.0)
            if weight <= 0.0:
                continue

            if dominant_direction == "NEUTRAL":
                alignment = 1.0
            elif res.direction == dominant_direction:
                alignment = 1.0
            elif res.direction == "NEUTRAL":
                alignment = 0.70
            else:
                alignment = 0.25

            aligned_score = res.score * alignment
            total_weighted_score += (aligned_score * weight)
            total_weight_applied += weight
            weighted_conf_sum += (res.confidence * weight)

        raw_composite = (total_weighted_score / total_weight_applied) if total_weight_applied > 0 else 50.0

        regime_res = engine_results.get("MarketRegime")
        if regime_res and regime_res.status == "SUCCESS":
            regime_val = regime_res.metrics.get("regime", "")
            if regime_val == "LOW_VOLATILITY_CONSOLIDATION":
                raw_composite = raw_composite * 0.92
            elif regime_val == "HIGH_VOLATILITY_EXPANSION" and dominant_direction != "NEUTRAL":
                raw_composite = min(96.0, raw_composite * 1.02)

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
                "timeframe": getattr(snapshot, "timeframe", "15m"),
                "session": getattr(snapshot, "session", "LONDON"),
                "data_quality": getattr(snapshot, "data_quality_status", getattr(snapshot, "data_quality", "VALID")),
                "is_crypto": getattr(snapshot, "is_crypto", False),
                "asset_class": asset_class,
                "aggregation_mode": "CHAMPION_BASELINE"
            },
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            neutral_factors=neutral,
            engine_results=results_dict,
            dominant_direction=dominant_direction,
            composite_opportunity_score=composite_score,
            overall_confidence=overall_confidence,
            missing_engines=missing,
            confidence_type="heuristic"
        )

    def _aggregate_candidate(
        self,
        snapshot: MarketSnapshot,
        engine_results: Dict[str, AnalysisResult],
        scan_id: str = None
    ) -> CompleteMarketContext:
        """
        Candidate v2.0 Direction-Aware Evidence Aggregator:
        - Separately computes LONG, SHORT, and NEUTRAL weighted evidence pools.
        - Opposing directional evidence is NEVER added as positive evidence.
        - Computes Net Directional Consensus in range [-1.0, +1.0].
        - Preserves explicit weight explainability and tags heuristic confidence.
        """
        scan_id = scan_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        asset_class = getattr(snapshot, "asset_class", "FOREX").upper()
        if snapshot.is_crypto:
            asset_class = "CRYPTO"
        elif "GOLD" in snapshot.symbol_name.upper() or "XAU" in snapshot.symbol.upper() or "GC=F" in snapshot.symbol:
            asset_class = "COMMODITY"

        weights_profile = self.CANDIDATE_ASSET_PROFILES.get(asset_class, self.CANDIDATE_ASSET_PROFILES["FOREX"])

        supporting: List[str] = []
        contradicting: List[str] = []
        neutral: List[str] = []
        missing: List[str] = []

        long_evidence = 0.0
        short_evidence = 0.0
        neutral_evidence = 0.0
        total_active_weight = 0.0

        results_dict = {}
        contributions_dict = {}

        for name, res in engine_results.items():
            results_dict[name] = {
                "status": res.status,
                "score": res.score,
                "direction": res.direction,
                "confidence": res.confidence,
                "metrics": res.metrics,
                "latency_ms": getattr(res, "latency_ms", 0.0),
                "confidence_type": "heuristic"
            }

            if res.status != "SUCCESS":
                missing.append(name)
                continue

            cfg = weights_profile.get(name, {"weight": 0.0, "reason": "Not applicable to asset class"})
            weight = cfg["weight"]
            reason = cfg["reason"]

            if weight <= 0.0:
                continue

            total_active_weight += weight

            # Direct engine weighted contribution: weight * raw_score (e.g. 0.10 * 75.0 = 7.50)
            raw_score = float(np.clip(res.score, 0.0, 100.0))
            direct_contrib = weight * raw_score

            contributions_dict[name] = {
                "raw_score": round(raw_score, 1),
                "direction": res.direction,
                "confidence": res.confidence,
                "confidence_type": "heuristic",
                "weight": weight,
                "weight_pct": f"{int(round(weight * 100))}%",
                "weighted_contribution": round(direct_contrib, 2),
                "reason_for_weight": reason
            }

            # Direction-aware scoring for LONG and SHORT:
            # - Matching direction contributes full score (weight * score)
            # - NEUTRAL contributes neutral baseline (weight * 50.0)
            # - Opposing direction contributes penalty (weight * max(0.0, 100.0 - score))
            if res.direction == "LONG":
                long_score_contrib = weight * raw_score
                short_score_contrib = weight * max(0.0, 100.0 - raw_score)
            elif res.direction == "SHORT":
                short_score_contrib = weight * raw_score
                long_score_contrib = weight * max(0.0, 100.0 - raw_score)
            else: # NEUTRAL
                long_score_contrib = weight * 50.0
                short_score_contrib = weight * 50.0

            long_evidence += long_score_contrib
            short_evidence += short_score_contrib
            neutral_evidence += (weight * 50.0) if res.direction == "NEUTRAL" else 0.0

            for ev in res.evidence:
                supporting.append(f"[{name}] {ev}")

            for con in res.contradictions:
                contradicting.append(f"[{name}] {con}")

            if res.direction == "NEUTRAL" and not res.evidence:
                neutral.append(f"[{name}] Neutral context")

        # Normalize by active weights sum in case any engine has 0 weight
        base_scale = total_active_weight if total_active_weight > 0 else 1.0
        norm_long_score = long_evidence / base_scale
        norm_short_score = short_evidence / base_scale

        # Determine Dominant Direction & Consensus
        score_diff = norm_long_score - norm_short_score
        consensus = score_diff / 100.0

        if norm_long_score > norm_short_score and norm_long_score >= 50.0:
            dominant_direction = "LONG"
            composite_score = norm_long_score
            supporting_strength = norm_long_score
            contradicting_strength = norm_short_score
        elif norm_short_score > norm_long_score and norm_short_score >= 50.0:
            dominant_direction = "SHORT"
            composite_score = norm_short_score
            supporting_strength = norm_short_score
            contradicting_strength = norm_long_score
        else:
            dominant_direction = "NEUTRAL"
            composite_score = max(norm_long_score, norm_short_score)
            supporting_strength = composite_score
            contradicting_strength = min(norm_long_score, norm_short_score)

        # Market regime contextual adjustment
        regime_res = engine_results.get("MarketRegime")
        if regime_res and regime_res.status == "SUCCESS":
            regime_val = regime_res.metrics.get("regime", "")
            if regime_val == "LOW_VOLATILITY_CONSOLIDATION":
                composite_score *= 0.98
            elif regime_val == "HIGH_VOLATILITY_EXPANSION" and dominant_direction != "NEUTRAL":
                composite_score = min(99.0, composite_score * 1.02)

        composite_score = round(float(np.clip(composite_score, 0.0, 100.0)), 2)
        overall_confidence = round(float(np.clip((composite_score / 100.0), 0.20, 0.95)), 2)

        return CompleteMarketContext(
            scan_id=scan_id,
            trace_id=trace_id,
            timestamp=timestamp,
            symbol=snapshot.symbol,
            symbol_name=snapshot.symbol_name,
            price=snapshot.price,
            spread_pips=snapshot.spread_pips,
            snapshot_meta={
                "timeframe": getattr(snapshot, "timeframe", "15m"),
                "session": getattr(snapshot, "session", "LONDON"),
                "data_quality": getattr(snapshot, "data_quality_status", getattr(snapshot, "data_quality", "VALID")),
                "is_crypto": getattr(snapshot, "is_crypto", False),
                "asset_class": asset_class,
                "aggregation_mode": "CANDIDATE_V2"
            },
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            neutral_factors=neutral,
            engine_results=results_dict,
            dominant_direction=dominant_direction,
            composite_opportunity_score=composite_score,
            overall_confidence=overall_confidence,
            missing_engines=missing,
            long_evidence=round(long_evidence, 3),
            short_evidence=round(short_evidence, 3),
            neutral_evidence=round(neutral_evidence, 3),
            directional_consensus=round(consensus, 3),
            supporting_strength=round(supporting_strength, 3),
            contradicting_strength=round(contradicting_strength, 3),
            weighted_contributions=contributions_dict,
            confidence_type="heuristic"
        )

class DirectionAwareEvidenceAggregator(EvidenceAggregator):
    """
    Explicit alias for candidate direction-aware evidence aggregation.
    """
    def aggregate_evidence(
        self,
        snapshot: MarketSnapshot,
        engine_results: Dict[str, AnalysisResult],
        scan_id: str = None
    ) -> CompleteMarketContext:
        return self._aggregate_candidate(snapshot, engine_results, scan_id)

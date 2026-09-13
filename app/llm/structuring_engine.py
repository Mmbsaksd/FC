"""
Small-Model & Preprocessing Structuring Layer.
Responsible for:
1. Normalizing raw engine outputs & sub-scores into structured market situations.
2. Generating canonical multi-dimensional retrieval query strings.
3. Compressing redundant context before Strong LLM adjudication.
4. STRICT INVARIANT: Does NOT make the trade decision (TRADE / WATCH / REJECT).
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.parallel.aggregator import CompleteMarketContext
from app.parallel.base_engine import MarketSnapshot

logger = logging.getLogger(__name__)


@dataclass
class StructuredMarketSituation:
    symbol: str
    asset_class: str
    timeframe: str
    session: str
    dominant_direction: str
    directional_consensus: float
    opportunity_score: float
    ml_probability: float
    expected_value_r: float
    risk_reward: float
    setup_classification: str
    regime_classification: str
    key_drivers: List[str]
    key_conflicts: List[str]
    retrieval_query: str
    compact_evidence_summary: str


class SmallModelStructuringEngine:
    """
    Lightweight deterministic preprocessing and structuring engine.
    Transforms raw multi-engine metrics into a unified situation representation.
    """

    @classmethod
    def structure_situation(
        cls,
        context: CompleteMarketContext,
        snapshot: Optional[MarketSnapshot] = None,
        trade_params: Optional[Dict[str, Any]] = None,
        ml_probability: float = 0.50
    ) -> StructuredMarketSituation:
        """
        Synthesizes raw evidence, sub-scores, and trade geometry into a clean structured situation.
        """
        symbol = context.symbol_name
        direction = context.dominant_direction
        asset_class = context.snapshot_meta.get("asset_class", "FOREX")
        timeframe = context.snapshot_meta.get("timeframe", "15M")
        session = context.snapshot_meta.get("session", "LONDON/NY_OVERLAP")
        
        # 1. Classify Setup Type from Technical / Structure metrics
        tech_m = context.engine_results.get("TechnicalAnalysis", {}).get("metrics", {})
        struct_m = context.engine_results.get("MarketStructure", {}).get("metrics", {})
        regime_m = context.engine_results.get("MarketRegime", {}).get("metrics", {})
        
        setup_type = tech_m.get("setup_type", "MOMENTUM_BREAKOUT")
        regime_type = regime_m.get("regime", "NORMAL")

        # 2. Extract Key Drivers (Top supporting engines by weighted contribution)
        drivers = []
        for eng_name, contrib_info in context.weighted_contributions.items():
            if isinstance(contrib_info, dict):
                score = contrib_info.get("raw_score", 0.0)
                d = contrib_info.get("direction", "NEUTRAL")
                w_pct = contrib_info.get("weight_pct", "0%")
                if d == direction and score >= 65.0:
                    drivers.append(f"{eng_name} ({w_pct}): {d} score {score:.1f}")

        # 3. Extract Key Conflicts (Opposing engines)
        conflicts = []
        for eng_name, contrib_info in context.weighted_contributions.items():
            if isinstance(contrib_info, dict):
                score = contrib_info.get("raw_score", 0.0)
                d = contrib_info.get("direction", "NEUTRAL")
                if d != "NEUTRAL" and d != direction:
                    conflicts.append(f"{eng_name} opposes with {d} (score {score:.1f})")

        # 4. Generate Canonical Retrieval Query
        rr_val = float(trade_params.get("risk_reward", 2.0)) if trade_params else 2.0
        ev_val = float(context.expected_value_r)
        
        retrieval_query = (
            f"Asset:{symbol} AssetClass:{asset_class} Direction:{direction} "
            f"Setup:{setup_type} Regime:{regime_type} Timeframe:{timeframe} "
            f"Consensus:{context.directional_consensus:+.2f} MLProb:{ml_probability:.2f} EV:{ev_val:+.2f}R"
        )

        # 5. Build Compact Summary for LLM Context Efficiency
        compact_summary = (
            f"Situation: {symbol} {direction} {setup_type} on {timeframe} ({session})\n"
            f"Consensus: {context.directional_consensus:+.2f} | Score: {context.composite_opportunity_score:.1f} | ML: {ml_probability*100:.1f}% | EV: {ev_val:+.2f}R (1:{rr_val:.1f})\n"
            f"Supporting Core: {'; '.join(drivers[:3]) if drivers else 'None'}\n"
            f"Opposing Frictions: {'; '.join(conflicts[:2]) if conflicts else 'None'}"
        )

        return StructuredMarketSituation(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            session=session,
            dominant_direction=direction,
            directional_consensus=context.directional_consensus,
            opportunity_score=context.composite_opportunity_score,
            ml_probability=ml_probability,
            expected_value_r=ev_val,
            risk_reward=rr_val,
            setup_classification=setup_type,
            regime_classification=regime_type,
            key_drivers=drivers,
            key_conflicts=conflicts,
            retrieval_query=retrieval_query,
            compact_evidence_summary=compact_summary
        )


# Global singleton instance
structuring_engine = SmallModelStructuringEngine()

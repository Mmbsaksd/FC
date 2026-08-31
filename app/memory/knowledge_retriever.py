import math
import logging
from typing import Dict, Any, List, Tuple, Optional
from app.memory.knowledge_base import knowledge_base, EmpiricalKnowledgeBase

logger = logging.getLogger(__name__)

class ContextualKnowledgeRetriever:
    """
    Upgraded Multi-Dimensional Contextual Knowledge Retriever.
    Retrieves validated empirical facts and risk rules from EmpiricalKnowledgeBase
    matching the current candidate context (symbol, asset class, timeframe, regime, session).
    Filters out unvalidated HYPOTHESES from live trading signals to protect execution safety.
    Ranks candidates by relevance, empirical sample weight, and freshness decay score.
    """

    def __init__(self, kb: EmpiricalKnowledgeBase = None):
        self.kb = kb or knowledge_base

    def retrieve_relevant_knowledge(
        self,
        symbol: str,
        regime: str = "NORMAL",
        setup_type: str = "BREAKOUT",
        timeframe: str = "15M",
        session: str = "LONDON/NY_OVERLAP",
        asset_class: Optional[str] = None,
        limit: int = 3,
        include_experimental: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top relevant validated knowledge items with full matching rationale.
        """
        # Determine allowed statuses: VALIDATED (and optionally EXPERIMENTAL)
        allowed_statuses = ["VALIDATED"]
        if include_experimental:
            allowed_statuses.append("EXPERIMENTAL")

        all_items = [i for i in self.kb.items if i.get("status") in allowed_statuses]
        scored_items: List[Tuple[float, Dict[str, Any], str]] = []

        clean_sym = symbol.replace("/", "").replace("_", "").upper()
        if not asset_class:
            asset_class = self._infer_asset_class(symbol)

        for item in all_items:
            score = 0.0
            reasons = []

            # 1. Symbol & Currency Match
            app_syms = [s.replace("/", "").replace("_", "").upper() for s in item.get("applicable_symbols", [])]
            sym_matched = False
            if clean_sym in app_syms:
                score += 4.0
                sym_matched = True
                reasons.append(f"Exact symbol ({symbol})")
            elif any(c in clean_sym for c in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "GOLD", "XAU"]):
                for s in app_syms:
                    if any(c in clean_sym and c in s for c in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "GOLD", "XAU"]):
                        score += 1.2
                        sym_matched = True
                        reasons.append("Currency overlap")
                        break

            # 2. Asset Class Match
            app_assets = [a.upper() for a in item.get("applicable_asset_classes", ["ALL"])]
            specific_asset_match = (asset_class.upper() in app_assets and "ALL" not in app_assets)
            if specific_asset_match:
                score += 2.5
                reasons.append(f"Asset class ({asset_class})")
            elif "ALL" in app_assets:
                score += 0.5

            # 3. Timeframe Match
            app_tf = [t.upper() for t in item.get("applicable_timeframes", ["ALL"])]
            if timeframe.upper() in app_tf and "ALL" not in app_tf:
                score += 2.0
                reasons.append(f"Timeframe ({timeframe})")
            elif "ALL" in app_tf:
                score += 0.5

            # 4. Regime Match
            app_regimes = [r.upper() for r in item.get("applicable_regimes", ["ALL"])]
            specific_regime_match = (regime.upper() in app_regimes and "ALL" not in app_regimes)
            if specific_regime_match:
                score += 2.5
                reasons.append(f"Regime ({regime})")
            elif "ALL" in app_regimes:
                score += 0.5

            # Primary context gate: MUST match either exact/overlap symbol, specific asset class, or specific regime
            if not (sym_matched or specific_asset_match or specific_regime_match):
                continue

            # 5. Session Match
            app_sessions = [s.upper() for s in item.get("applicable_sessions", ["ALL"])]
            if session.upper() in app_sessions and "ALL" not in app_sessions:
                score += 1.5
                reasons.append(f"Session ({session})")

            # 6. Empirical Sample Weight Boost (Log-scaled)
            n_samples = max(1, int(item.get("sample_size", 10)))
            sample_weight = min(2.5, math.log10(n_samples) * 1.0)
            score += sample_weight

            # 7. Freshness Time-Decay Multiplier
            freshness = float(item.get("freshness_score", 1.0))
            score = score * freshness

            if score > 3.0:
                reason_str = " + ".join(reasons) + f" [Score: {score:.1f}, Freshness: {freshness:.2f}]"
                
                # Clone item and attach retrieval explanation
                retrieved_item = dict(item)
                retrieved_item["retrieval_score"] = round(score, 2)
                retrieved_item["retrieval_reason"] = reason_str
                
                scored_items.append((score, retrieved_item, reason_str))

                # Increment retrieval counter
                usage = item.setdefault("usage_stats", {})
                usage["times_retrieved"] = usage.get("times_retrieved", 0) + 1

        # Sort by total relevance score descending
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [it[1] for it in scored_items[:limit]]

    def _infer_asset_class(self, symbol: str) -> str:
        s = symbol.upper()
        if any(c in s for c in ["BTC", "ETH", "SOL", "XRP", "-USD"]):
            return "CRYPTO"
        elif any(c in s for c in ["XAU", "GOLD", "OIL", "WTI", "BRENT"]):
            return "COMMODITIES"
        return "FOREX"

# Global singleton
knowledge_retriever = ContextualKnowledgeRetriever()

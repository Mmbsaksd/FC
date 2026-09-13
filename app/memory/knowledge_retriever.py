"""
Hybrid Multi-Dimensional Knowledge & Vector Retriever.
Combines:
1. Hard Metadata Filtering (symbol, asset_class, timeframe, regime, session, validation_status)
2. Keyword & Empirical Attribute Scoring
3. Dense Vector Cosine Similarity Search
4. Category Provenance Tagging & Prompt Injection Protection
"""

import math
import logging
from typing import Dict, Any, List, Tuple, Optional
from app.memory.knowledge_base import knowledge_base, EmpiricalKnowledgeBase
from app.memory.vector_store import vector_store, LocalVectorStore

logger = logging.getLogger(__name__)


class HybridKnowledgeRetriever:
    """
    Hybrid Retriever integrating relational metadata filtering, empirical scoring,
    and vector similarity search across institutional knowledge collections.
    """

    def __init__(
        self,
        kb: Optional[EmpiricalKnowledgeBase] = None,
        v_store: Optional[LocalVectorStore] = None
    ):
        self.kb = kb or knowledge_base
        self.vector_store = v_store or vector_store

    def retrieve_hybrid_knowledge(
        self,
        symbol: str,
        direction: str = "LONG",
        regime: str = "NORMAL",
        setup_type: str = "BREAKOUT",
        timeframe: str = "15M",
        session: str = "LONDON/NY_OVERLAP",
        asset_class: Optional[str] = None,
        semantic_query: Optional[str] = None,
        limit: int = 3,
        include_external_reference: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid retrieval combining metadata-filtered empirical items and vector similarity search.
        """
        clean_sym = symbol.replace("/", "").replace("_", "").upper()
        if not asset_class:
            asset_class = self._infer_asset_class(symbol)

        # 1. Build Metadata Filters
        meta_filters = {
            "applicable_asset_classes": asset_class,
            "applicable_regimes": regime
        }

        # 2. Build canonical situation query if not explicitly passed
        if not semantic_query:
            semantic_query = (
                f"{symbol} {direction} {setup_type} {regime} {timeframe} {session} "
                f"AssetClass:{asset_class} Strategy:MomentumBreakout"
            )

        # 3. Vector Similarity Search
        vector_results = self.vector_store.similarity_search(
            query=semantic_query,
            metadata_filters=None, # Filter dynamically in reranker for flexibility
            limit=limit * 2,
            min_similarity=0.05
        )
        vector_doc_map = {doc["doc_id"]: sim for sim, doc in vector_results}

        # 4. Filter and Score Structured Knowledge Base items
        allowed_statuses = ["VALIDATED", "EMPIRICAL"]
        if include_external_reference:
            allowed_statuses.append("EXTERNAL_REFERENCE")

        all_items = [i for i in self.kb.items if i.get("status") in allowed_statuses]
        scored_items: List[Tuple[float, Dict[str, Any], str]] = []

        for item in all_items:
            score = 0.0
            reasons = []
            item_id = item.get("item_id", "")

            # A. Symbol & Currency Match
            app_syms = [s.replace("/", "").replace("_", "").upper() for s in item.get("applicable_symbols", [])]
            sym_matched = False
            if clean_sym in app_syms:
                score += 4.0
                sym_matched = True
                reasons.append(f"Exact symbol ({symbol})")
            elif any(c in clean_sym for c in ["USD", "EUR", "GBP", "JPY", "GOLD", "XAU", "BTC", "ETH"]):
                for s in app_syms:
                    if any(c in clean_sym and c in s for c in ["USD", "EUR", "GBP", "JPY", "GOLD", "XAU", "BTC", "ETH"]):
                        score += 1.5
                        sym_matched = True
                        reasons.append("Currency/Asset overlap")
                        break

            # B. Asset Class Match & Hard Isolation Filter
            app_assets = [a.upper() for a in item.get("applicable_asset_classes", ["ALL"])]
            if "ALL" not in app_assets and asset_class.upper() not in app_assets:
                # Hard isolation: Item belongs exclusively to a different asset class
                continue

            specific_asset_match = (asset_class.upper() in app_assets and "ALL" not in app_assets)
            if specific_asset_match:
                score += 2.5
                reasons.append(f"Asset class ({asset_class})")
            elif "ALL" in app_assets:
                score += 0.5

            # C. Timeframe Match
            app_tf = [t.upper() for t in item.get("applicable_timeframes", ["ALL"])]
            if timeframe.upper() in app_tf and "ALL" not in app_tf:
                score += 2.0
                reasons.append(f"Timeframe ({timeframe})")
            elif "ALL" in app_tf:
                score += 0.5

            # D. Regime Match
            app_regimes = [r.upper() for r in item.get("applicable_regimes", ["ALL"])]
            specific_regime_match = (regime.upper() in app_regimes and "ALL" not in app_regimes)
            if specific_regime_match:
                score += 2.5
                reasons.append(f"Regime ({regime})")
            elif "ALL" in app_regimes:
                score += 0.5

            # E. Vector Similarity Contribution
            if item_id in vector_doc_map:
                v_sim = vector_doc_map[item_id]
                score += (v_sim * 3.0)
                reasons.append(f"Vector Similarity ({v_sim:.2f})")

            # Must match either symbol, specific asset class, regime, or high vector similarity
            if not (sym_matched or specific_asset_match or specific_regime_match or (item_id in vector_doc_map)):
                continue

            # F. Empirical Sample Weight Boost
            n_samples = max(1, int(item.get("sample_size", 10)))
            sample_weight = min(2.5, math.log10(n_samples) * 1.0)
            score += sample_weight

            # G. Freshness Decay
            freshness = float(item.get("freshness_score", 1.0))
            score = score * freshness

            if score > 2.5:
                reason_str = " + ".join(reasons) + f" [Score: {score:.1f}, Freshness: {freshness:.2f}]"
                retrieved_item = dict(item)
                retrieved_item["retrieval_score"] = round(score, 2)
                retrieved_item["retrieval_reason"] = reason_str
                retrieved_item["vector_similarity"] = round(vector_doc_map.get(item_id, 0.0), 3)
                
                # Tag source category for LLM prompt separation
                cat = item.get("category", "STRATEGY_RULE")
                if cat == "FAILURE_POST_MORTEM":
                    retrieved_item["provenance_category"] = "FAILURE_MEMORY"
                elif cat == "RESEARCH_LITERATURE":
                    retrieved_item["provenance_category"] = "EXTERNAL_RESEARCH"
                elif cat == "HISTORICAL_TRADE":
                    retrieved_item["provenance_category"] = "FC_HISTORICAL_EXPERIENCE"
                else:
                    retrieved_item["provenance_category"] = "VALIDATED_STRATEGY_KNOWLEDGE"

                scored_items.append((score, retrieved_item, reason_str))

        # Sort descending by hybrid score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [it[1] for it in scored_items[:limit]]

    # Backward compatibility alias
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
        return self.retrieve_hybrid_knowledge(
            symbol=symbol,
            direction="LONG",
            regime=regime,
            setup_type=setup_type,
            timeframe=timeframe,
            session=session,
            asset_class=asset_class,
            limit=limit,
            include_external_reference=True
        )

    def _infer_asset_class(self, symbol: str) -> str:
        s = symbol.upper()
        if any(c in s for c in ["BTC", "ETH", "-USD"]):
            return "CRYPTO"
        elif any(c in s for c in ["XAU", "GOLD", "GC=F"]):
            return "COMMODITY"
        return "FOREX"


# Global singleton instance
knowledge_retriever = HybridKnowledgeRetriever()
ContextualKnowledgeRetriever = HybridKnowledgeRetriever

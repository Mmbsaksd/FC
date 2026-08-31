import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.memory.knowledge_base import knowledge_base, EmpiricalKnowledgeBase
from app.memory.experience_memory import experience_memory

logger = logging.getLogger(__name__)

class KnowledgeDiscoveryEngine:
    """
    Automated Post-Trade Pattern & Knowledge Discovery Engine.
    Mines resolved trades in Experience Memory to identify recurring failure traps
    and high-expectancy confluence setups. Formulates structured candidate hypotheses,
    enforces strict sample-size promotion gates, and detects performance decay.
    """

    def __init__(self, kb: EmpiricalKnowledgeBase = None):
        self.kb = kb or knowledge_base
        self.min_samples_hypothesis = 5
        self.min_samples_experimental = 12
        self.min_samples_validated = 25

    def run_discovery_scan(self, experiences: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes empirical pattern mining across resolved trade outcomes.
        Produces candidate hypotheses and evaluates promotion/demotion gates.
        """
        if experiences is None:
            experiences = experience_memory.records

        resolved = [e for e in experiences if e.get("outcome_status") not in ["ACTIVE_PENDING", None]]
        if len(resolved) < self.min_samples_hypothesis:
            return {
                "status": "INSUFFICIENT_DATA",
                "resolved_trades_count": len(resolved),
                "required_minimum": self.min_samples_hypothesis,
                "message": f"Need at least {self.min_samples_hypothesis} resolved trades to run pattern discovery (current: {len(resolved)})."
            }

        candidates_discovered = []

        # 1. Cluster Analysis: Regime & Volatility Traps (Failure Discovery)
        choppy_trades = [
            e for e in resolved
            if "CHOPPY" in str(e.get("engine_evidence", {}).get("MarketRegime", {}).get("metrics", {}).get("regime", "")).upper()
            or "RANGE" in str(e.get("engine_evidence", {}).get("MarketRegime", {}).get("metrics", {}).get("regime", "")).upper()
        ]
        if len(choppy_trades) >= self.min_samples_hypothesis:
            losses = sum(1 for e in choppy_trades if "LOSS" in str(e.get("outcome_status", "")))
            loss_rate = round(losses / len(choppy_trades) * 100.0, 1)
            if loss_rate >= 60.0:
                candidates_discovered.append(self._create_hypothesis_from_cluster(
                    title="Choppy Regime Breakout Degradation Pattern",
                    category="FAILURE_ANALYSIS",
                    hypothesis="Breakout continuation setups triggered during Choppy/Ranging regimes suffer elevated loss rates.",
                    finding=f"Observed {loss_rate}% failure rate across {len(choppy_trades)} trades executed in choppy/ranging market regimes.",
                    sample_size=len(choppy_trades),
                    success_count=len(choppy_trades) - losses,
                    failure_count=losses,
                    win_rate=round(100.0 - loss_rate, 1),
                    expectancy_r=round(sum(float(e.get("realized_r", 0.0) or 0.0) for e in choppy_trades) / len(choppy_trades), 2),
                    applicable_regimes=["CHOPPY", "RANGING"],
                    applicable_symbols=list(set(e.get("symbol", "") for e in choppy_trades if e.get("symbol"))),
                    applicable_asset_classes=list(set(self._infer_asset_class(e.get("symbol", "")) for e in choppy_trades))
                ))

        # 2. Cluster Analysis: Currency Strength Divergence Confluence (Success Discovery)
        strong_cs_trades = [
            e for e in resolved
            if abs(float(e.get("engine_evidence", {}).get("CurrencyStrength", {}).get("metrics", {}).get("strength_diff", 0.0))) >= 1.5
        ]
        if len(strong_cs_trades) >= self.min_samples_hypothesis:
            wins = sum(1 for e in strong_cs_trades if "WIN" in str(e.get("outcome_status", "")))
            win_rate = round(wins / len(strong_cs_trades) * 100.0, 1)
            if win_rate >= 65.0:
                candidates_discovered.append(self._create_hypothesis_from_cluster(
                    title="High Currency Basket Divergence Edge",
                    category="STRATEGY_RULE",
                    hypothesis="Trades entered when base/quote currency strength difference exceeds 1.5 exhibit superior follow-through.",
                    finding=f"Strong currency divergence (diff >= 1.5) achieved {win_rate}% win rate across {len(strong_cs_trades)} trades with positive expectancy.",
                    sample_size=len(strong_cs_trades),
                    success_count=wins,
                    failure_count=len(strong_cs_trades) - wins,
                    win_rate=win_rate,
                    expectancy_r=round(sum(float(e.get("realized_r", 0.0) or 0.0) for e in strong_cs_trades) / len(strong_cs_trades), 2),
                    applicable_regimes=["TRENDING", "NORMAL"],
                    applicable_symbols=list(set(e.get("symbol", "") for e in strong_cs_trades if e.get("symbol"))),
                    applicable_asset_classes=["FOREX"]
                ))

        # 3. Cluster Analysis: Session Overlap SMC Structures
        overlap_trades = [
            e for e in resolved
            if "OVERLAP" in str(e.get("engine_evidence", {}).get("MarketSnapshot", {}).get("session", "")).upper()
            or (12 <= datetime.fromisoformat(e.get("created_at", "2026-01-01T00:00:00+00:00").replace("Z", "+00:00")).hour <= 16)
        ]
        if len(overlap_trades) >= self.min_samples_hypothesis:
            wins = sum(1 for e in overlap_trades if "WIN" in str(e.get("outcome_status", "")))
            win_rate = round(wins / len(overlap_trades) * 100.0, 1)
            if win_rate >= 65.0:
                candidates_discovered.append(self._create_hypothesis_from_cluster(
                    title="London/NY Overlap Momentum Confluence",
                    category="STRATEGY_RULE",
                    hypothesis="Institutional liquidity during London/NY overlap improves swing momentum completion.",
                    finding=f"London/NY session executions achieved {win_rate}% win rate across {len(overlap_trades)} observations.",
                    sample_size=len(overlap_trades),
                    success_count=wins,
                    failure_count=len(overlap_trades) - wins,
                    win_rate=win_rate,
                    expectancy_r=round(sum(float(e.get("realized_r", 0.0) or 0.0) for e in overlap_trades) / len(overlap_trades), 2),
                    applicable_sessions=["LONDON/NY_OVERLAP", "LONDON", "NEW_YORK"],
                    applicable_symbols=list(set(e.get("symbol", "") for e in overlap_trades if e.get("symbol"))),
                    applicable_asset_classes=["FOREX", "COMMODITIES"]
                ))

        # Register newly discovered candidate hypotheses (preventing duplicate titles)
        existing_titles = [i.get("title", "").lower() for i in self.kb.items]
        added_items = []
        for cand in candidates_discovered:
            if cand["title"].lower() not in existing_titles:
                new_id = self.kb.add_knowledge_item(cand)
                added_items.append(new_id)

        # 4. Evaluate Promotion Gates on all existing candidate/experimental items
        promotion_results = self.evaluate_promotion_gates()

        return {
            "status": "SUCCESS",
            "resolved_trades_evaluated": len(resolved),
            "candidates_discovered_count": len(candidates_discovered),
            "new_hypotheses_added": added_items,
            "promotion_gate_actions": promotion_results
        }

    def _create_hypothesis_from_cluster(
        self,
        title: str,
        category: str,
        hypothesis: str,
        finding: str,
        sample_size: int,
        success_count: int,
        failure_count: int,
        win_rate: float,
        expectancy_r: float,
        applicable_regimes: List[str] = None,
        applicable_symbols: List[str] = None,
        applicable_asset_classes: List[str] = None,
        applicable_sessions: List[str] = None
    ) -> Dict[str, Any]:
        return {
            "category": category,
            "title": title,
            "hypothesis": hypothesis,
            "finding": finding,
            "evidence": f"Automated ExperienceMemory cluster mining across {sample_size} resolved trades.",
            "sample_size": sample_size,
            "success_count": success_count,
            "failure_count": failure_count,
            "win_rate": win_rate,
            "expectancy_r": expectancy_r,
            "confidence": "MEDIUM" if sample_size < self.min_samples_experimental else "HIGH",
            "statistical_significance": f"Sample N = {sample_size} (Initial Discovery Gate)",
            "applicable_symbols": applicable_symbols or ["ALL"],
            "applicable_asset_classes": applicable_asset_classes or ["FOREX"],
            "applicable_timeframes": ["15M", "1H"],
            "applicable_regimes": applicable_regimes or ["ALL"],
            "applicable_sessions": applicable_sessions or ["ALL"],
            "status": "HYPOTHESIS",
            "source_type": "AUTOMATED_DISCOVERY",
            "source_reference": "Experience Memory Trade Mining",
            "discovery_method": "CLUSTER_MINING",
            "validation_method": "SAMPLE_SIZE_GATE"
        }

    def _infer_asset_class(self, symbol: str) -> str:
        s = symbol.upper()
        if any(c in s for c in ["BTC", "ETH", "SOL", "XRP", "-USD"]):
            return "CRYPTO"
        elif any(c in s for c in ["XAU", "GOLD", "OIL", "WTI", "BRENT"]):
            return "COMMODITIES"
        return "FOREX"

    def evaluate_promotion_gates(self) -> Dict[str, Any]:
        """
        Applies mathematical promotion & demotion gates across all knowledge items:
        - HYPOTHESIS -> EXPERIMENTAL when N >= 12
        - EXPERIMENTAL -> VALIDATED when N >= 25 and (win_rate >= 65% or failure_trap win_rate <= 35%) and EV >= +0.35R
        - VALIDATED -> REQUIRES_REVIEW if recent win rate < 45% (decay/invalidation)
        """
        promoted_to_exp = 0
        promoted_to_val = 0
        demoted_to_review = 0

        for it in self.kb.items:
            status = it.get("status", "HYPOTHESIS")
            sample_size = int(it.get("sample_size", 0))
            win_rate = float(it.get("win_rate", 0.0))
            expectancy = float(it.get("expectancy_r", 0.0))
            is_trap = it.get("category") == "FAILURE_ANALYSIS"

            # 1. Gate: HYPOTHESIS -> EXPERIMENTAL
            if status == "HYPOTHESIS" and sample_size >= self.min_samples_experimental:
                it["status"] = "EXPERIMENTAL"
                self.kb.update_item_status(it["item_id"], "EXPERIMENTAL", f"Sample size reached N={sample_size} >= {self.min_samples_experimental}")
                promoted_to_exp += 1

            # 2. Gate: EXPERIMENTAL -> VALIDATED
            elif status == "EXPERIMENTAL" and sample_size >= self.min_samples_validated:
                valid_rule = (not is_trap and win_rate >= 65.0 and expectancy >= 0.35)
                valid_trap = (is_trap and win_rate <= 35.0)
                if valid_rule or valid_trap:
                    self.kb.update_item_status(
                        it["item_id"], "VALIDATED",
                        f"Passed Gate: N={sample_size} >= {self.min_samples_validated}, WinRate={win_rate}%, EV={expectancy}R"
                    )
                    promoted_to_val += 1

            # 3. Gate: VALIDATED -> REQUIRES_REVIEW (Performance Degradation)
            elif status == "VALIDATED" and not is_trap and sample_size >= 30 and win_rate < 50.0:
                self.kb.update_item_status(
                    it["item_id"], "REQUIRES_REVIEW",
                    f"Performance deterioration detected: Win rate dropped to {win_rate}% (< 50%) across N={sample_size} trades."
                )
                demoted_to_review += 1

        return {
            "promoted_to_experimental": promoted_to_exp,
            "promoted_to_validated": promoted_to_val,
            "demoted_to_review": demoted_to_review
        }

# Global singleton
knowledge_discovery_engine = KnowledgeDiscoveryEngine()

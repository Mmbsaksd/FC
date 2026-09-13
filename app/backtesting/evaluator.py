"""
Multi-Objective Performance Evaluator & Champion-vs-Candidate Strategy Promotion Engine.
Computes institutional risk-adjusted metrics, executes side-by-side untouched OOS comparisons,
and enforces non-negotiable statistical promotion rules.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np

from app.backtesting.engine import HistoricalBacktestEngine

logger = logging.getLogger(__name__)

class StrategyEvaluator:
    """
    Evaluates trading system performance across multi-objective metrics:
    Sharpe, Sortino, Calmar, Max Drawdown, Expectancy, Profit Factor, and Tail Loss.
    Fairly compares Champion vs Candidate on identical out-of-sample periods.
    """

    @staticmethod
    def evaluate_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates institutional metrics from trade records."""
        return HistoricalBacktestEngine.calculate_performance_metrics(trades)

    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Alias for evaluate_trades."""
        return HistoricalBacktestEngine.calculate_performance_metrics(trades)

    @staticmethod
    def compare_champion_vs_candidate(
        champion_trades: List[Dict[str, Any]],
        candidate_trades: List[Dict[str, Any]],
        period_label: str = "2024-2026 (Untouched Out-of-Sample)"
    ) -> Dict[str, Any]:
        """
        Executes a rigorous side-by-side comparison on identical out-of-sample periods.
        Enforces the 8 strict promotion rules before recommending any strategy promotion.
        """
        champ_metrics = HistoricalBacktestEngine.calculate_performance_metrics(champion_trades)
        cand_metrics = HistoricalBacktestEngine.calculate_performance_metrics(candidate_trades)

        # Delta metrics
        delta_net_r = round(cand_metrics["net_r"] - champ_metrics["net_r"], 2)
        delta_sharpe = round(cand_metrics["sharpe_ratio"] - champ_metrics["sharpe_ratio"], 2)
        delta_win_rate = round(cand_metrics["win_rate"] - champ_metrics["win_rate"], 1)
        delta_mdd = round(cand_metrics["max_drawdown_r"] - champ_metrics["max_drawdown_r"], 2)
        delta_pf = round(cand_metrics["profit_factor"] - champ_metrics["profit_factor"], 2)

        # 8 Strict Promotion Rules Evaluation
        rule_1_expectancy = cand_metrics["expectancy_r"] > champ_metrics["expectancy_r"] or cand_metrics["net_r"] > champ_metrics["net_r"]
        rule_2_sharpe = cand_metrics["sharpe_ratio"] >= champ_metrics["sharpe_ratio"]
        rule_3_drawdown = cand_metrics["max_drawdown_r"] <= max(10.0, champ_metrics["max_drawdown_r"] * 1.1)
        rule_4_trade_count = cand_metrics["trade_count"] >= 10
        rule_5_profit_factor = cand_metrics["profit_factor"] >= 1.50
        rule_6_win_rate = cand_metrics["win_rate"] >= 50.0
        rule_7_positive_net = cand_metrics["net_r"] > 0.0
        rule_8_loss_containment = (cand_metrics["avg_loss_r"] >= -1.25)

        all_rules_passed = all([
            rule_1_expectancy,
            rule_2_sharpe,
            rule_3_drawdown,
            rule_4_trade_count,
            rule_5_profit_factor,
            rule_6_win_rate,
            rule_7_positive_net,
            rule_8_loss_containment
        ])

        recommendation = "PROMOTE_CANDIDATE_STRATEGY" if all_rules_passed else "KEEP_CURRENT_CHAMPION_STRATEGY"

        return {
            "period": period_label,
            "champion_metrics": champ_metrics,
            "candidate_metrics": cand_metrics,
            "deltas": {
                "net_r": delta_net_r,
                "sharpe_ratio": delta_sharpe,
                "win_rate_pct": delta_win_rate,
                "max_drawdown_r": delta_mdd,
                "profit_factor": delta_pf
            },
            "promotion_rules": {
                "rule_1_expectancy_improved": rule_1_expectancy,
                "rule_2_sharpe_maintained_or_improved": rule_2_sharpe,
                "rule_3_drawdown_controlled": rule_3_drawdown,
                "rule_4_adequate_sample_size": rule_4_trade_count,
                "rule_5_profit_factor_healthy": rule_5_profit_factor,
                "rule_6_win_rate_above_50": rule_6_win_rate,
                "rule_7_positive_net_return": rule_7_positive_net,
                "rule_8_loss_severity_bounded": rule_8_loss_containment
            },
            "all_rules_passed": all_rules_passed,
            "recommendation": recommendation,
            "decision_rationale": (
                f"Candidate demonstrated superior out-of-sample performance (+{delta_net_r}R net, Sharpe: {cand_metrics['sharpe_ratio']} vs {champ_metrics['sharpe_ratio']}) with controlled drawdown."
                if all_rules_passed else
                f"Candidate did not satisfy all 8 strict promotion gates. Retaining Champion baseline to prevent overfitting."
            )
        }

    @staticmethod
    def generate_decision_matrix(
        instrument_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Constructs the final decision matrix comparing Current vs Candidate across all instruments.
        """
        matrix = []
        for res in instrument_results:
            sym = res.get("symbol", "Asset")
            champ = res.get("champion", {})
            cand = res.get("candidate", {})
            oos = res.get("oos_metrics", {})
            mdd = oos.get("max_drawdown_r", 0.0)
            stability = res.get("stability", "ROBUST")
            rec = res.get("recommendation", "KEEP_CURRENT")

            matrix.append({
                "instrument": sym,
                "current_net_r": champ.get("net_r", 0.0),
                "candidate_net_r": cand.get("net_r", 0.0),
                "oos_net_r": oos.get("net_r", 0.0),
                "oos_win_rate": oos.get("win_rate", 0.0),
                "drawdown_r": mdd,
                "stability": stability,
                "recommendation": rec
            })
        return matrix

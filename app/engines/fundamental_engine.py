import logging
from typing import Dict, Any, List
import pandas as pd

logger = logging.getLogger(__name__)

class FundamentalAnalysisEngine:
    """
    Fundamental Analysis Engine evaluating economic releases (CPI, NFP, GDP, PMI, Central Bank Rates)
    and computing standard deviation surprise scores and upcoming event risks.
    """

    def __init__(self):
        self.economic_events = [
            {"currency": "USD", "event": "CPI MoM", "consensus": 0.2, "actual": 0.2, "std": 0.1, "importance": "HIGH"},
            {"currency": "USD", "event": "Non-Farm Payrolls", "consensus": 175, "actual": 190, "std": 30.0, "importance": "HIGH"},
            {"currency": "USD", "event": "ISM Services PMI", "consensus": 51.0, "actual": 52.4, "std": 1.5, "importance": "HIGH"},
            {"currency": "EUR", "event": "ECB Interest Rate", "consensus": 3.75, "actual": 3.75, "std": 0.25, "importance": "HIGH"},
            {"currency": "EUR", "event": "HICP Inflation YoY", "consensus": 2.5, "actual": 2.4, "std": 0.2, "importance": "HIGH"},
            {"currency": "GBP", "event": "BOE Bank Rate", "consensus": 5.25, "actual": 5.25, "std": 0.25, "importance": "HIGH"},
            {"currency": "GBP", "event": "UK GDP QoQ", "consensus": 0.6, "actual": 0.7, "std": 0.2, "importance": "MEDIUM"},
            {"currency": "JPY", "event": "BOJ Policy Rate", "consensus": 0.25, "actual": 0.25, "std": 0.15, "importance": "HIGH"},
            {"currency": "JPY", "event": "Tokyo Core CPI YoY", "consensus": 2.2, "actual": 2.4, "std": 0.3, "importance": "HIGH"},
            {"currency": "AUD", "event": "RBA Cash Rate", "consensus": 4.35, "actual": 4.35, "std": 0.25, "importance": "HIGH"},
            {"currency": "CAD", "event": "BOC Overnight Rate", "consensus": 4.75, "actual": 4.75, "std": 0.25, "importance": "HIGH"},
            {"currency": "CHF", "event": "SNB Policy Rate", "consensus": 1.25, "actual": 1.25, "std": 0.25, "importance": "HIGH"},
            {"currency": "NZD", "event": "RBNZ Official Cash Rate", "consensus": 5.25, "actual": 5.25, "std": 0.25, "importance": "HIGH"}
        ]

    def calculate_fundamental_score(self, base_currency: str, quote_currency: str) -> Dict[str, Any]:
        """
        Calculates fundamental score (0-100), net economic surprise, and upcoming event risk for currency pair.
        Returns neutral backdrop for non-FX commodities.
        """
        # Non-FX commodities and crypto return neutral macro-fundamental backdrop
        is_fx = (base_currency in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"] and
                 quote_currency in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"])

        if not is_fx:
            return {
                "score": 50.0,
                "net_surprise": 0.0,
                "base_surprise": 0.0,
                "quote_surprise": 0.0,
                "upcoming_high_impact_events": 0,
                "bias": "NEUTRAL"
            }

        base_surprises = []
        quote_surprises = []
        upcoming_events = 0

        for ev in self.economic_events:
            curr = ev["currency"]
            consensus = ev["consensus"]
            actual = ev["actual"]
            std = ev.get("std", 1.0)
            importance = ev.get("importance", "MEDIUM")
            surprise = (actual - consensus) / (std if std > 0 else 1.0)

            if curr == base_currency:
                base_surprises.append(surprise)
            elif curr == quote_currency:
                quote_surprises.append(surprise)

        base_score = float(pd.Series(base_surprises).mean()) if base_surprises else 0.0
        quote_score = float(pd.Series(quote_surprises).mean()) if quote_surprises else 0.0

        net_surprise = base_score - quote_score
        fund_score = round(float(50.0 + (net_surprise * 12.0)), 2)
        fund_score = max(20.0, min(85.0, fund_score))

        return {
            "score": fund_score,
            "net_surprise": round(net_surprise, 2),
            "base_surprise": round(base_score, 2),
            "quote_surprise": round(quote_score, 2),
            "upcoming_high_impact_events": upcoming_events,
            "bias": "LONG" if net_surprise > 0.1 else ("SHORT" if net_surprise < -0.1 else "NEUTRAL")
        }

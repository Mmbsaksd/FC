import logging
from typing import Dict, Any, List
import pandas as pd

logger = logging.getLogger(__name__)

class FundamentalAnalysisEngine:
    """
    Fundamental Analysis Engine evaluating economic releases (CPI, NFP, GDP, Central Bank Rates)
    and computing standard deviation surprise scores.
    """

    def __init__(self):
        # Sample macro economic baseline dataset (for initial scope)
        self.economic_events = [
            {"currency": "USD", "event": "CPI MoM", "consensus": 0.2, "actual": 0.1, "std": 0.1, "importance": "HIGH"},
            {"currency": "USD", "event": "Non-Farm Payrolls", "consensus": 175, "actual": 215, "std": 30.0, "importance": "HIGH"},
            {"currency": "EUR", "event": "ECB Interest Rate", "consensus": 3.75, "actual": 3.75, "std": 0.25, "importance": "HIGH"},
            {"currency": "GBP", "event": "UK GDP QoQ", "consensus": 0.6, "actual": 0.7, "std": 0.2, "importance": "MEDIUM"}
        ]

    def calculate_fundamental_score(self, base_currency: str, quote_currency: str) -> Dict[str, Any]:
        """
        Calculates fundamental score (0-100) and net economic surprise difference for currency pair.
        """
        base_surprises = []
        quote_surprises = []

        for ev in self.economic_events:
            curr = ev["currency"]
            consensus = ev["consensus"]
            actual = ev["actual"]
            std = ev.get("std", 1.0)
            surprise = (actual - consensus) / (std if std > 0 else 1.0)

            if curr == base_currency:
                base_surprises.append(surprise)
            elif curr == quote_currency:
                quote_surprises.append(surprise)

        base_score = float(pd.Series(base_surprises).mean()) if base_surprises else 0.0
        quote_score = float(pd.Series(quote_surprises).mean()) if quote_surprises else 0.0

        net_surprise = base_score - quote_score
        # Scale to 0-100 score
        fund_score = round(float(50.0 + (net_surprise * 15.0)), 2)
        fund_score = max(10.0, min(95.0, fund_score))

        return {
            "score": fund_score,
            "net_surprise": round(net_surprise, 2),
            "base_surprise": round(base_score, 2),
            "quote_surprise": round(quote_score, 2),
            "bias": "LONG" if net_surprise > 0 else ("SHORT" if net_surprise < 0 else "NEUTRAL")
        }

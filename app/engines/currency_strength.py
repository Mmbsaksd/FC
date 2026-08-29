import logging
from typing import Dict, List, Any
import pandas as pd
import numpy as np

from app.config.constants import MAJOR_CURRENCIES, TRACKED_INSTRUMENTS
from app.providers.yahoo_provider import YahooMarketDataProvider

logger = logging.getLogger(__name__)

class CurrencyStrengthEngine:
    """
    Computes relative currency strength (0 to 10 scale) across 8 major currencies.
    Memory Footprint: < 5 MB RAM.
    """

    def __init__(self, provider: YahooMarketDataProvider = None):
        self.provider = provider or YahooMarketDataProvider()

    def calculate_currency_strength(self, timeframe: str = "1H") -> Dict[str, float]:
        """
        Calculates normalized currency strength score (-10 to +10) for each major currency.
        Positive values = Strong, Negative values = Weak.
        """
        returns_matrix = {curr: [] for curr in MAJOR_CURRENCIES}

        # Fetch returns for available FX pairs
        for inst in TRACKED_INSTRUMENTS:
            if inst["type"] != "FOREX":
                continue

            symbol = inst["symbol"]
            base = inst["base"]
            quote = inst["quote"]

            df = self.provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=20)
            if df.empty or len(df) < 2:
                continue

            # Log return over recent 10 candles
            start_price = df['close'].iloc[0]
            end_price = df['close'].iloc[-1]
            if start_price > 0:
                ret = np.log(end_price / start_price) * 100.0
                returns_matrix[base].append(ret)
                returns_matrix[quote].append(-ret)

        strength_scores = {}
        for curr, rets in returns_matrix.items():
            if rets:
                avg_ret = np.mean(rets)
                # Scale to -10.0 ... +10.0
                score = np.clip(avg_ret * 5.0, -10.0, 10.0)
                strength_scores[curr] = round(float(score), 2)
            else:
                strength_scores[curr] = 0.0

        return strength_scores

    def get_strong_weak_pairs(self, strength_scores: Dict[str, float], threshold: float = 2.0) -> List[Dict[str, Any]]:
        """
        Identifies Strong vs Weak combinations (e.g. Strong USD vs Weak JPY).
        """
        sorted_currencies = sorted(strength_scores.items(), key=lambda x: x[1], reverse=True)
        strongest = [c for c in sorted_currencies if c[1] >= threshold]
        weakest = [c for c in sorted_currencies if c[1] <= -threshold]

        opportunities = []
        for s_curr, s_score in strongest:
            for w_curr, w_score in weakest:
                spread = s_score - w_score
                opportunities.append({
                    "strong_currency": s_curr,
                    "weak_currency": w_curr,
                    "strength_diff": round(spread, 2),
                    "suggested_pair": f"{s_curr}/{w_curr}",
                    "bias": "LONG"
                })

        return sorted(opportunities, key=lambda x: x["strength_diff"], reverse=True)

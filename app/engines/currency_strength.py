import time
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
        Uses Z-score relative return distribution across active currencies with caching.
        """
        cache_key = f"cs_matrix_{timeframe}"
        cached = getattr(self, "_cs_cache", {}).get(cache_key)
        now_ts = time.time()
        if cached and (now_ts - cached.get("time", 0)) < 60:
            return cached.get("data", {})

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

            # Log return over lookback period
            start_price = float(df['close'].iloc[0])
            end_price = float(df['close'].iloc[-1])
            if start_price > 0 and end_price > 0:
                ret = float(np.log(end_price / start_price) * 100.0)
                returns_matrix[base].append(ret)
                returns_matrix[quote].append(-ret)

        raw_means = {}
        for curr, rets in returns_matrix.items():
            raw_means[curr] = float(np.mean(rets)) if rets else 0.0

        all_vals = list(raw_means.values())
        mean_all = float(np.mean(all_vals)) if all_vals else 0.0
        std_all = float(np.std(all_vals)) if all_vals else 1.0
        if std_all < 1e-4:
            std_all = 1.0

        strength_scores = {}
        for curr, m in raw_means.items():
            z_score = (m - mean_all) / std_all
            score = np.clip(z_score * 3.5, -10.0, 10.0)
            strength_scores[curr] = round(float(score), 2)

        if not hasattr(self, "_cs_cache"):
            self._cs_cache = {}
        self._cs_cache[cache_key] = {"time": now_ts, "data": strength_scores}

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

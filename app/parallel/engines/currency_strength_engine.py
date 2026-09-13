import time
import logging
import numpy as np
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.engines.currency_strength import CurrencyStrengthEngine

logger = logging.getLogger(__name__)

class ParallelCurrencyStrengthEngine(BaseAnalysisEngine):
    def __init__(self, provider=None, enabled: bool = True):
        super().__init__(name="CurrencyStrength", enabled=enabled, timeout_seconds=3.0)
        self.cs_engine = CurrencyStrengthEngine(provider=provider)

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            base = snapshot.base_currency
            quote = snapshot.quote_currency
            asset_class = getattr(snapshot, "asset_class", "FOREX").upper()

            # Currency strength matrix strictly applies to fiat Forex pairs
            from app.config.constants import MAJOR_CURRENCIES
            if asset_class != "FOREX" or base not in MAJOR_CURRENCIES or quote not in MAJOR_CURRENCIES:
                return AnalysisResult(
                    engine_name=self.name,
                    status="UNAVAILABLE",
                    score=50.0,
                    direction="NEUTRAL",
                    confidence=0.0,
                    evidence=[f"Currency Strength matrix skipped: {base}/{quote} ({asset_class}) is not a fiat cross"],
                    contradictions=[],
                    metrics={
                        "base_currency": base,
                        "quote_currency": quote,
                        "asset_class": asset_class,
                        "applicable": False
                    },
                    latency_ms=(time.perf_counter() - start) * 1000.0
                )

            if snapshot.candles is not None and len(snapshot.candles) >= 5:
                # Point-in-time momentum calculation across lookback window
                lookback = min(15, len(snapshot.candles) - 1)
                start_p = float(snapshot.candles['close'].iloc[-lookback])
                end_p = float(snapshot.candles['close'].iloc[-1])
                ret = ((end_p - start_p) / start_p * 100.0) if start_p > 0 else 0.0
                diff = float(np.clip(ret * 2.5, -10.0, 10.0))
                base_score = round(diff / 2.0, 2)
                quote_score = round(-diff / 2.0, 2)
            else:
                scores = self.cs_engine.calculate_currency_strength(timeframe="1H")
                base_score = scores.get(base, 0.0)
                quote_score = scores.get(quote, 0.0)
                diff = base_score - quote_score
            score = min(98.0, 50.0 + (abs(diff) * 6.0))
            direction = "LONG" if diff > 0 else ("SHORT" if diff < 0 else "NEUTRAL")

            evidence = []
            contradictions = []

            if abs(diff) >= 3.0:
                evidence.append(f"Strong Currency Divergence: {base} ({base_score:+.2f}) vs {quote} ({quote_score:+.2f}) -> Diff: {diff:+.2f}")
            elif abs(diff) >= 1.0:
                evidence.append(f"Moderate Currency Difference: {base} ({base_score:+.2f}) vs {quote} ({quote_score:+.2f})")
            else:
                contradictions.append(f"Weak currency strength differential ({diff:+.2f}) indicates potential chop")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=min(1.0, score / 100.0),
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "base_currency": base,
                    "quote_currency": quote,
                    "base_strength": base_score,
                    "quote_strength": quote_score,
                    "strength_diff": diff
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelCurrencyStrengthEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

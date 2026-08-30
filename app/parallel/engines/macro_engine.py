import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.engines.macro_engine import MacroYieldEngine

logger = logging.getLogger(__name__)

class ParallelMacroEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="MacroAnalysis", enabled=enabled, timeout_seconds=3.0)
        self.macro_engine = MacroYieldEngine()

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            base = snapshot.base_currency
            quote = snapshot.quote_currency

            res = self.macro_engine.fetch_macro_state(base_currency=base, quote_currency=quote)
            score = float(res.get("macro_score", 50.0))
            dxy_bias = res.get("dxy_bias", "NEUTRAL")
            rate_diff = float(res.get("rate_diff", 0.0))

            usd_is_bullish = ("BULLISH" in dxy_bias)
            usd_is_bearish = ("BEARISH" in dxy_bias)

            evidence = []
            contradictions = []

            if base == "USD":
                direction = "LONG" if usd_is_bullish else ("SHORT" if usd_is_bearish else "NEUTRAL")
                evidence.append(f"Macro DXY Bias: {dxy_bias} (Yield 10Y: {res.get('us10y_yield', 0.0):.2f}%, 2s10s: {res.get('yield_curve_2s10s', 0.0):.2f}%)")
            elif quote == "USD":
                direction = "SHORT" if usd_is_bullish else ("LONG" if usd_is_bearish else "NEUTRAL")
                evidence.append(f"Macro DXY Bias: {dxy_bias} (Yield 10Y: {res.get('us10y_yield', 0.0):.2f}%, 2s10s: {res.get('yield_curve_2s10s', 0.0):.2f}%)")
            else:
                # Non-USD crosses: evaluate central bank interest rate differential
                if rate_diff >= 1.0:
                    direction = "LONG"
                    evidence.append(f"Central Bank Rate Differential favors {base} (+{rate_diff:.2f}% over {quote})")
                elif rate_diff <= -1.0:
                    direction = "SHORT"
                    evidence.append(f"Central Bank Rate Differential favors {quote} (+{abs(rate_diff):.2f}% over {base})")
                else:
                    direction = "NEUTRAL"
                    evidence.append(f"Neutral Rate Differential ({base} vs {quote}: {rate_diff:+.2f}%)")

            if abs(rate_diff) >= 0.5:
                evidence.append(f"Policy Rates: {base} ({res.get('base_rate')}%) vs {quote} ({res.get('quote_rate')}%)")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=0.75,
                evidence=evidence,
                contradictions=contradictions,
                metrics=res,
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelMacroEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

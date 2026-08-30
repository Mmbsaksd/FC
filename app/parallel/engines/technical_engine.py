import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.engines.technical_engine import TechnicalAnalysisEngine

logger = logging.getLogger(__name__)

class ParallelTechnicalEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="TechnicalAnalysis", enabled=enabled, timeout_seconds=3.0)

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            df = snapshot.candles
            if df is None or len(df) < 20:
                return AnalysisResult(
                    engine_name=self.name,
                    status="UNAVAILABLE",
                    score=50.0,
                    direction="NEUTRAL",
                    confidence=0.5,
                    evidence=[],
                    contradictions=["Insufficient candle history"],
                    latency_ms=(time.perf_counter() - start) * 1000.0
                )

            eval_res = TechnicalAnalysisEngine.evaluate_technical_score(df)
            score = float(eval_res.get("score", 50.0))
            direction = eval_res.get("direction", "NEUTRAL")
            setup_type = eval_res.get("setup_type", "NO_SETUP")

            evidence = []
            contradictions = []

            rsi = eval_res.get("rsi", 50.0)
            adx = eval_res.get("adx", 20.0)

            if direction == "LONG":
                evidence.append(f"Technical score {score:.1f}/100 supports LONG ({setup_type})")
                if rsi < 70:
                    evidence.append(f"RSI at {rsi:.1f} shows bullish room")
                else:
                    contradictions.append(f"RSI elevated at {rsi:.1f} (overbought risk)")
                if adx > 25:
                    evidence.append(f"Strong trend momentum (ADX: {adx:.1f})")
            elif direction == "SHORT":
                evidence.append(f"Technical score {score:.1f}/100 supports SHORT ({setup_type})")
                if rsi > 30:
                    evidence.append(f"RSI at {rsi:.1f} shows bearish room")
                else:
                    contradictions.append(f"RSI low at {rsi:.1f} (oversold risk)")
                if adx > 25:
                    evidence.append(f"Strong trend momentum (ADX: {adx:.1f})")
            else:
                contradictions.append("Technical indicators reflect neutral/choppy condition")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=min(1.0, score / 100.0),
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "rsi": rsi,
                    "adx": adx,
                    "setup_type": setup_type,
                    "atr": eval_res.get("atr", 0.0)
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelTechnicalEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

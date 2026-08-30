import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.engines.fundamental_engine import FundamentalAnalysisEngine

logger = logging.getLogger(__name__)

class ParallelFundamentalEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="FundamentalAnalysis", enabled=enabled, timeout_seconds=3.0)
        self.fundamental_engine = FundamentalAnalysisEngine()

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            res = self.fundamental_engine.calculate_fundamental_score(snapshot.base_currency, snapshot.quote_currency)
            score = float(res.get("score", 50.0))
            direction = res.get("bias", "NEUTRAL")

            evidence = []
            contradictions = []

            events = res.get("upcoming_high_impact_events", 0)
            if events > 0:
                contradictions.append(f"Upcoming high-impact news event detected ({events} event in queue)")
            else:
                evidence.append("No high-impact economic releases scheduled in next 2 hours")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=0.7,
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "event_risk": events > 0,
                    "calendar_score": score
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelFundamentalEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

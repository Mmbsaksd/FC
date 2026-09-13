import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult

logger = logging.getLogger(__name__)

class ParallelRegimeEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="MarketRegime", enabled=enabled, timeout_seconds=3.0)

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            df = snapshot.candles
            if df is None or len(df) < 20:
                regime = "NORMAL_TREND"
                volatility = "MEDIUM"
            else:
                high_low_range = (df['high'] - df['low']).mean()
                close_mean = df['close'].mean()
                norm_vol = (high_low_range / close_mean) * 100.0

                asset_class = getattr(snapshot, "asset_class", "FOREX").upper()
                if snapshot.is_crypto:
                    asset_class = "CRYPTO"

                # Asset-calibrated volatility thresholds
                if asset_class == "CRYPTO":
                    low_thresh, high_thresh = 0.80, 2.50
                elif asset_class == "COMMODITY":
                    low_thresh, high_thresh = 0.30, 1.00
                else:  # FOREX
                    low_thresh, high_thresh = 0.12, 0.35

                if norm_vol > high_thresh:
                    regime = "HIGH_VOLATILITY_EXPANSION"
                    volatility = "HIGH"
                elif norm_vol < low_thresh:
                    regime = "LOW_VOLATILITY_CONSOLIDATION"
                    volatility = "LOW"
                else:
                    regime = "TRENDING_MOMENTUM"
                    volatility = "MEDIUM"

            evidence = [f"Market Regime classified as: {regime} (Volatility: {volatility})"]
            contradictions = []

            if volatility == "HIGH":
                contradictions.append("High volatility expansion increases stop-loss slippage risk")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=75.0 if volatility != "HIGH" else 60.0,
                direction="NEUTRAL",
                confidence=0.8,
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "regime": regime,
                    "volatility_level": volatility
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelRegimeEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

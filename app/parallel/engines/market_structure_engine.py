import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult

logger = logging.getLogger(__name__)

class ParallelMarketStructureEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="MarketStructure", enabled=enabled, timeout_seconds=3.0)

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
                    latency_ms=(time.perf_counter() - start) * 1000.0
                )

            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            n = len(df)

            # Detect Fractal Swing Points (5-bar window: central bar is highest/lowest)
            swing_highs = []
            swing_lows = []

            for i in range(2, n - 2):
                if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]:
                    swing_highs.append((i, float(highs[i])))
                if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1] and lows[i] <= lows[i+2]:
                    swing_lows.append((i, float(lows[i])))

            current_close = float(closes[-1])
            prev_close = float(closes[-2]) if len(closes) > 1 else current_close
            evidence = []
            contradictions = []
            direction = "NEUTRAL"
            score = 50.0

            higher_high = False
            higher_low = False
            lower_high = False
            lower_low = False
            bos_detected = False
            choch_detected = False

            if len(swing_highs) >= 2:
                last_sh = swing_highs[-1][1]
                prev_sh = swing_highs[-2][1]
                higher_high = last_sh > prev_sh
                lower_high = last_sh < prev_sh

                # Confirmed Break of Structure (BOS) Long: candle close sustained above swing high
                if higher_high and current_close > last_sh:
                    bos_detected = True
                    evidence.append(f"Confirmed Bullish Break of Structure (BOS) above swing high {last_sh:.5f}")
                # Confirmed Change of Character (CHoCH) Long: close breaks last swing high after lower high
                elif lower_high and current_close > last_sh:
                    choch_detected = True
                    evidence.append(f"Confirmed Bullish Change of Character (CHoCH) breaking {last_sh:.5f}")

            if len(swing_lows) >= 2:
                last_sl = swing_lows[-1][1]
                prev_sl = swing_lows[-2][1]
                higher_low = last_sl > prev_sl
                lower_low = last_sl < prev_sl

                # Confirmed Break of Structure (BOS) Short: candle close sustained below swing low
                if lower_low and current_close < last_sl:
                    bos_detected = True
                    evidence.append(f"Confirmed Bearish Break of Structure (BOS) below swing low {last_sl:.5f}")
                # Confirmed Change of Character (CHoCH) Short: close breaks last swing low after higher low
                elif higher_low and current_close < last_sl:
                    choch_detected = True
                    evidence.append(f"Confirmed Bearish Change of Character (CHoCH) breaking {last_sl:.5f}")

            # Multi-Swing Trend Structure Evaluation
            if higher_high and higher_low:
                direction = "LONG"
                score = 88.0 if (bos_detected or choch_detected) else 80.0
                evidence.append("Bullish Market Structure: Higher Highs & Higher Lows confirmed")
            elif lower_high and lower_low:
                direction = "SHORT"
                score = 88.0 if (bos_detected or choch_detected) else 80.0
                evidence.append("Bearish Market Structure: Lower Highs & Lower Lows confirmed")
            elif choch_detected:
                direction = "LONG" if current_close > swing_highs[-1][1] else "SHORT"
                score = 82.0
            elif higher_high or higher_low:
                direction = "LONG"
                score = 68.0
                evidence.append("Bullish Market Expansion / Trend Transition in progress")
            elif lower_high or lower_low:
                direction = "SHORT"
                score = 68.0
                evidence.append("Bearish Market Expansion / Trend Transition in progress")
            else:
                contradictions.append("Market Structure reflects horizontal consolidation range")
                score = 50.0

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=min(1.0, score / 100.0),
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "higher_high": bool(higher_high),
                    "higher_low": bool(higher_low),
                    "lower_high": bool(lower_high),
                    "lower_low": bool(lower_low),
                    "bos_detected": bool(bos_detected),
                    "choch_detected": bool(choch_detected),
                    "total_swing_highs": len(swing_highs),
                    "total_swing_lows": len(swing_lows)
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelMarketStructureEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult

logger = logging.getLogger(__name__)

class ParallelCandleEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="CandleStructure", enabled=enabled, timeout_seconds=3.0)

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            df = snapshot.candles
            if df is None or len(df) < 5:
                return AnalysisResult(
                    engine_name=self.name,
                    status="UNAVAILABLE",
                    score=50.0,
                    direction="NEUTRAL",
                    confidence=0.5,
                    latency_ms=(time.perf_counter() - start) * 1000.0
                )

            last_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            prev2_candle = df.iloc[-3] if len(df) >= 3 else prev_candle

            o, h, l, c = float(last_candle['open']), float(last_candle['high']), float(last_candle['low']), float(last_candle['close'])
            p_o, p_h, p_l, p_c = float(prev_candle['open']), float(prev_candle['high']), float(prev_candle['low']), float(prev_candle['close'])
            p2_o, p2_h, p2_l, p2_c = float(prev2_candle['open']), float(prev2_candle['high']), float(prev2_candle['low']), float(prev2_candle['close'])

            body_size = abs(c - o)
            total_range = max(0.00001, h - l)
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l

            body_ratio = body_size / total_range
            upper_wick_ratio = upper_wick / total_range
            lower_wick_ratio = lower_wick / total_range

            # Asset-aware price tolerance (half a pip/tick for the instrument)
            pip_tol = max(1e-5, getattr(snapshot, "pip_size", 0.0001) * 0.5)

            patterns_detected = []
            bullish_votes = 0
            bearish_votes = 0
            score = 50.0

            # Prior 2-bar trend bias
            prior_downtrend = (p_c < p2_c) or (p_c < p_o and p2_c < p2_o)
            prior_uptrend = (p_c > p2_c) or (p_c > p_o and p2_c > p2_o)

            # 1. 3-Candle Morning Star (Bullish Reversal)
            if p2_c < p2_o and (abs(p_c - p_o) / max(0.00001, p_h - p_l)) < 0.35 and c > o and c > (p2_o + p2_c) / 2.0:
                patterns_detected.append("Morning Star 3-Candle Bullish Reversal")
                bullish_votes += 3
                score = max(score, 88.0)

            # 2. 3-Candle Evening Star (Bearish Reversal)
            if p2_c > p2_o and (abs(p_c - p_o) / max(0.00001, p_h - p_l)) < 0.35 and c < o and c < (p2_o + p2_c) / 2.0:
                patterns_detected.append("Evening Star 3-Candle Bearish Reversal")
                bearish_votes += 3
                score = max(score, 88.0)

            # 3. Real Body Bullish Engulfing
            if p_c < p_o and c > o and o <= (p_c + pip_tol) and c >= (p_o - pip_tol) and body_size > abs(p_c - p_o):
                patterns_detected.append("Bullish Engulfing (Real Body Engulfing)")
                bullish_votes += 2
                score = max(score, 85.0)

            # 4. Real Body Bearish Engulfing
            if p_c > p_o and c < o and o >= (p_c - pip_tol) and c <= (p_o + pip_tol) and body_size > abs(p_c - p_o):
                patterns_detected.append("Bearish Engulfing (Real Body Engulfing)")
                bearish_votes += 2
                score = max(score, 85.0)

            # 5. Bullish Pinbar / Hammer / Lower Wick Rejection (With Downtrend Context)
            if lower_wick_ratio >= 0.55 and upper_wick_ratio <= 0.25:
                context_tag = " (After Pullback)" if prior_downtrend else ""
                patterns_detected.append(f"Bullish Pinbar / Hammer Rejection{context_tag} ({lower_wick_ratio*100:.0f}% lower wick)")
                bullish_votes += (2 if prior_downtrend else 1)
                score = max(score, 84.0 if prior_downtrend else 72.0)

            # 6. Bearish Pinbar / Shooting Star / Upper Wick Rejection (With Uptrend Context)
            if upper_wick_ratio >= 0.55 and lower_wick_ratio <= 0.25:
                context_tag = " (After Rally)" if prior_uptrend else ""
                patterns_detected.append(f"Bearish Pinbar / Shooting Star Rejection{context_tag} ({upper_wick_ratio*100:.0f}% upper wick)")
                bearish_votes += (2 if prior_uptrend else 1)
                score = max(score, 84.0 if prior_uptrend else 72.0)

            # 7. Inside Bar (Market Volatility Compression)
            if h < p_h and l > p_l:
                patterns_detected.append("Inside Bar (Market Volatility Compression)")
                if p_c > p_o:
                    bullish_votes += 1
                else:
                    bearish_votes += 1
                score = max(score, 68.0)

            # 8. Outside Bar (Volatility Expansion)
            if h > p_h and l < p_l:
                patterns_detected.append("Outside Bar (Market Volatility Expansion)")
                if c > o:
                    bullish_votes += 1
                else:
                    bearish_votes += 1
                score = max(score, 72.0)

            # 9. Strong Momentum Marubozu
            if body_ratio >= 0.75:
                dir_label = "Bullish" if c > o else "Bearish"
                patterns_detected.append(f"Strong {dir_label} Momentum Marubozu ({body_ratio*100:.0f}% body)")
                if c > o:
                    bullish_votes += 2
                else:
                    bearish_votes += 2
                score = max(score, 76.0)

            # 10. Doji Indecision
            if body_ratio <= 0.10 and not patterns_detected:
                patterns_detected.append(f"Doji Candle of Indecision ({body_ratio*100:.0f}% body)")
                score = 50.0

            # Determine dominant candle direction
            if bullish_votes > bearish_votes:
                direction = "LONG"
            elif bearish_votes > bullish_votes:
                direction = "SHORT"
            else:
                direction = "NEUTRAL"
                score = 50.0

            evidence = [f"Pattern: {p}" for p in patterns_detected]
            contradictions = []

            if direction == "NEUTRAL" and not patterns_detected:
                evidence.append("Candle structure reflects balanced/normal price action")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=min(1.0, score / 100.0),
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "body_ratio": round(body_ratio, 2),
                    "upper_wick_ratio": round(upper_wick_ratio, 2),
                    "lower_wick_ratio": round(lower_wick_ratio, 2),
                    "patterns_detected": patterns_detected
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelCandleEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

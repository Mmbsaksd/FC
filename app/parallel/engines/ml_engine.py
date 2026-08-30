import time
import logging
import pandas as pd
import numpy as np
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.ml.classifier import OpportunityMLClassifier

logger = logging.getLogger(__name__)

class ParallelMLEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="MLPrediction", enabled=enabled, timeout_seconds=3.0)
        self.ml_classifier = OpportunityMLClassifier()

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            df = snapshot.candles
            if df is None or len(df) < 14:
                return AnalysisResult(
                    engine_name=self.name,
                    status="UNAVAILABLE",
                    score=50.0,
                    direction="NEUTRAL",
                    confidence=0.5,
                    latency_ms=(time.perf_counter() - start) * 1000.0
                )

            # Compute live technical features from snapshot candle series
            close = df['close']
            high = df['high']
            low = df['low']
            last_close = float(close.iloc[-1])

            # Live EMA(20) & EMA(50)
            ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])

            # Live RSI(14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().iloc[-1]
            avg_loss = loss.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().iloc[-1]
            rs = avg_gain / (avg_loss if avg_loss > 0 else 1e-5)
            live_rsi = float(100.0 - (100.0 / (1.0 + rs)))

            # Live ADX(14)
            tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
            atr = tr.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().iloc[-1]
            up_move = high.diff()
            down_move = -low.diff()
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            smooth_plus = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().iloc[-1]
            smooth_minus = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().iloc[-1]
            plus_di = 100.0 * (smooth_plus / (atr if atr > 0 else 1e-5))
            minus_di = 100.0 * (smooth_minus / (atr if atr > 0 else 1e-5))
            live_adx = float((100.0 * abs(plus_di - minus_di) / max(1e-5, plus_di + minus_di)))

            # Determine dynamic direction
            if last_close > ema20 and ema20 >= ema50:
                direction = "LONG"
                tech_score = 75.0 + (10.0 if live_adx > 25 else 0.0)
            elif last_close < ema20 and ema20 <= ema50:
                direction = "SHORT"
                tech_score = 75.0 + (10.0 if live_adx > 25 else 0.0)
            else:
                direction = "NEUTRAL"
                tech_score = 50.0

            # Calculate dynamic price momentum factor
            momentum_ret = float((last_close - float(close.iloc[0])) / float(close.iloc[0]) * 100.0) if len(close) > 0 else 0.0
            dynamic_strength = momentum_ret * 2.5

            # Construct dynamic live feature dict
            features = {
                "rsi": live_rsi,
                "adx": live_adx,
                "tech_score": tech_score,
                "strength_diff": dynamic_strength if direction != "NEUTRAL" else 0.0,
                "direction": direction
            }

            win_prob = self.ml_classifier.predict_probability(features)
            score = round(win_prob * 100.0, 2)

            evidence = []
            contradictions = []

            if win_prob >= 0.65:
                evidence.append(f"Calibrated Statistical Win Probability: {win_prob*100:.1f}% (RSI: {live_rsi:.1f}, ADX: {live_adx:.1f})")
            elif win_prob >= 0.52:
                evidence.append(f"Moderate Statistical Win Probability: {win_prob*100:.1f}% on dynamic momentum")
            else:
                contradictions.append(f"Statistical win probability at {win_prob*100:.1f}% indicates choppy/uncertain market structure")

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=win_prob,
                evidence=evidence,
                contradictions=contradictions,
                metrics={
                    "win_probability": win_prob,
                    "model_type": "Calibrated Statistical Factor Model",
                    "live_rsi": round(live_rsi, 2),
                    "live_adx": round(live_adx, 2),
                    "dynamic_momentum_score": round(dynamic_strength, 2)
                },
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelMLEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

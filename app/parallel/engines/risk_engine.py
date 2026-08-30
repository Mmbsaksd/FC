import time
import logging
from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.risk.risk_engine import RiskEngine

logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np

class ParallelRiskEngine(BaseAnalysisEngine):
    def __init__(self, enabled: bool = True):
        super().__init__(name="RiskMetrics", enabled=enabled, timeout_seconds=3.0)

    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        start = time.perf_counter()
        try:
            df = snapshot.candles
            if df is None or len(df) < 14:
                atr = max(snapshot.price * 0.002, snapshot.pip_size * 15.0)
                direction = "NEUTRAL"
            else:
                high = df['high']
                low = df['low']
                close = df['close']
                tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
                atr = float(tr.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().iloc[-1])
                ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
                last_price = float(close.iloc[-1])
                direction = "LONG" if last_price >= ema20 else "SHORT"

            # Compute risk parameters matching direction and provide dual-bracket metrics
            calc_direction = direction if direction in ["LONG", "SHORT"] else "LONG"
            risk_params = RiskEngine.calculate_trade_parameters(
                symbol=snapshot.symbol,
                direction=calc_direction,
                current_price=snapshot.price,
                atr=atr,
                pip_size=snapshot.pip_size
            )
            long_params = RiskEngine.calculate_trade_parameters(
                symbol=snapshot.symbol,
                direction="LONG",
                current_price=snapshot.price,
                atr=atr,
                pip_size=snapshot.pip_size
            )
            short_params = RiskEngine.calculate_trade_parameters(
                symbol=snapshot.symbol,
                direction="SHORT",
                current_price=snapshot.price,
                atr=atr,
                pip_size=snapshot.pip_size
            )

            valid = risk_params.get("valid", False)
            rr = float(risk_params.get("risk_reward", 2.0))

            evidence = []
            contradictions = []

            if valid and rr >= 2.0:
                evidence.append(f"Favorable Risk/Reward 1:{rr:.1f} ({calc_direction}) - SL: {risk_params['stop_loss']}, TP1: {risk_params['take_profit_1']}")
                score = min(95.0, 50.0 + (rr * 15.0))
            else:
                contradictions.append(f"Risk/Reward 1:{rr:.1f} below minimum required 1:2.0")
                score = 45.0

            metrics = {
                **risk_params,
                "atr": atr,
                "long_parameters": long_params,
                "short_parameters": short_params
            }

            return AnalysisResult(
                engine_name=self.name,
                status="SUCCESS",
                score=score,
                direction=direction,
                confidence=0.85,
                evidence=evidence,
                contradictions=contradictions,
                metrics=metrics,
                latency_ms=(time.perf_counter() - start) * 1000.0
            )
        except Exception as e:
            logger.error(f"Error in ParallelRiskEngine: {e}")
            return AnalysisResult(
                engine_name=self.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000.0
            )

import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class DeterministicGeometricStructureVerifier:
    """
    Deterministic Geometric & Price Structure Verifier.
    Performs deterministic mathematical verification of price structure, support/resistance levels,
    and 30-bar candle geometry.
    NOTE: This is a deterministic rule-based structural verifier, NOT an image-based computer vision model.
    It generates structured price-chart context for multi-modal and tabular evaluation.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def generate_chart_payload(
        self,
        snapshot,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        take_profit_2: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Builds standardized deterministic chart payload containing recent candles,
        trend metrics, key swing points, and entry/SL/TP coordinates.
        """
        raw_candles = getattr(snapshot, "candles", None)
        df = raw_candles if isinstance(raw_candles, pd.DataFrame) and not raw_candles.empty else None
        candle_data = []

        trend_state = "UNKNOWN"
        last_swing_high = entry
        last_swing_low = entry

        if df is not None and len(df) >= 5:
            tail = df.tail(30)
            for idx, row in tail.iterrows():
                candle_data.append({
                    "time": str(row.get("time", idx)),
                    "open": round(float(row.get("open", 0.0)), 5),
                    "high": round(float(row.get("high", 0.0)), 5),
                    "low": round(float(row.get("low", 0.0)), 5),
                    "close": round(float(row.get("close", 0.0)), 5),
                    "volume": float(row.get("volume", 0.0))
                })

            c = tail['close'].values
            if len(c) >= 20:
                ema20 = float(tail['close'].ewm(span=20, adjust=False).mean().iloc[-1])
                trend_state = "BULLISH" if c[-1] > ema20 else "BEARISH"

            last_swing_high = round(float(tail['high'].max()), 5)
            last_swing_low = round(float(tail['low'].min()), 5)

        tp2_val = take_profit_2 or round(entry + (take_profit - entry) * 1.5, 5)

        return {
            "symbol": snapshot.symbol_name,
            "direction": direction,
            "current_price": snapshot.price,
            "entry_price": entry,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit,
            "take_profit_2": tp2_val,
            "timeframe": snapshot.timeframe,
            "candle_count": len(candle_data),
            "candles": candle_data,
            "trend_state": trend_state,
            "swing_high": last_swing_high,
            "swing_low": last_swing_low,
            "key_levels": {
                "support": round(min(last_swing_low, entry - (abs(entry - stop_loss) * 1.2)), 5),
                "resistance": round(max(last_swing_high, entry + (abs(take_profit - entry) * 1.1)), 5)
            },
            "verification_method": "DETERMINISTIC_GEOMETRIC_STRUCTURE_VALIDATION",
            "has_rendered_image_file": False
        }

    def verify_candidate_setup(
        self,
        snapshot,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict[str, Any]:
        """
        Performs geometric structure confirmation relative to recent 20-bar baseline.
        """
        if not self.enabled:
            return {
                "status": "SKIPPED",
                "verification_method": "DETERMINISTIC_GEOMETRIC",
                "visual_direction": direction,
                "structure_confirmation": True,
                "contradictions": [],
                "confidence": 0.70
            }

        try:
            df = snapshot.candles
            if df is None or len(df) < 10:
                return {
                    "status": "UNAVAILABLE",
                    "verification_method": "DETERMINISTIC_GEOMETRIC",
                    "visual_direction": direction,
                    "confidence": 0.50,
                    "contradictions": ["Insufficient candle history for geometric validation"]
                }

            c = df['close'].values
            baseline = float(df['close'].tail(20).mean())
            is_structurally_aligned = (c[-1] >= baseline) if direction == "LONG" else (c[-1] <= baseline)

            contradictions = []
            if not is_structurally_aligned:
                contradictions.append(f"Price action ({c[-1]:.5f}) diverges from 20-period baseline ({baseline:.5f})")

            status = "CONFIRMED" if len(contradictions) == 0 else "AMBIGUOUS"

            chart_payload = self.generate_chart_payload(snapshot, direction, entry, stop_loss, take_profit)

            return {
                "status": status,
                "verification_method": "DETERMINISTIC_GEOMETRIC_STRUCTURE_VALIDATION",
                "visual_direction": direction,
                "structure_confirmation": is_structurally_aligned,
                "contradictions": contradictions,
                "confidence": 0.82 if status == "CONFIRMED" else 0.55,
                "chart_context": chart_payload
            }
        except Exception as e:
            logger.error(f"Error in geometric structure verifier: {e}")
            return {
                "status": "ERROR",
                "verification_method": "DETERMINISTIC_GEOMETRIC",
                "visual_direction": direction,
                "confidence": 0.50,
                "contradictions": [str(e)]
            }

# Backward compatibility alias
VisualMarketVerifier = DeterministicGeometricStructureVerifier
visual_verifier = DeterministicGeometricStructureVerifier()

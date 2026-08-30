import logging
from typing import Dict, Any, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

class DataValidator:
    """
    Data Quality Engine evaluating freshness, price jump anomalies, zero values, and spread bounds.
    Memory Footprint: Negligible (< 1 MB).
    """

    @staticmethod
    def validate_ohlcv(df: pd.DataFrame, max_latency_seconds: int = 3600, is_crypto: bool = False) -> Tuple[str, float, str]:
        """
        Validates OHLCV DataFrame.
        Returns (status, quality_score, reason)
        Status: 'GOOD', 'DEGRADED', 'STALE', 'INVALID'
        """
        if df is None or df.empty:
            return "INVALID", 0.0, "Empty DataFrame"

        required_cols = {'timestamp', 'open', 'high', 'low', 'close'}
        if not required_cols.issubset(df.columns):
            return "INVALID", 0.0, f"Missing required columns: {required_cols - set(df.columns)}"

        # Null check
        null_count = df[list(required_cols)].isnull().sum().sum()
        if null_count > 0:
            return "INVALID", 0.0, f"Contains {null_count} null values"

        # Timestamp Freshness
        try:
            last_timestamp = pd.to_datetime(df['timestamp'].iloc[-1])
            if last_timestamp.tzinfo is None:
                last_timestamp = last_timestamp.tz_localize('UTC')
            
            now = pd.Timestamp.now(tz='UTC')
            latency = (now - last_timestamp).total_seconds()

            # Weekend Market Close Check (Markets closed Fri 21:00 UTC - Sun 21:00 UTC for FX, Crypto is 24/7)
            is_weekend = (now.weekday() == 5) or (now.weekday() == 6) or (now.weekday() == 0 and now.hour < 1)

            if latency > max_latency_seconds * 3:
                if is_weekend and not is_crypto:
                    return "GOOD", 85.0, f"Weekend market closure (Last candle: {last_timestamp})"
                return "STALE", 30.0, f"Data stale by {latency / 3600:.1f} hours"
            elif latency > max_latency_seconds:
                return "DEGRADED", 70.0, f"Minor latency of {latency / 60:.1f} minutes"
        except Exception as e:
            return "DEGRADED", 60.0, f"Timestamp parsing note: {e}"

        # Abnormal Price Jump Check ( > 10% jump between consecutive candles)
        price_pct_change = df['close'].pct_change().abs()
        max_jump = price_pct_change.max()
        if max_jump > 0.10:
            return "DEGRADED", 65.0, f"Abnormal single-candle price jump detected: {max_jump*100:.1f}%"

        return "GOOD", 100.0, "Data valid and fresh"

    @staticmethod
    def validate_quote(quote: Dict[str, Any]) -> Tuple[str, float]:
        if not quote or quote.get("last", 0.0) <= 0.0:
            return "INVALID", 0.0

        spread = quote.get("spread", 0.0)
        last = quote.get("last", 1.0)
        spread_pct = (spread / last) * 100.0 if last > 0 else 0.0

        if spread_pct > 1.0: # > 1% spread is abnormal
            return "DEGRADED", 60.0

        return "GOOD", 100.0

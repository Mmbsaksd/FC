import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class TechnicalAnalysisEngine:
    """
    Computes technical indicators and market structure metrics.
    Optimized for low RAM consumption by working on sliced tail arrays.
    """

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates EMA(20, 50, 200), Wilder's RSI(14), True ATR(14), Wilder's ADX(14), and Bollinger Bands.
        """
        if df.empty or len(df) < 14:
            return df

        df = df.copy()
        close = df['close']
        high = df['high']
        low = df['low']

        # Exponential Moving Averages
        df['ema_20'] = close.ewm(span=20, adjust=False).mean()
        df['ema_50'] = close.ewm(span=50, adjust=False).mean()
        if len(df) >= 200:
            df['sma_200'] = close.rolling(window=200).mean()
        else:
            df['sma_200'] = np.nan

        # Wilder's Smoothed RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df['rsi_14'] = 100.0 - (100.0 / (1.0 + rs))
        df['rsi_14'] = df['rsi_14'].fillna(50.0)

        # True Range and Wilder's Smoothed ATR (14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr_14'] = tr.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().fillna(tr.rolling(14, min_periods=1).mean())

        # Wilder's Smoothed ADX (14)
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        atr_series = df['atr_14'].replace(0, 1e-5)
        smooth_plus_dm = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        smooth_minus_dm = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()

        plus_di = 100.0 * (smooth_plus_dm / atr_series)
        minus_di = 100.0 * (smooth_minus_dm / atr_series)
        di_sum = (plus_di + minus_di).replace(0, 1e-5)
        dx = 100.0 * (plus_di - minus_di).abs() / di_sum
        df['adx_14'] = dx.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean().fillna(20.0)

        # Bollinger Bands (20, 2.0) with population standard deviation (ddof=0)
        sma20 = close.rolling(20, min_periods=1).mean()
        std20 = close.rolling(20, min_periods=1).std(ddof=0).fillna(0)
        df['bb_upper'] = sma20 + (std20 * 2.0)
        df['bb_lower'] = sma20 - (std20 * 2.0)
        df['bb_bandwidth'] = ((df['bb_upper'] - df['bb_lower']) / sma20.replace(0, 1e-5)) * 100.0
        df['bb_percent'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower']).replace(0, 1e-5)

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Rate of Change Momentum (10)
        df['roc_10'] = close.pct_change(10).fillna(0) * 100.0

        # Donchian 10-period High/Low for genuine breakout detection
        df['donchian_high_10'] = high.rolling(10).max().shift(1)
        df['donchian_low_10'] = low.rolling(10).min().shift(1)

        return df

    @staticmethod
    def evaluate_technical_score(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates current technical state and outputs Technical Score (0-100) and Direction.
        """
        if df.empty or len(df) < 5:
            return {"score": 50.0, "direction": "NEUTRAL", "setup_type": "NONE"}

        df = TechnicalAnalysisEngine.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        score = 50.0
        direction = "NEUTRAL"
        setup_type = "RANGE"

        close = float(last['close'])
        ema20 = float(last['ema_20'])
        ema50 = float(last['ema_50'])
        sma200 = float(last['sma_200']) if not np.isnan(last['sma_200']) else None
        rsi = float(last['rsi_14'])
        adx = float(last['adx_14'])
        atr = float(last['atr_14'])
        bb_bandwidth = float(last.get('bb_bandwidth', 2.0))
        bb_percent = float(last.get('bb_percent', 0.5))
        macd_hist = float(last.get('macd_hist', 0.0))
        roc10 = float(last.get('roc_10', 0.0))
        donch_high = float(last.get('donchian_high_10', 0.0))
        donch_low = float(last.get('donchian_low_10', 0.0))

        # Bullish Signals (Non-overlapping)
        bullish_signals = 0
        if close > ema20: bullish_signals += 1
        if ema20 > ema50: bullish_signals += 1
        if sma200 is not None:
            if close > sma200: bullish_signals += 1
        else:
            if close > ema50: bullish_signals += 1
        if 50 <= rsi <= 68: bullish_signals += 1 # Non-overlapping bullish momentum
        if float(prev['close']) <= float(prev['ema_20']) and close > ema20: bullish_signals += 1 # Pullback bounce
        if bb_percent > 0.55: bullish_signals += 1 # Upper Bollinger zone
        if macd_hist > 0: bullish_signals += 1 # Positive MACD histogram
        if roc10 > 0.1: bullish_signals += 1 # Positive momentum ROC

        # Bearish Signals (Non-overlapping)
        bearish_signals = 0
        if close < ema20: bearish_signals += 1
        if ema20 < ema50: bearish_signals += 1
        if sma200 is not None:
            if close < sma200: bearish_signals += 1
        else:
            if close < ema50: bearish_signals += 1
        if 32 <= rsi <= 50: bearish_signals += 1 # Non-overlapping bearish momentum
        if float(prev['close']) >= float(prev['ema_20']) and close < ema20: bearish_signals += 1 # Pullback rejection
        if bb_percent < 0.45: bearish_signals += 1 # Lower Bollinger zone
        if macd_hist < 0: bearish_signals += 1 # Negative MACD histogram
        if roc10 < -0.1: bearish_signals += 1 # Negative momentum ROC

        # Determine Setup Type and Score
        if bullish_signals > bearish_signals and bullish_signals >= 4:
            direction = "LONG"
            trend_bonus = 10.0 if adx > 25 else (5.0 if adx > 20 else 0.0)
            score = min(96.0, 50.0 + (bullish_signals * 6.0) + trend_bonus)
            
            # Genuine setup classification
            if close > donch_high and donch_high > 0:
                setup_type = "DONCHIAN_BREAKOUT_LONG"
            elif bb_bandwidth > 3.0 and adx > 25:
                setup_type = "VOLATILITY_EXPANSION_LONG"
            elif abs(close - ema20) <= (atr * 0.5):
                setup_type = "TREND_PULLBACK_BOUNCE"
            else:
                setup_type = "MOMENTUM_CONTINUATION"

        elif bearish_signals > bullish_signals and bearish_signals >= 4:
            direction = "SHORT"
            trend_bonus = 10.0 if adx > 25 else (5.0 if adx > 20 else 0.0)
            score = min(96.0, 50.0 + (bearish_signals * 6.0) + trend_bonus)
            
            if close < donch_low and donch_low > 0:
                setup_type = "DONCHIAN_BREAKOUT_SHORT"
            elif bb_bandwidth > 3.0 and adx > 25:
                setup_type = "VOLATILITY_EXPANSION_SHORT"
            elif abs(close - ema20) <= (atr * 0.5):
                setup_type = "TREND_PULLBACK_REJECTION"
            else:
                setup_type = "MOMENTUM_CONTINUATION"

        return {
            "score": round(score, 2),
            "direction": direction,
            "setup_type": setup_type,
            "close": close,
            "atr": atr,
            "rsi": rsi,
            "adx": adx,
            "ema_20": ema20,
            "ema_50": ema50,
            "macd": round(float(last.get('macd', 0.0)), 5),
            "macd_hist": round(macd_hist, 5),
            "roc_10": round(roc10, 2),
            "bb_bandwidth": bb_bandwidth,
            "bb_percent": bb_percent
        }

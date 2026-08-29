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
        Calculates EMA(20, 50, 200), RSI(14), ATR(14), ADX(14), and Bollinger Bands.
        """
        if df.empty or len(df) < 20:
            return df

        df = df.copy()
        close = df['close']
        high = df['high']
        low = df['low']

        # Exponential Moving Averages
        df['ema_20'] = close.ewm(span=20, adjust=False).mean()
        df['ema_50'] = close.ewm(span=50, adjust=False).mean()
        df['sma_200'] = close.rolling(window=min(200, len(df)), min_periods=20).mean()

        # RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss.replace(0, np.nan))
        df['rsi_14'] = 100 - (100 / (1 + rs))
        df['rsi_14'] = df['rsi_14'].fillna(50)

        # ATR (14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(window=14, min_periods=1).mean()

        # ADX (14) Trend Strength Estimation
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        atr = df['atr_14'].replace(0, 1e-5)
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(14).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(14).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-5)
        df['adx_14'] = dx.rolling(14, min_periods=1).mean().fillna(20)

        # Bollinger Bands (20, 2.0)
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df['bb_upper'] = sma20 + (std20 * 2.0)
        df['bb_lower'] = sma20 - (std20 * 2.0)
        df['bb_bandwidth'] = (df['bb_upper'] - df['bb_lower']) / sma20.replace(0, 1e-5)

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

        close = last['close']
        ema20 = last['ema_20']
        ema50 = last['ema_50']
        sma200 = last['sma_200']
        rsi = last['rsi_14']
        adx = last['adx_14']
        atr = last['atr_14']

        # Bullish Conditions
        bullish_signals = 0
        if close > ema20: bullish_signals += 1
        if ema20 > ema50: bullish_signals += 1
        if close > sma200: bullish_signals += 1
        if 45 <= rsi <= 65: bullish_signals += 1 # Healthy momentum, not overbought
        if prev['close'] <= prev['ema_20'] and close > ema20: bullish_signals += 1 # Pullback bounce

        # Bearish Conditions
        bearish_signals = 0
        if close < ema20: bearish_signals += 1
        if ema20 < ema50: bearish_signals += 1
        if close < sma200: bearish_signals += 1
        if 35 <= rsi <= 55: bearish_signals += 1
        if prev['close'] >= prev['ema_20'] and close < ema20: bearish_signals += 1

        if bullish_signals > bearish_signals and bullish_signals >= 3:
            direction = "LONG"
            score = min(95.0, 50.0 + (bullish_signals * 9.0) + (10.0 if adx > 25 else 0.0))
            setup_type = "TREND_PULLBACK" if close <= ema20 * 1.002 else "BREAKOUT_CONTINUATION"

        elif bearish_signals > bullish_signals and bearish_signals >= 3:
            direction = "SHORT"
            score = min(95.0, 50.0 + (bearish_signals * 9.0) + (10.0 if adx > 25 else 0.0))
            setup_type = "TREND_PULLBACK" if close >= ema20 * 0.998 else "BREAKOUT_CONTINUATION"

        return {
            "score": round(score, 2),
            "direction": direction,
            "setup_type": setup_type,
            "close": float(close),
            "atr": float(atr),
            "rsi": float(rsi),
            "adx": float(adx),
            "ema_20": float(ema20),
            "ema_50": float(ema50)
        }

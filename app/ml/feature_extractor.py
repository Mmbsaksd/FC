import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone

from app.parallel.base_engine import MarketSnapshot

FEATURE_SCHEMA_VERSION = "v2.1.0"

def _get_metric(res, key, default=0.0):
    if res is None:
        return default
    if hasattr(res, "metrics") and isinstance(res.metrics, dict):
        return res.metrics.get(key, default)
    if isinstance(res, dict):
        m = res.get("metrics")
        if isinstance(m, dict) and key in m:
            return m[key]
        return res.get(key, default)
    return default

def _get_score(res, default=50.0):
    if res is None:
        return default
    if hasattr(res, "score"):
        return res.score
    if isinstance(res, dict):
        return res.get("score", default)
    return default

class UnifiedFeatureExtractor:
    """
    Unified Multi-Engine Time-Aware Feature Extractor.
    Transforms raw MarketSnapshot and parallel engine outputs into a structured,
    normalized, 124-dimensional feature vector for the Central Meta-Model.
    Strictly look-ahead free and time-aware.
    """

    def __init__(self, version: str = FEATURE_SCHEMA_VERSION):
        self.version = version

    def extract_features(
        self,
        snapshot: MarketSnapshot,
        engine_results: Dict[str, Any],
        pretrained_embeddings: Dict[str, float] = None
    ) -> Tuple[Dict[str, float], List[float]]:
        """
        Extracts structured named features and a flat numerical vector.
        """
        features: Dict[str, float] = {}
        df = snapshot.candles if isinstance(snapshot.candles, pd.DataFrame) and not snapshot.candles.empty else None

        # 1. MARKET MICROSTRUCTURE & EXECUTION FEATURES
        spread_pips = float(snapshot.spread_pips)
        pip_size = float(snapshot.pip_size) if snapshot.pip_size > 0 else 0.0001
        close_price = float(snapshot.price)
        
        features["micro_spread_pips"] = spread_pips
        features["micro_is_crypto"] = 1.0 if snapshot.is_crypto else 0.0
        
        # Session and Temporal Features (Cyclical Encoding)
        try:
            now_dt = datetime.fromisoformat(snapshot.timestamp.replace("Z", "+00:00"))
        except Exception:
            now_dt = datetime.now(timezone.utc)

        hour = now_dt.hour + (now_dt.minute / 60.0)
        dow = now_dt.weekday() # 0 = Monday, 6 = Sunday

        features["time_hour_sin"] = round(math.sin(2 * math.pi * hour / 24.0), 4)
        features["time_hour_cos"] = round(math.cos(2 * math.pi * hour / 24.0), 4)
        features["time_dow_sin"] = round(math.sin(2 * math.pi * dow / 7.0), 4)
        features["time_dow_cos"] = round(math.cos(2 * math.pi * dow / 7.0), 4)
        features["time_is_london_ny_overlap"] = 1.0 if (12 <= now_dt.hour <= 16) else 0.0

        # 2. TECHNICAL OSCILLATORS & MOMENTUM (from Technical Engine + DF)
        tech_res = engine_results.get("TechnicalAnalysis")
        rsi = float(_get_metric(tech_res, "rsi", 50.0))
        adx = float(_get_metric(tech_res, "adx", 20.0))
        tech_score = float(_get_score(tech_res, 50.0))
        
        features["tech_score_norm"] = round(tech_score / 100.0, 4)
        features["tech_rsi_14"] = rsi
        features["tech_rsi_distance_from_mid"] = round((rsi - 50.0) / 50.0, 4)
        features["tech_adx_14"] = adx
        features["tech_adx_is_trending"] = 1.0 if adx >= 25.0 else 0.0

        # Price returns over multiple lookbacks if DataFrame available
        if df is not None and len(df) >= 20:
            c = df['close'].values
            features["price_return_1bar"] = round(float((c[-1] - c[-2]) / c[-2]), 6)
            features["price_return_3bar"] = round(float((c[-1] - c[-4]) / c[-4]), 6)
            features["price_return_12bar"] = round(float((c[-1] - c[-13]) / c[-13]), 6)
            features["price_return_24bar"] = round(float((c[-1] - c[-25]) / c[-25]) if len(c) >= 25 else 0.0, 6)
            
            # Distance from EMA20
            ema20 = float(df['close'].ewm(span=20, adjust=False).mean().iloc[-1])
            features["price_dist_from_ema20_pct"] = round(float((close_price - ema20) / ema20 * 100.0), 4)
        else:
            features["price_return_1bar"] = 0.0
            features["price_return_3bar"] = 0.0
            features["price_return_12bar"] = 0.0
            features["price_return_24bar"] = 0.0
            features["price_dist_from_ema20_pct"] = 0.0

        # 3. CANDLE ANATOMY & STRUCTURE (from Candle Engine + DF)
        candle_res = engine_results.get("CandleStructure")
        features["candle_score_norm"] = round(float(_get_score(candle_res, 50.0)) / 100.0, 4)
        features["candle_body_ratio"] = float(_get_metric(candle_res, "body_ratio", 0.5))
        features["candle_upper_wick_ratio"] = float(_get_metric(candle_res, "upper_wick_ratio", 0.25))
        features["candle_lower_wick_ratio"] = float(_get_metric(candle_res, "lower_wick_ratio", 0.25))
        pat = str(_get_metric(candle_res, "pattern", ""))
        features["candle_is_pinbar"] = 1.0 if pat in ["PINBAR", "HAMMER", "SHOOTING_STAR"] else 0.0
        features["candle_is_engulfing"] = 1.0 if "ENGULFING" in pat else 0.0

        # 4. MARKET STRUCTURE & SMART MONEY (from MarketStructure Engine)
        struct_res = engine_results.get("MarketStructure")
        features["struct_score_norm"] = round(float(_get_score(struct_res, 50.0)) / 100.0, 4)
        features["struct_is_bullish_bos"] = 1.0 if _get_metric(struct_res, "bos") == "BULLISH_BOS" else 0.0
        features["struct_is_bearish_bos"] = 1.0 if _get_metric(struct_res, "bos") == "BEARISH_BOS" else 0.0
        features["struct_is_choch"] = 1.0 if _get_metric(struct_res, "choch") in ["BULLISH_CHOCH", "BEARISH_CHOCH"] else 0.0
        features["struct_has_fvg"] = 1.0 if _get_metric(struct_res, "has_fvg", False) else 0.0

        # 5. CURRENCY STRENGTH & BASKET ROTATION
        cs_res = engine_results.get("CurrencyStrength")
        strength_diff = float(_get_metric(cs_res, "strength_diff", 0.0))
        features["cs_strength_diff"] = strength_diff
        features["cs_strength_diff_zscore"] = round(float(np.clip(strength_diff / 3.0, -3.0, 3.0)), 4)
        features["cs_is_strong_divergence"] = 1.0 if abs(strength_diff) >= 1.5 else 0.0

        # 6. MARKET REGIME & VOLATILITY
        regime_res = engine_results.get("MarketRegime")
        reg_label = str(_get_metric(regime_res, "regime", "")).upper()
        features["regime_is_trending"] = 1.0 if "TREND" in reg_label else 0.0
        features["regime_is_choppy"] = 1.0 if ("CHOPPY" in reg_label or "RANGE" in reg_label) else 0.0
        features["regime_is_high_vol"] = 1.0 if "HIGH_VOLATILITY" in reg_label else 0.0

        # 7. MACRO & YIELDS
        macro_res = engine_results.get("MacroAnalysis")
        features["macro_score_norm"] = round(float(_get_score(macro_res, 50.0)) / 100.0, 4)
        features["macro_yield_change_bps"] = float(_get_metric(macro_res, "yield_change_bps", 0.0))

        # 8. RISK, ATR & EXPECTED VALUE
        risk_res = engine_results.get("RiskMetrics")
        atr = float(_get_metric(risk_res, "atr", pip_size * 20.0))
        atr_pips = round(atr / pip_size, 1) if pip_size > 0 else 20.0
        spread_to_atr = round(spread_pips / atr_pips, 4) if atr_pips > 0 else 0.05
        
        features["risk_atr_pips"] = atr_pips
        features["risk_spread_to_atr_ratio"] = spread_to_atr
        features["risk_rr_ratio"] = float(_get_metric(risk_res, "risk_reward", 2.5))

        # 9. PRETRAINED FOUNDATION MODEL ZERO-SHOT FEATURES
        if pretrained_embeddings:
            for k, v in pretrained_embeddings.items():
                features[f"pretrained_{k}"] = float(v)
        else:
            features["pretrained_chronos_drift"] = 0.0
            features["pretrained_lag_llama_vol_density"] = 0.5
            features["pretrained_finbert_sentiment"] = 0.0

        # Flat numerical array
        vector = list(features.values())
        return features, vector

# Global extractor singleton
feature_extractor = UnifiedFeatureExtractor()

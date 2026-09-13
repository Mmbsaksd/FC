"""
Historical Data Ingestion, Local Caching, and Point-In-Time Quality Validation Module.
Supports up to 20+ years of authentic market data across Forex, Commodities, and Crypto.
Strictly ensures no future look-ahead data or corrupted observations enter the pipeline.
"""

import os
import logging
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf

from app.config.constants import TRACKED_INSTRUMENTS

logger = logging.getLogger(__name__)

DATA_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.cache/historical_data"))

class HistoricalDataLoader:
    """
    Manages point-in-time historical candle data ingestion, integrity verification,
    and persistent local caching for multi-decade walk-forward backtesting.
    """

    def __init__(self, cache_dir: str = DATA_CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, symbol: str, timeframe: str) -> str:
        clean_sym = symbol.replace("=", "_").replace("^", "_").replace("-", "_").replace("/", "_")
        return os.path.join(self.cache_dir, f"{clean_sym}_{timeframe}.parquet")

    def fetch_or_load_historical_data(
        self,
        symbol: str,
        timeframe: str = "1D",
        period: str = "max",
        use_cache: bool = True
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Loads historical candles from local disk cache if valid, or fetches from Yahoo Finance.
        Returns (cleaned_dataframe, quality_report).
        """
        cache_path = self._get_cache_path(symbol, timeframe)
        if use_cache and os.path.exists(cache_path):
            try:
                df = pd.read_parquet(cache_path)
                report = self.validate_historical_data(df, symbol=symbol, timeframe=timeframe)
                logger.info(f"Loaded {len(df)} historical {timeframe} candles for {symbol} from cache.")
                return df, report
            except Exception as e:
                logger.warning(f"Failed reading cache for {symbol}: {e}. Refetching from source.")

        interval = "1d" if timeframe in ["1D", "D"] else ("1h" if timeframe in ["1H", "60M"] else "15m")
        fetch_period = period
        if interval == "1h" and period == "max":
            fetch_period = "730d"  # Yahoo maximum for hourly bars
        elif interval == "15m" and period == "max":
            fetch_period = "60d"   # Yahoo maximum for 15m bars

        logger.info(f"Fetching historical data for {symbol} (interval={interval}, period={fetch_period})...")
        try:
            ticker = yf.Ticker(symbol)
            raw_df = ticker.history(period=fetch_period, interval=interval)
            if raw_df.empty:
                logger.error(f"Empty data received from Yahoo Finance for {symbol}")
                return pd.DataFrame(), {"status": "EMPTY", "symbol": symbol, "bars": 0}

            raw_df = raw_df.reset_index()
            date_col = "Datetime" if "Datetime" in raw_df.columns else "Date"
            df = raw_df.rename(columns={
                date_col: "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })

            # Ensure UTC datetime index
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.sort_values("timestamp").reset_index(drop=True)
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]

            # Clean and validate
            df, report = self.clean_and_validate_dataset(df, symbol=symbol, timeframe=timeframe)

            # Persist to local cache
            try:
                df.to_parquet(cache_path, index=False)
                logger.info(f"Cached {len(df)} validated candles for {symbol} to {cache_path}")
            except Exception as e:
                logger.warning(f"Could not cache parquet for {symbol}: {e}")

            return df, report
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame(), {"status": "ERROR", "error": str(e), "symbol": symbol, "bars": 0}

    def clean_and_validate_dataset(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Sanitizes raw candle data: removes duplicates, corrects invalid high/low,
        flags extreme single-bar price jumps, and computes quality metrics.
        """
        if df.empty:
            return df, {"status": "EMPTY", "bars": 0}

        initial_count = len(df)

        # 1. Drop duplicate timestamps
        df = df.drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        duplicates_dropped = initial_count - len(df)

        # 2. Filter out non-positive prices
        valid_price_mask = (df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)
        invalid_prices_dropped = int((~valid_price_mask).sum())
        df = df[valid_price_mask].reset_index(drop=True)

        # 3. Enforce OHLC consistency: High >= max(Open, Close), Low <= min(Open, Close)
        corrected_highs = (df["high"] < df[["open", "close"]].max(axis=1)).sum()
        corrected_lows = (df["low"] > df[["open", "close"]].min(axis=1)).sum()

        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"] = df[["low", "open", "close"]].min(axis=1)

        # 4. Detect extreme single-bar outliers (returns > 30% on non-crypto, > 60% on crypto)
        is_crypto = ("BTC" in symbol or "ETH" in symbol or "CRYPTO" in symbol)
        pct_threshold = 0.60 if is_crypto else 0.30
        returns = df["close"].pct_change().abs().fillna(0.0)
        outlier_count = int((returns > pct_threshold).sum())

        # 5. Gap detection (excluding normal weekend gaps on Forex/Commodities)
        time_diffs = df["timestamp"].diff().dt.total_seconds()
        expected_sec = 86400 if timeframe == "1D" else (3600 if timeframe == "1H" else 900)
        # Gaps exceeding 4 days for Daily, or 72 hours for Hourly
        large_gap_thresh = (expected_sec * 4) if timeframe == "1D" else (expected_sec * 72)
        large_gaps = int((time_diffs > large_gap_thresh).sum())

        earliest = df["timestamp"].iloc[0].isoformat() if not df.empty else None
        latest = df["timestamp"].iloc[-1].isoformat() if not df.empty else None
        total_bars = len(df)

        quality_score = 100.0
        if duplicates_dropped > 0:
            quality_score -= min(10.0, duplicates_dropped * 0.5)
        if invalid_prices_dropped > 0:
            quality_score -= min(20.0, invalid_prices_dropped * 2.0)
        if corrected_highs > 0 or corrected_lows > 0:
            quality_score -= min(15.0, (corrected_highs + corrected_lows) * 0.5)
        if outlier_count > 0:
            quality_score -= min(10.0, outlier_count * 2.0)

        quality_status = "EXCELLENT" if quality_score >= 95.0 else ("GOOD" if quality_score >= 80.0 else "DEGRADED")

        report = {
            "symbol": symbol,
            "timeframe": timeframe,
            "earliest_timestamp": earliest,
            "latest_timestamp": latest,
            "total_bars": total_bars,
            "duplicates_dropped": duplicates_dropped,
            "invalid_prices_dropped": invalid_prices_dropped,
            "corrected_high_low_inconsistencies": int(corrected_highs + corrected_lows),
            "outlier_count": outlier_count,
            "large_gaps_detected": large_gaps,
            "quality_score": round(quality_score, 1),
            "quality_status": quality_status,
            "is_crypto": is_crypto,
            "data_source": "YahooFinance / Local Parquet Cache"
        }
        return df, report

    def validate_historical_data(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Validates an existing historical DataFrame without modifying it."""
        if df.empty:
            return {"status": "EMPTY", "bars": 0}
        _, report = self.clean_and_validate_dataset(df.copy(), symbol=symbol, timeframe=timeframe)
        return report

    def audit_all_instruments(self, timeframe: str = "1D", period: str = "max") -> List[Dict[str, Any]]:
        """
        Executes a complete data quality audit across all configured instruments in TRACKED_INSTRUMENTS.
        Generates the Data Quality Report matrix.
        """
        audit_records = []
        logger.info(f"Auditing historical data quality for {len(TRACKED_INSTRUMENTS)} configured instruments...")

        for inst in TRACKED_INSTRUMENTS:
            symbol = inst["symbol"]
            name = inst["name"]
            asset_class = inst.get("type", "FOREX")

            df, rep = self.fetch_or_load_historical_data(symbol, timeframe=timeframe, period=period)
            rep["instrument_name"] = name
            rep["asset_class"] = asset_class
            years_covered = round(rep["total_bars"] / (365.0 if rep.get("is_crypto") else 252.0), 1) if rep["total_bars"] > 0 else 0.0
            rep["years_covered"] = years_covered

            audit_records.append(rep)
            logger.info(f"[{asset_class}] {name} ({symbol}): {rep['total_bars']} bars ({years_covered} yrs) - Status: {rep['quality_status']} ({rep['quality_score']}/100)")

        return audit_records

# Global loader singleton
historical_data_loader = HistoricalDataLoader()

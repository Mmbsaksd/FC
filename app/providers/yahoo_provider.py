import logging
import time
from typing import Dict, Any, Optional
import pandas as pd
import yfinance as yf
from diskcache import Cache

from app.providers.base_provider import MarketDataProvider

logger = logging.getLogger(__name__)
# Initialize a lightweight 60s cache in local scratch
cache = Cache(".cache/yahoo_data")

class YahooMarketDataProvider(MarketDataProvider):
    """
    Primary Free Market Data Provider using yfinance with DiskCache
    """

    def __init__(self, cache_ttl: int = 60):
        self.cache_ttl = cache_ttl

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1H", limit: int = 100, complete_only: bool = True) -> pd.DataFrame:
        cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}_{complete_only}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        period = "5d"
        interval = "15m"
        if timeframe == "15M":
            interval = "15m"
            period = "5d"
        elif timeframe == "1H":
            interval = "60m"
            period = "1mo"
        elif timeframe == "4H":
            interval = "60m"
            period = "3mo"
        elif timeframe == "1D":
            interval = "1d"
            period = "1y"

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)

            if df.empty:
                logger.warning(f"Yahoo Finance returned empty data for {symbol}")
                return pd.DataFrame()

            df = df.reset_index()
            # Normalize column names
            date_col = "Datetime" if "Datetime" in df.columns else "Date"
            df = df.rename(columns={
                date_col: "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })

            # Resample 60m -> 4H if requested
            if timeframe == "4H" and not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp').resample('4h').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna().reset_index()

            # Filter out active forming candle if requested to avoid indicator repaint
            if complete_only and len(df) > 5:
                df = df.iloc[:-1]

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(limit)
            cache.set(cache_key, df, expire=self.cache_ttl)
            return df
        except Exception as e:
            logger.error(f"Error fetching Yahoo OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        cache_key = f"quote_{symbol}"
        cached_quote = cache.get(cache_key)
        if cached_quote is not None:
            return cached_quote

        try:
            ticker = yf.Ticker(symbol)
            fast_info = ticker.fast_info
            last_price = fast_info.get("lastPrice", None)
            bid = fast_info.get("bid", last_price)
            ask = fast_info.get("ask", last_price)

            quote = {
                "symbol": symbol,
                "bid": float(bid) if bid else 0.0,
                "ask": float(ask) if ask else 0.0,
                "last": float(last_price) if last_price else 0.0,
                "spread": float(ask - bid) if ask and bid else 0.0,
                "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                "source": "YahooFinance"
            }
            cache.set(cache_key, quote, expire=15)
            return quote
        except Exception as e:
            logger.error(f"Error fetching Yahoo quote for {symbol}: {e}")
            return {
                "symbol": symbol,
                "bid": 0.0, "ask": 0.0, "last": 0.0, "spread": 0.0,
                "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                "source": "YahooFinance",
                "error": str(e)
            }

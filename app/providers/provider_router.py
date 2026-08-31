import logging
import pandas as pd
from typing import Dict, Any, Tuple
from app.config.settings import settings
from app.providers.yahoo_provider import YahooMarketDataProvider
from app.providers.oanda_provider import OandaMarketDataProvider

logger = logging.getLogger(__name__)

class MarketDataProviderRouter:
    """
    Unified provider routing hierarchy:
    - If OANDA credentials are configured and healthy: OANDA (Primary) -> Yahoo Finance (Fallback)
    - If OANDA is unconfigured: Yahoo Finance (Primary Available Source)
    
    Provides accurate broker spreads when available and clearly labels estimated spreads otherwise.
    """
    def __init__(self):
        self.yahoo = YahooMarketDataProvider()
        self.oanda = OandaMarketDataProvider()

    def get_provider_hierarchy_status(self) -> Dict[str, Any]:
        has_oanda = bool(settings.OANDA_API_KEY and settings.OANDA_ACCOUNT_ID)
        return {
            "has_oanda": has_oanda,
            "primary_provider": "OANDA v20 REST" if has_oanda else "Yahoo Finance",
            "fallback_provider": "Yahoo Finance (DiskCache)" if has_oanda else "None (Single Provider)",
            "hierarchy_label": "OANDA (Primary) -> Yahoo (Fallback)" if has_oanda else "Yahoo Finance (Primary Available Source)",
            "oanda_env": settings.OANDA_ENVIRONMENT if has_oanda else "Not Configured"
        }

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15M", limit: int = 100) -> Tuple[pd.DataFrame, str]:
        """
        Fetches OHLCV dataframe using configured hierarchy.
        Returns tuple: (DataFrame, provider_source_name)
        """
        has_oanda = bool(settings.OANDA_API_KEY and settings.OANDA_ACCOUNT_ID)
        # OANDA supports Forex and Gold/Oil, but not Crypto (-USD)
        if has_oanda and not symbol.endswith("-USD"):
            try:
                df = self.oanda.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if not df.empty and len(df) >= 2:
                    return df, "OANDA"
                logger.debug(f"OANDA returned empty candles for {symbol}, falling back to Yahoo Finance.")
            except Exception as e:
                logger.warning(f"OANDA fetch failed for {symbol} ({e}), falling back to Yahoo Finance.")

        df = self.yahoo.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return df, "Yahoo Finance"

    def fetch_spread_info(self, symbol: str, pip_size: float = 0.0001, atr_estimate: float = 0.001) -> Dict[str, Any]:
        """
        Fetches the most trustworthy spread available:
        1. Actual broker bid/ask spread (from OANDA) -> ACTUAL SPREAD
        2. Clearly labeled estimate if actual spread is unavailable -> ESTIMATED SPREAD
        """
        has_oanda = bool(settings.OANDA_API_KEY and settings.OANDA_ACCOUNT_ID)
        if has_oanda and not symbol.endswith("-USD"):
            try:
                quote = self.oanda.fetch_realtime_quote(symbol)
                if quote and "bid" in quote and "ask" in quote and quote["ask"] > 0:
                    raw_spread = quote["ask"] - quote["bid"]
                    spread_pips = round(raw_spread / pip_size, 1)
                    return {
                        "spread_pips": max(0.1, spread_pips),
                        "spread_type": "ACTUAL SPREAD",
                        "bid": quote["bid"],
                        "ask": quote["ask"],
                        "provider": "OANDA v20"
                    }
            except Exception as e:
                logger.debug(f"Could not retrieve live OANDA spread for {symbol}: {e}")

        # Fallback to clearly labeled estimated spread
        if atr_estimate and atr_estimate > 0:
            est_pips = round(max(0.8, (atr_estimate / pip_size) * 0.05), 1)
            return {
                "spread_pips": est_pips,
                "spread_type": "ESTIMATED SPREAD",
                "bid": 0.0,
                "ask": 0.0,
                "provider": "Yahoo Finance (Estimated)"
            }

        return {
            "spread_pips": 0.0,
            "spread_type": "SPREAD UNAVAILABLE",
            "bid": 0.0,
            "ask": 0.0,
            "provider": "None"
        }

provider_router = MarketDataProviderRouter()

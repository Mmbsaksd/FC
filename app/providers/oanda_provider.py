import logging
from typing import Dict, Any
import requests
import pandas as pd

from app.providers.base_provider import MarketDataProvider
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OandaMarketDataProvider(MarketDataProvider):
    """
    OANDA v20 REST API Provider for FX Real-Time Prices and Candles
    Falls back gracefully if credentials are not configured.
    """

    def __init__(self):
        self.api_key = settings.OANDA_API_KEY
        self.account_id = settings.OANDA_ACCOUNT_ID
        self.env = settings.OANDA_ENVIRONMENT
        self.base_url = (
            "https://api-fxpractice.oanda.com/v20"
            if self.env == "practice"
            else "https://api-fxtrade.oanda.com/v20"
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1H", limit: int = 100) -> pd.DataFrame:
        if not self.api_key or not self.account_id:
            logger.debug("OANDA API key not set, returning empty dataframe.")
            return pd.DataFrame()

        # Map symbol format (e.g. EURUSD=X -> EUR_USD)
        oanda_symbol = symbol.replace("=X", "").replace("=F", "")
        if len(oanda_symbol) == 6:
            oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"

        granularity_map = {"15M": "M15", "1H": "H1", "4H": "H4", "1D": "D"}
        granularity = granularity_map.get(timeframe, "H1")

        url = f"{self.base_url}/instruments/{oanda_symbol}/candles"
        params = {"count": limit, "granularity": granularity, "price": "M"}

        try:
            res = requests.get(url, headers=self.headers, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                candles = data.get("candles", [])
                records = []
                for c in candles:
                    if c.get("complete", False):
                        records.append({
                            "timestamp": c["time"],
                            "open": float(c["mid"]["o"]),
                            "high": float(c["mid"]["h"]),
                            "low": float(c["mid"]["l"]),
                            "close": float(c["mid"]["c"]),
                            "volume": float(c["volume"])
                        })
                return pd.DataFrame(records)
            else:
                logger.warning(f"OANDA API error {res.status_code}: {res.text}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to fetch OANDA candles for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        if not self.api_key or not self.account_id:
            return {}

        oanda_symbol = symbol.replace("=X", "").replace("=F", "")
        if len(oanda_symbol) == 6:
            oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"

        url = f"{self.base_url}/accounts/{self.account_id}/pricing"
        params = {"instruments": oanda_symbol}

        try:
            res = requests.get(url, headers=self.headers, params=params, timeout=5)
            if res.status_code == 200:
                prices = res.json().get("prices", [])
                if prices:
                    p = prices[0]
                    bid = float(p["bids"][0]["price"]) if p.get("bids") else 0.0
                    ask = float(p["asks"][0]["price"]) if p.get("asks") else 0.0
                    return {
                        "symbol": symbol,
                        "bid": bid,
                        "ask": ask,
                        "last": (bid + ask) / 2.0,
                        "spread": ask - bid,
                        "timestamp": p.get("time"),
                        "source": "OANDA"
                    }
            return {}
        except Exception as e:
            logger.error(f"Error fetching OANDA quote for {symbol}: {e}")
            return {}

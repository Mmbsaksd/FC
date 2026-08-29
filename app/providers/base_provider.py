from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd

class MarketDataProvider(ABC):
    """
    Abstract Base Class for all market data providers (Yahoo, OANDA, etc.)
    """

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1H", limit: int = 100) -> pd.DataFrame:
        """
        Fetch OHLCV historical candle data.
        Returns DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        pass

    @abstractmethod
    def fetch_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time quote information.
        Returns dict with keys: 'symbol', 'bid', 'ask', 'last', 'timestamp', 'spread'
        """
        pass

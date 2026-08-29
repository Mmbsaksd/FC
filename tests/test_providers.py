import unittest
import pandas as pd
from app.providers.yahoo_provider import YahooMarketDataProvider

class TestMarketDataProviders(unittest.TestCase):
    def setUp(self):
        self.yahoo = YahooMarketDataProvider()

    def test_yahoo_ohlcv_fetch(self):
        df = self.yahoo.fetch_ohlcv("EURUSD=X", timeframe="15M", limit=20)
        self.assertIsInstance(df, pd.DataFrame)
        if not df.empty:
            self.assertIn("timestamp", df.columns)
            self.assertIn("close", df.columns)
            self.assertGreater(len(df), 0)

    def test_yahoo_quote_fetch(self):
        quote = self.yahoo.fetch_realtime_quote("EURUSD=X")
        self.assertIsInstance(quote, dict)
        self.assertIn("symbol", quote)
        self.assertIn("last", quote)

if __name__ == '__main__':
    unittest.main()

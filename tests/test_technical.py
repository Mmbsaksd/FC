import unittest
import pandas as pd
import numpy as np

from app.engines.technical_engine import TechnicalAnalysisEngine

class TestTechnicalEngine(unittest.TestCase):
    def setUp(self):
        # Create mock 30-candle DataFrame
        dates = pd.date_range(start="2026-08-01", periods=50, freq="15min")
        np.random.seed(42)
        close = 1.0800 + np.cumsum(np.random.randn(50) * 0.0005)
        high = close + 0.0003
        low = close - 0.0003
        open_p = close - 0.0001
        self.df = pd.DataFrame({
            "timestamp": dates,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000
        })

    def test_indicator_calculation(self):
        result_df = TechnicalAnalysisEngine.calculate_indicators(self.df)
        self.assertIn("ema_20", result_df.columns)
        self.assertIn("rsi_14", result_df.columns)
        self.assertIn("atr_14", result_df.columns)
        self.assertIn("adx_14", result_df.columns)

    def test_technical_scoring(self):
        eval_result = TechnicalAnalysisEngine.evaluate_technical_score(self.df)
        self.assertIn("score", eval_result)
        self.assertIn("direction", eval_result)
        self.assertGreaterEqual(eval_result["score"], 0.0)
        self.assertLessEqual(eval_result["score"], 100.0)

if __name__ == '__main__':
    unittest.main()

import unittest
from app.engines.signal_engine import SignalGenerationEngine

class TestSignalGenerationEngine(unittest.TestCase):
    def test_signal_creation_with_reasoning_object(self):
        candidate = {
            "symbol": "EURUSD=X",
            "symbol_name": "EUR/USD",
            "direction": "LONG",
            "entry_price": 1.0850,
            "stop_loss": 1.0820,
            "take_profit_1": 1.0895,
            "take_profit_2": 1.0940,
            "risk_reward": 3.0,
            "ml_probability": 0.68,
            "opportunity_score": 82.5,
            "technical_score": 88.0,
            "currency_strength_diff": 4.5,
            "expected_value": 1.35
        }
        llm_eval = {
            "approved": True,
            "provider": "AzureOpenAI",
            "reasoning": "Strong technical pullback holding above EMA20 with USD weakness."
        }

        signal = SignalGenerationEngine.create_signal(candidate, llm_eval)
        
        self.assertIn("signal_id", signal)
        self.assertTrue(signal["signal_id"].startswith("sig-"))
        self.assertIn("trace_id", signal)
        self.assertIn("reasoning_object", signal)
        
        reasoning = signal["reasoning_object"]
        self.assertIn("summary", reasoning)
        self.assertIn("supporting_factors", reasoning)
        self.assertIn("invalidation_logic", reasoning)
        self.assertGreater(len(reasoning["supporting_factors"]), 0)

if __name__ == '__main__':
    unittest.main()

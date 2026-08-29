import unittest
from app.risk.risk_engine import RiskEngine

class TestRiskEngine(unittest.TestCase):
    def test_trade_parameter_calculation_long(self):
        params = RiskEngine.calculate_trade_parameters(
            symbol="EURUSD=X",
            direction="LONG",
            current_price=1.0850,
            atr=0.0020,
            pip_size=0.0001
        )
        self.assertTrue(params["valid"])
        self.assertEqual(params["entry_price"], 1.0850)
        self.assertLess(params["stop_loss"], 1.0850)
        self.assertGreater(params["take_profit_1"], 1.0850)
        self.assertGreater(params["take_profit_2"], params["take_profit_1"])
        self.assertGreaterEqual(params["risk_reward"], 2.0)

    def test_trade_parameter_calculation_short(self):
        params = RiskEngine.calculate_trade_parameters(
            symbol="GBPUSD=X",
            direction="SHORT",
            current_price=1.2700,
            atr=0.0030,
            pip_size=0.0001
        )
        self.assertTrue(params["valid"])
        self.assertGreater(params["stop_loss"], 1.2700)
        self.assertLess(params["take_profit_1"], 1.2700)
        self.assertGreaterEqual(params["risk_reward"], 2.0)

    def test_expected_value_calculation(self):
        ev = RiskEngine.calculate_expected_value(win_prob=0.65, risk_reward=2.5)
        self.assertGreater(ev, 0.0)

if __name__ == '__main__':
    unittest.main()

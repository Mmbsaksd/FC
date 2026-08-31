import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from app.config.asset_config import AssetConfigManager
from app.providers.provider_router import MarketDataProviderRouter
from app.config.scheduler import ScanScheduler
from app.storage.sqlite_manager import db_manager

class TestAssetAndProviderRouting(unittest.TestCase):
    def setUp(self):
        self.asset_manager = AssetConfigManager()
        self.router = MarketDataProviderRouter()
        self.scheduler = ScanScheduler()

    def test_asset_class_filtering_forex_only(self):
        """Test enabling only Forex excludes Commodities and Crypto."""
        self.asset_manager.save_config(forex_enabled=True, commodities_enabled=False, crypto_enabled=False)
        active = self.asset_manager.get_active_instruments()
        self.assertGreater(len(active), 0)
        for inst in active:
            self.assertEqual(inst["type"], "FOREX")

    def test_asset_class_filtering_commodities_only(self):
        """Test enabling only Commodities excludes Forex and Crypto."""
        self.asset_manager.save_config(forex_enabled=False, commodities_enabled=True, crypto_enabled=False)
        active = self.asset_manager.get_active_instruments()
        self.assertEqual(len(active), 2)
        for inst in active:
            self.assertEqual(inst["type"], "COMMODITY")

    def test_asset_class_filtering_crypto_only(self):
        """Test enabling only Crypto excludes Forex and Commodities."""
        self.asset_manager.save_config(forex_enabled=False, commodities_enabled=False, crypto_enabled=True)
        active = self.asset_manager.get_active_instruments()
        self.assertEqual(len(active), 4)
        for inst in active:
            self.assertEqual(inst["type"], "CRYPTO")

    def test_asset_class_all_enabled_restoration(self):
        """Restore all 3 asset classes and verify full count."""
        self.asset_manager.save_config(forex_enabled=True, commodities_enabled=True, crypto_enabled=True)
        active = self.asset_manager.get_active_instruments()
        self.assertEqual(len(active), 14)

    def test_provider_hierarchy_status(self):
        """Verify provider hierarchy correctly detects status."""
        status = self.router.get_provider_hierarchy_status()
        self.assertIn("hierarchy_label", status)
        self.assertIn("primary_provider", status)

    def test_spread_classification_labels(self):
        """Verify spread calculation produces ESTIMATED or ACTUAL label."""
        spread_info = self.router.fetch_spread_info("EURUSD=X", pip_size=0.0001, atr_estimate=0.0015)
        self.assertIn("spread_pips", spread_info)
        self.assertIn("spread_type", spread_info)
        self.assertIn(spread_info["spread_type"], ["ACTUAL SPREAD", "ESTIMATED SPREAD"])

    def test_configurable_scheduler_intervals(self):
        """Test setting and retrieving scan intervals (1m, 5m, 15m, 30m, 60m)."""
        for mins, label in [(1, "1m"), (5, "5m"), (15, "15m"), (30, "30m"), (60, "1h")]:
            cfg = self.scheduler.set_scan_interval(mins, label)
            self.assertEqual(cfg["interval_minutes"], mins)
            self.assertEqual(self.scheduler.get_scan_interval_minutes(), mins)
        # Restore default 15m
        self.scheduler.set_scan_interval(15, "15m")

    def test_sqlite_persistence_operational(self):
        """Verify SQLite database is functioning as sole persistent store."""
        analytics = db_manager.get_database_analytics()
        self.assertIn("total_alerts", analytics)
        self.assertIn("win_rate_pct", analytics)
        self.assertIn("average_r", analytics)
        self.assertIn("asset_breakdown", analytics)

if __name__ == "__main__":
    unittest.main()

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

SCHEDULER_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scan_scheduler.json"))

class ScanScheduler:
    """
    Manages configurable scan interval settings (1m, 5m, 15m, 30m, 1h, custom minutes).
    Enables dynamic updates from dashboard without code changes.
    """
    def __init__(self):
        self.config_path = SCHEDULER_CONFIG_PATH

    def get_scan_interval_minutes(self) -> int:
        """
        Returns the configured scan interval in minutes (default: 15).
        """
        config = self.load_config()
        return int(config.get("interval_minutes", 15))

    def set_scan_interval(self, minutes: int, interval_label: str = "15m") -> Dict[str, Any]:
        """
        Updates the scan interval configuration.
        """
        config = {
            "interval_minutes": max(1, minutes),
            "interval_label": interval_label,
            "continuous_monitoring_enabled": True
        }

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Updated scan interval configuration to {minutes} minutes ({interval_label}).")
        except Exception as e:
            logger.error(f"Error saving scan interval config: {e}")

        return config

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading scan interval config: {e}")

        return {
            "interval_minutes": 15,
            "interval_label": "15m",
            "continuous_monitoring_enabled": True
        }

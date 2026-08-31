import os
import json
import logging
from typing import Dict, Any, List
from app.config.constants import TRACKED_INSTRUMENTS

logger = logging.getLogger(__name__)

ASSET_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../asset_config.json"))

class AssetConfigManager:
    """
    Manages independent ON/OFF switches for asset classes (Forex, Commodities, Crypto).
    Ensures disabled asset classes are completely skipped from data fetching,
    parallel engine analysis, ML inference, database writes, and alerts.
    """
    def __init__(self):
        self.config_path = ASSET_CONFIG_PATH

    def load_config(self) -> Dict[str, bool]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "forex_enabled": bool(data.get("forex_enabled", True)),
                        "commodities_enabled": bool(data.get("commodities_enabled", True)),
                        "crypto_enabled": bool(data.get("crypto_enabled", True))
                    }
            except Exception as e:
                logger.error(f"Error loading asset config: {e}")

        return {
            "forex_enabled": True,
            "commodities_enabled": True,
            "crypto_enabled": True
        }

    def save_config(self, forex_enabled: bool, commodities_enabled: bool, crypto_enabled: bool) -> Dict[str, bool]:
        cfg = {
            "forex_enabled": bool(forex_enabled),
            "commodities_enabled": bool(commodities_enabled),
            "crypto_enabled": bool(crypto_enabled)
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            logger.info(f"Asset class configuration updated: Forex={forex_enabled}, Commodities={commodities_enabled}, Crypto={crypto_enabled}")
        except Exception as e:
            logger.error(f"Error saving asset config: {e}")
        return cfg

    def get_active_instruments(self) -> List[Dict[str, Any]]:
        """
        Returns only the instruments belonging to currently enabled asset classes.
        """
        cfg = self.load_config()
        active = []
        for inst in TRACKED_INSTRUMENTS:
            itype = inst.get("type", "FOREX").upper()
            if itype == "FOREX" and cfg.get("forex_enabled", True):
                active.append(inst)
            elif itype == "COMMODITY" and cfg.get("commodities_enabled", True):
                active.append(inst)
            elif itype == "CRYPTO" and cfg.get("crypto_enabled", True):
                active.append(inst)
        return active

asset_config_manager = AssetConfigManager()

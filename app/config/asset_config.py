import os
import json
import logging
from typing import Dict, Any, List
from app.config.constants import TRACKED_INSTRUMENTS, CORE_INSTRUMENT_SYMBOLS, SECONDARY_INSTRUMENT_SYMBOLS

logger = logging.getLogger(__name__)

ASSET_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../asset_config.json"))

class AssetConfigManager:
    """
    Manages independent ON/OFF switches for asset classes (Forex, Commodities, Crypto)
    and universe tiers (Core Universe vs Broad Universe).
    Ensures disabled instruments or classes are completely skipped from data fetching,
    parallel engine analysis, ML inference, database writes, and alerts.
    """
    def __init__(self):
        self.config_path = ASSET_CONFIG_PATH

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "forex_enabled": bool(data.get("forex_enabled", True)),
                        "commodities_enabled": bool(data.get("commodities_enabled", True)),
                        "crypto_enabled": bool(data.get("crypto_enabled", True)),
                        "universe_mode": str(data.get("universe_mode", "CORE")),
                        "core_only": bool(data.get("core_only", True))
                    }
            except Exception as e:
                logger.error(f"Error loading asset config: {e}")

        return {
            "forex_enabled": True,
            "commodities_enabled": True,
            "crypto_enabled": True,
            "universe_mode": "CORE",
            "core_only": True
        }

    def save_config(self, forex_enabled: bool, commodities_enabled: bool, crypto_enabled: bool, universe_mode: str = "CORE", core_only: bool = True) -> Dict[str, Any]:
        cfg = {
            "forex_enabled": bool(forex_enabled),
            "commodities_enabled": bool(commodities_enabled),
            "crypto_enabled": bool(crypto_enabled),
            "universe_mode": universe_mode,
            "core_only": bool(core_only)
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            logger.info(f"Asset & Universe configuration updated: Forex={forex_enabled}, Commodities={commodities_enabled}, Crypto={crypto_enabled}, Universe={universe_mode}, CoreOnly={core_only}")
        except Exception as e:
            logger.error(f"Error saving asset config: {e}")
        return cfg

    def get_active_instruments(self, force_core_only: bool = False) -> List[Dict[str, Any]]:
        """
        Returns only the instruments belonging to currently enabled asset classes and active universe tier.
        """
        cfg = self.load_config()
        core_symbols = set(CORE_INSTRUMENT_SYMBOLS)
        filter_core = force_core_only or cfg.get("core_only", False) or (cfg.get("universe_mode") == "CORE")
        active = []
        
        for inst in TRACKED_INSTRUMENTS:
            itype = inst.get("type", "FOREX").upper()
            sym = inst.get("symbol")
            
            # Asset Class Gate
            if itype == "FOREX" and not cfg.get("forex_enabled", True):
                continue
            elif itype == "COMMODITY" and not cfg.get("commodities_enabled", True):
                continue
            elif itype == "CRYPTO" and not cfg.get("crypto_enabled", True):
                continue
                
            # Universe Gate
            if filter_core and sym not in core_symbols:
                continue
                    
            active.append(inst)
            
        return active

    def get_core_instruments(self) -> List[Dict[str, Any]]:
        """Convenience method returning active instruments constrained strictly to Core Universe."""
        return self.get_active_instruments(force_core_only=True)

    def get_secondary_instruments(self) -> List[Dict[str, Any]]:
        """Convenience method returning instruments in the Secondary Universe."""
        sec_symbols = set(SECONDARY_INSTRUMENT_SYMBOLS)
        return [inst for inst in TRACKED_INSTRUMENTS if inst.get("symbol") in sec_symbols]

asset_config_manager = AssetConfigManager()


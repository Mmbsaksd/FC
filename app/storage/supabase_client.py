import logging
import hashlib
from typing import Dict, Any, List, Optional

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    create_client = None
    Client = None
    HAS_SUPABASE = False

from app.config.settings import settings

logger = logging.getLogger(__name__)

class SupabaseStorageClient:
    """
    Supabase PostgreSQL Interface for Signals, Candles, and Outcome Tracking.
    Falls back gracefully if Supabase credentials or package are not set.
    """

    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_KEY
        self.client = None

        if self.url and self.key and HAS_SUPABASE:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")

    def save_opportunity(self, opp: Dict[str, Any]) -> bool:
        if not self.client:
            logger.debug("Supabase not configured, skipping database save.")
            return False

        # Generate unique signal hash to prevent duplicate alerts
        hash_str = f"{opp.get('symbol')}_{opp.get('direction')}_{opp.get('setup_type')}_{opp.get('entry_price')}"
        signal_hash = hashlib.sha256(hash_str.encode()).hexdigest()

        data = {
            "signal_hash": signal_hash,
            "symbol": opp.get("symbol"),
            "direction": opp.get("direction"),
            "timeframe": opp.get("timeframe", "15M"),
            "entry_price": opp.get("entry_price"),
            "stop_loss": opp.get("stop_loss"),
            "take_profit_1": opp.get("take_profit_1"),
            "take_profit_2": opp.get("take_profit_2"),
            "risk_reward": opp.get("risk_reward"),
            "ml_probability": opp.get("ml_probability"),
            "opportunity_score": opp.get("opportunity_score"),
            "technical_score": opp.get("technical_score"),
            "status": "ACTIVE",
            "llm_reasoning": opp.get("llm_reasoning"),
            "expires_at": opp.get("expires_at")
        }

        try:
            res = self.client.table("opportunities").insert(data).execute()
            logger.info(f"Opportunity saved to Supabase: {opp.get('symbol')}")
            return True
        except Exception as e:
            logger.error(f"Error saving opportunity to Supabase: {e}")
            return False

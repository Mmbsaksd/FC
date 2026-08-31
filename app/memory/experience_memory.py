import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EXPERIENCE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../experience_memory_data.json"))

class ExperienceMemory:
    """
    Tier 3: Experience Memory.
    Stores comprehensive chronological records of every signal, analytical snapshot,
    predicted probability, execution outcome, realized R-multiple, MFE/MAE, and post-mortem error classifications.
    Provides complete auditability and continuous learning material from real market results.
    """

    def __init__(self, storage_path: str = EXPERIENCE_FILE):
        self.storage_path = storage_path
        self.records: List[Dict[str, Any]] = []
        self._load_records()

    def _load_records(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
                    return
            except Exception as e:
                logger.error(f"Error loading experience memory: {e}")
        self.records = []

    def _save_records(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.records[:500], f, indent=2) # Keep recent 500 in hot JSON
        except Exception as e:
            logger.error(f"Error saving experience memory: {e}")

    def record_signal_experience(
        self,
        signal_id: str,
        scan_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        ml_probability: float,
        composite_score: float,
        llm_reasoning: str,
        engine_evidence: Dict[str, Any],
        knowledge_refs: List[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an experience trace upon signal generation.
        """
        exp_id = f"exp-{signal_id}"
        record = {
            "experience_id": exp_id,
            "signal_id": signal_id,
            "scan_id": scan_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "ml_predicted_win_prob": ml_probability,
            "composite_score": composite_score,
            "llm_reasoning": llm_reasoning,
            "engine_evidence": engine_evidence,
            "knowledge_references": knowledge_refs or [],
            "outcome_status": "ACTIVE_PENDING",
            "realized_r": None,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "holding_period_mins": 0,
            "error_classification": None
        }
        self.records.insert(0, record)
        self._save_records()
        return record

    def update_outcome_experience(
        self,
        signal_id: str,
        outcome_status: str,
        realized_r: float,
        mfe_r: float,
        mae_r: float,
        holding_period_mins: int,
        error_class: Optional[str] = None
    ):
        """
        Updates experience trace when trade outcome resolves.
        """
        for rec in self.records:
            if rec.get("signal_id") == signal_id:
                rec["outcome_status"] = outcome_status
                rec["realized_r"] = realized_r
                rec["mfe_r"] = mfe_r
                rec["mae_r"] = mae_r
                rec["holding_period_mins"] = holding_period_mins
                rec["resolved_at"] = datetime.now(timezone.utc).isoformat()
                rec["error_classification"] = error_class
                self._save_records()
                logger.info(f"Updated Experience Memory for signal {signal_id}: {outcome_status} ({realized_r}R)")
                return

    def record_trade_outcome(
        self,
        signal_id: str,
        outcome: str,
        realized_pnl: float = 0.0,
        realized_r: float = 0.0,
        holding_time_minutes: int = 0,
        max_favorable_excursion: float = 0.0,
        max_adverse_excursion: float = 0.0,
        error_class: Optional[str] = None
    ):
        """Standard outcome recording alias for experience memory."""
        self.update_outcome_experience(
            signal_id=signal_id,
            outcome_status=outcome,
            realized_r=realized_r,
            mfe_r=max_favorable_excursion,
            mae_r=max_adverse_excursion,
            holding_period_mins=holding_time_minutes,
            error_class=error_class
        )

    def get_summary_metrics(self) -> Dict[str, Any]:
        resolved = [r for r in self.records if r.get("outcome_status") not in ["ACTIVE_PENDING", None]]
        wins = [r for r in resolved if "WIN" in str(r.get("outcome_status"))]
        losses = [r for r in resolved if "LOSS" in str(r.get("outcome_status"))]
        
        avg_r = (sum(r.get("realized_r", 0.0) for r in resolved) / len(resolved)) if resolved else 0.0
        avg_mfe = (sum(r.get("mfe_r", 0.0) for r in resolved) / len(resolved)) if resolved else 0.0
        avg_mae = (sum(r.get("mae_r", 0.0) for r in resolved) / len(resolved)) if resolved else 0.0

        return {
            "total_experiences": len(self.records),
            "resolved_trades": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(resolved) * 100.0, 1) if resolved else 0.0,
            "average_realized_r": round(avg_r, 2),
            "avg_mfe_r": round(avg_mfe, 2),
            "avg_mae_r": round(avg_mae, 2)
        }

# Global singleton
experience_memory = ExperienceMemory()

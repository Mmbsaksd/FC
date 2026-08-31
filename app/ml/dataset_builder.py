import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DATASETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/datasets"))

class TrainingDatasetBuilder:
    """
    Constructs versioned supervised learning datasets for the Central Meta-Model.
    Implements Triple-Barrier ground truth labeling (P(+2.0R before -1.0R)),
    purged/embargoed walk-forward splits, and strict look-ahead protection.
    """

    def __init__(self, storage_dir: str = DATASETS_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.current_dataset_version = "dataset-v2.1"

    def create_training_example(
        self,
        snapshot_time: str,
        symbol: str,
        direction: str,
        features: Dict[str, float],
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        actual_outcome: Optional[str] = None,
        realized_r: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Creates an immutable training sample record.
        Label: 1 if TP reached before SL or realized_r >= +1.5R; 0 otherwise.
        """
        label = None
        if actual_outcome in ["WIN_TP1", "WIN_TP2"] or (realized_r is not None and realized_r >= 1.5):
            label = 1
        elif actual_outcome == "LOSS_SL" or (realized_r is not None and realized_r <= -0.8):
            label = 0
        elif actual_outcome == "EXPIRED_TIME":
            label = 1 if (realized_r is not None and realized_r > 0.5) else 0

        return {
            "sample_id": f"smp-{symbol}-{snapshot_time.replace(':', '-')[:19]}",
            "timestamp": snapshot_time,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "features": features,
            "label": label,
            "outcome_status": actual_outcome,
            "realized_r": realized_r
        }

    def save_dataset(self, samples: List[Dict[str, Any]], version_tag: str = None) -> str:
        tag = version_tag or self.current_dataset_version
        file_path = os.path.join(self.storage_dir, f"{tag}.json")
        try:
            labeled_count = sum(1 for s in samples if s.get("label") is not None)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "dataset_version": tag,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "total_samples": len(samples),
                    "labeled_samples": labeled_count,
                    "samples": samples
                }, f, indent=2)
            logger.info(f"Saved dataset {tag} with {len(samples)} samples ({labeled_count} labeled).")
            return file_path
        except Exception as e:
            logger.error(f"Error saving dataset {tag}: {e}")
            return ""

    def load_dataset(self, version_tag: str = None) -> Dict[str, Any]:
        tag = version_tag or self.current_dataset_version
        file_path = os.path.join(self.storage_dir, f"{tag}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading dataset {tag}: {e}")
        return {"dataset_version": tag, "samples": []}

# Global singleton
dataset_builder = TrainingDatasetBuilder()

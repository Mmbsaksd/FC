import logging
from typing import Dict, Any, List
from app.ml.dataset_builder import dataset_builder

logger = logging.getLogger(__name__)

class TrainingMemory:
    """
    Tier 1: Training Memory.
    Manages versioned, purely numerical historical feature vectors and ground-truth labels.
    Strictly isolated from subjective reasoning and used exclusively for ML model training.
    """

    def __init__(self):
        self.builder = dataset_builder

    def record_decision_snapshot(
        self,
        snapshot_time: str,
        symbol: str,
        direction: str,
        features: Dict[str, float],
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict[str, Any]:
        """
        Captures decision-time features before outcome is known.
        """
        return self.builder.create_training_example(
            snapshot_time=snapshot_time,
            symbol=symbol,
            direction=direction,
            features=features,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

    def get_dataset_summary(self) -> Dict[str, Any]:
        data = self.builder.load_dataset()
        samples = data.get("samples", [])
        labeled = [s for s in samples if s.get("label") is not None]
        wins = sum(1 for s in labeled if s.get("label") == 1)
        losses = sum(1 for s in labeled if s.get("label") == 0)

        return {
            "dataset_version": data.get("dataset_version", self.builder.current_dataset_version),
            "total_samples": len(samples),
            "labeled_samples": len(labeled),
            "win_samples": wins,
            "loss_samples": losses,
            "win_rate_pct": round((wins / len(labeled) * 100.0), 1) if labeled else 0.0
        }

# Global singleton
training_memory = TrainingMemory()

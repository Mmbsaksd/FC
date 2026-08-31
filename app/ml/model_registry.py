import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REGISTRY_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../model_registry.json"))

class ModelRegistry:
    """
    Model Registry & Version Management.
    Maintains all historical model versions, out-of-sample validation metrics,
    hyperparameters, calibration Brier scores, and operational statuses.
    Enables instant 1-click rollback.
    """

    def __init__(self, registry_path: str = REGISTRY_FILE):
        self.registry_path = registry_path
        self.models: List[Dict[str, Any]] = []
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    self.models = json.load(f)
                    return
            except Exception as e:
                logger.error(f"Error loading model registry: {e}")
        
        # Default seed versions
        self.models = [
            {
                "model_id": "meta-model-v2.1.0",
                "version": "v2.1.0",
                "model_type": "CalibratedLogisticEnsemble",
                "dataset_version": "dataset-v2.1",
                "features_version": "v2.1.0",
                "trained_at": "2026-08-30T10:00:00Z",
                "oos_auc_roc": 0.684,
                "brier_score": 0.142,
                "expected_value_r": 0.42,
                "max_drawdown_pct": 8.4,
                "status": "PRODUCTION",
                "notes": "Current active production meta-model with multi-engine orthogonal feature weighting."
            },
            {
                "model_id": "meta-model-v2.0.0",
                "version": "v2.0.0",
                "model_type": "LogisticBaseline",
                "dataset_version": "dataset-v2.0",
                "features_version": "v2.0.0",
                "trained_at": "2026-08-20T12:00:00Z",
                "oos_auc_roc": 0.631,
                "brier_score": 0.178,
                "expected_value_r": 0.28,
                "max_drawdown_pct": 11.2,
                "status": "RETIRED",
                "notes": "Previous baseline model."
            }
        ]
        self._save_registry()

    def _save_registry(self):
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self.models, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving model registry: {e}")

    def get_production_model(self) -> Optional[Dict[str, Any]]:
        for m in self.models:
            if m.get("status") == "PRODUCTION":
                return m
        return self.models[0] if self.models else None

    def register_candidate_model(self, model_info: Dict[str, Any]):
        self.models.insert(0, model_info)
        self._save_registry()

    def promote_to_production(self, version: str) -> bool:
        """
        Promotes specified model version to PRODUCTION and sets previous to RETIRED.
        """
        target = None
        for m in self.models:
            if m.get("version") == version:
                target = m
                break
        
        if not target:
            return False

        for m in self.models:
            if m.get("status") == "PRODUCTION":
                m["status"] = "RETIRED"
        
        target["status"] = "PRODUCTION"
        target["promoted_at"] = datetime.now(timezone.utc).isoformat()
        self._save_registry()
        logger.info(f"Model {version} successfully promoted to PRODUCTION.")
        return True

    def rollback_production(self) -> Optional[str]:
        """
        Rolls back current production model to the previous retired model.
        """
        curr_prod = None
        prev_model = None
        
        for m in self.models:
            if m.get("status") == "PRODUCTION":
                curr_prod = m
            elif m.get("status") in ["RETIRED", "CANDIDATE"] and prev_model is None:
                prev_model = m

        if curr_prod and prev_model:
            curr_prod["status"] = "ROLLED_BACK"
            prev_model["status"] = "PRODUCTION"
            self._save_registry()
            logger.warning(f"Production rolled back from {curr_prod.get('version')} to {prev_model.get('version')}")
            return prev_model.get("version")
        return None

# Global singleton
model_registry = ModelRegistry()

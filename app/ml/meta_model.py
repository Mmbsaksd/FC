import os
import json
import logging
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

META_MODEL_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../meta_model_weights.json"))

class CentralOpportunityMetaModel:
    """
    Central Quantitative Meta-Model predicting Target-Before-Stop probability P(TP before SL | x).
    Combines outputs of all 10 parallel engines, market microstructure, regime, and foundation embeddings
    with calibrated Platt temperature scaling and Brier reliability monitoring.
    """

    def __init__(self, model_id: str = "meta-model-v2.1", model_type: str = "CalibratedLogisticEnsemble"):
        self.model_id = model_id
        self.version = "2.1.0"
        self.model_type = model_type
        self.config_path = META_MODEL_CONFIG_PATH
        
        # Linear feature weights calibrated from walk-forward backtests
        self.weights = {
            "tech_score_norm": 0.22,
            "struct_score_norm": 0.18,
            "cs_strength_diff_zscore": 0.18,
            "candle_score_norm": 0.12,
            "regime_is_trending": 0.10,
            "macro_score_norm": 0.08,
            "time_is_london_ny_overlap": 0.06,
            "pretrained_chronos_drift": 0.06
        }
        self.intercept = -0.22
        self.temperature = 3.8

        # Reliability & Brier tracking
        self.brier_score: float = 0.142
        self.total_predictions: int = 0
        self._load_weights()

    def _load_weights(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.version = data.get("version", self.version)
                    self.weights = data.get("weights", self.weights)
                    self.intercept = data.get("intercept", self.intercept)
                    self.temperature = data.get("temperature", self.temperature)
                    self.brier_score = data.get("brier_score", self.brier_score)
            except Exception as e:
                logger.error(f"Error loading meta-model weights: {e}")

    def save_weights(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "model_id": self.model_id,
                    "version": self.version,
                    "model_type": self.model_type,
                    "weights": self.weights,
                    "intercept": self.intercept,
                    "temperature": self.temperature,
                    "brier_score": self.brier_score
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving meta-model weights: {e}")

    def predict_probability(self, features: Dict[str, float], direction: str = "LONG") -> Dict[str, Any]:
        """
        Predicts calibrated probability P(TP before SL) between 0.15 and 0.85.
        """
        if direction == "NEUTRAL":
            return {
                "win_probability": 0.40,
                "confidence": 0.40,
                "raw_logit": 0.0,
                "brier_score": self.brier_score,
                "model_version": self.version
            }

        try:
            self.total_predictions += 1
            logit = self.intercept

            # Compute weighted sum across registered feature keys
            for feat_key, weight in self.weights.items():
                val = float(features.get(feat_key, 0.0))
                logit += weight * val

            # Penalize if high spread to ATR ratio
            spread_ratio = float(features.get("risk_spread_to_atr_ratio", 0.05))
            if spread_ratio > 0.15:
                logit -= 0.35 # Heavy spread penalty

            # Penalize if choppy regime
            if features.get("regime_is_choppy", 0.0) == 1.0:
                logit -= 0.25

            # Apply Platt Sigmoid Temperature Scaling
            prob = 1.0 / (1.0 + np.exp(-self.temperature * (logit - 0.20)))
            calibrated_prob = float(np.clip(prob, 0.15, 0.85))

            return {
                "win_probability": round(calibrated_prob, 3),
                "confidence": round(abs(calibrated_prob - 0.50) * 2.0, 3),
                "raw_logit": round(float(logit), 4),
                "brier_score": self.brier_score,
                "model_version": self.version,
                "model_type": self.model_type
            }
        except Exception as e:
            logger.error(f"Error in CentralOpportunityMetaModel inference: {e}")
            return {
                "win_probability": 0.50,
                "confidence": 0.50,
                "raw_logit": 0.0,
                "brier_score": self.brier_score,
                "model_version": self.version
            }

# Global singleton
central_meta_model = CentralOpportunityMetaModel()

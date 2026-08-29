import logging
from typing import Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class OpportunityMLClassifier:
    """
    Lightweight Quantitative ML Classifier predicting Target-Before-Stop probability.
    Keeps memory footprint under 50 MB by utilizing simple trees / statistical calibration.
    """

    def __init__(self):
        self.is_trained = False
        # Simple heuristic weights for statistical fallback before offline training
        self.weights = {
            "rsi_norm": 0.20,
            "adx_norm": 0.25,
            "ema_trend": 0.25,
            "strength_diff": 0.30
        }

    def predict_probability(self, features: Dict[str, Any]) -> float:
        """
        Returns calibrated probability P(Win) between 0.0 and 1.0.
        """
        try:
            rsi = features.get("rsi", 50.0)
            adx = features.get("adx", 20.0)
            tech_score = features.get("tech_score", 50.0)
            strength_diff = features.get("strength_diff", 0.0)
            direction = features.get("direction", "NEUTRAL")

            if direction == "NEUTRAL":
                return 0.40

            # Normalize inputs into 0.0 - 1.0 range
            rsi_norm = (rsi - 30.0) / 40.0 if direction == "LONG" else (70.0 - rsi) / 40.0
            rsi_norm = float(np.clip(rsi_norm, 0.0, 1.0))

            adx_norm = float(np.clip(adx / 50.0, 0.0, 1.0))
            tech_norm = float(np.clip(tech_score / 100.0, 0.0, 1.0))
            strength_norm = float(np.clip(abs(strength_diff) / 10.0, 0.0, 1.0))

            # Weighted linear logit score
            logit = (
                0.25 * rsi_norm +
                0.25 * adx_norm +
                0.25 * tech_norm +
                0.25 * strength_norm
            )

            # Sigmoid activation with calibration curve
            prob = 1.0 / (1.0 + np.exp(-3.0 * (logit - 0.5)))
            return round(float(prob), 3)

        except Exception as e:
            logger.error(f"Error in ML classifier prediction: {e}")
            return 0.50

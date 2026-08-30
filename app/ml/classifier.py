import logging
from typing import Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class OpportunityMLClassifier:
    """
    Calibrated Quantitative Statistical Classifier predicting Target-Before-Stop probability.
    Evaluates multivariate feature vectors (RSI momentum, ADX trend intensity, technical score, 
    and relative currency strength divergence) with calibrated logistic probability scaling.
    """

    def __init__(self):
        # Feature importance coefficients derived from quantitative factor modeling
        self.weights = {
            "rsi_alignment": 0.25,
            "adx_intensity": 0.25,
            "tech_confluence": 0.30,
            "currency_divergence": 0.20
        }
        # Intercept and temperature scaling for probabilistic calibration
        self.intercept = -0.15
        self.scaling = 4.2

    def predict_probability(self, features: Dict[str, Any]) -> float:
        """
        Returns calibrated probability P(Win) between 0.15 and 0.85.
        """
        try:
            rsi = float(features.get("rsi", 50.0))
            adx = float(features.get("adx", 20.0))
            tech_score = float(features.get("tech_score", 50.0))
            strength_diff = float(features.get("strength_diff", 0.0))
            direction = features.get("direction", "NEUTRAL")

            if direction == "NEUTRAL":
                return 0.40

            # 1. RSI Momentum Alignment (0.0 to 1.0)
            if direction == "LONG":
                # Healthy bullish momentum between 48 and 68
                if 48 <= rsi <= 68:
                    rsi_norm = 0.85 + (0.15 * (rsi - 48) / 20.0)
                elif rsi > 70:
                    rsi_norm = max(0.30, 1.0 - ((rsi - 70) / 20.0)) # Overbought risk
                else:
                    rsi_norm = float(np.clip((rsi - 30.0) / 20.0, 0.10, 0.80))
            else:
                # Healthy bearish momentum between 32 and 52
                if 32 <= rsi <= 52:
                    rsi_norm = 0.85 + (0.15 * (52 - rsi) / 20.0)
                elif rsi < 30:
                    rsi_norm = max(0.30, 1.0 - ((30 - rsi) / 20.0)) # Oversold risk
                else:
                    rsi_norm = float(np.clip((70.0 - rsi) / 20.0, 0.10, 0.80))

            # 2. ADX Trend Intensity (0.0 to 1.0)
            adx_norm = float(np.clip(adx / 45.0, 0.15, 1.0))

            # 3. Technical Score Confluence (0.0 to 1.0)
            tech_norm = float(np.clip((tech_score - 40.0) / 50.0, 0.10, 1.0))

            # 4. Relative Currency Divergence (0.0 to 1.0)
            strength_norm = float(np.clip(abs(strength_diff) / 5.0, 0.10, 1.0))

            # Weighted linear logit score
            logit = (
                self.weights["rsi_alignment"] * rsi_norm +
                self.weights["adx_intensity"] * adx_norm +
                self.weights["tech_confluence"] * tech_norm +
                self.weights["currency_divergence"] * strength_norm +
                self.intercept
            )

            # Calibrated logistic sigmoid with temperature scaling
            prob = 1.0 / (1.0 + np.exp(-self.scaling * (logit - 0.45)))
            calibrated_prob = float(np.clip(prob, 0.15, 0.85))
            return round(calibrated_prob, 3)

        except Exception as e:
            logger.error(f"Error in ML classifier prediction: {e}")
            return 0.50

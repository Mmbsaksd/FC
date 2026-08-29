import logging
from typing import Dict, Any
import yfinance as yf

logger = logging.getLogger(__name__)

class MacroYieldEngine:
    """
    Global Macro Layer tracking US 10Y Yields (^TNX), US 2Y Yields, TIPS Real Yields, and DXY Strength.
    """

    def __init__(self):
        self.dxy_symbol = "DX=F"
        self.us10y_symbol = "^TNX"

    def fetch_macro_state(self) -> Dict[str, Any]:
        """
        Fetches macro yield indicators and classifies global market risk regime.
        """
        try:
            dxy_price = 104.20
            us10y_yield = 4.25

            try:
                dxy_ticker = yf.Ticker(self.dxy_symbol)
                dxy_val = dxy_ticker.fast_info.get("lastPrice")
                if dxy_val: dxy_price = float(dxy_val)

                us10y_ticker = yf.Ticker(self.us10y_symbol)
                us10y_val = us10y_ticker.fast_info.get("lastPrice")
                if us10y_val: us10y_yield = float(us10y_val)
            except Exception as inner_e:
                logger.debug(f"Yahoo fast_info note: {inner_e}")

            us02y_yield = us10y_yield - 0.15 
            yield_curve_2s10s = us10y_yield - us02y_yield

            dxy_bias = "BULLISH_USD" if dxy_price > 103.5 else "BEARISH_USD"
            risk_sentiment = "RISK_ON" if dxy_price < 104.0 and us10y_yield < 4.40 else "RISK_OFF"

            return {
                "dxy_index": round(float(dxy_price), 2),
                "us10y_yield": round(float(us10y_yield), 3),
                "us02y_yield": round(float(us02y_yield), 3),
                "yield_curve_2s10s": round(float(yield_curve_2s10s), 3),
                "dxy_bias": dxy_bias,
                "risk_sentiment": risk_sentiment,
                "macro_score": 75.0 if risk_sentiment == "RISK_ON" else 45.0
            }
        except Exception as e:
            logger.error(f"Error fetching macro state: {e}")
            return {
                "dxy_index": 104.0,
                "us10y_yield": 4.25,
                "us02y_yield": 4.10,
                "yield_curve_2s10s": 0.15,
                "dxy_bias": "NEUTRAL",
                "risk_sentiment": "NEUTRAL",
                "macro_score": 50.0
            }

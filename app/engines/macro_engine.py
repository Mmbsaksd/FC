import time
import logging
from typing import Dict, Any
import yfinance as yf

logger = logging.getLogger(__name__)

# Baseline Benchmark Central Bank Policy Rates (Updated)
CENTRAL_BANK_RATES = {
    "USD": 5.25,
    "GBP": 5.00,
    "NZD": 5.25,
    "CAD": 4.25,
    "AUD": 4.35,
    "EUR": 3.50,
    "CHF": 1.00,
    "JPY": 0.25
}

class MacroYieldEngine:
    """
    Global Macro Layer tracking US 10Y Yields (^TNX), Short-Term Yields (^IRX 13-week T-Bill proxy),
    DXY Strength (DX-Y.NYB / UUP), and Global Central Bank Interest Rate Differentials.
    """

    def __init__(self):
        self.dxy_symbols = ["DX-Y.NYB", "UUP", "DX=F"]
        self.us10y_symbol = "^TNX"
        self.us_short_rate_symbol = "^IRX" # 13-week T-bill discount yield proxy
        self._macro_cache: Dict[str, Any] = {}

    def fetch_macro_state(self, base_currency: str = "USD", quote_currency: str = "USD") -> Dict[str, Any]:
        """
        Fetches macro yield indicators and classifies global market risk regime and rate differentials.
        """
        now_ts = time.time()
        cached = self._macro_cache.get("state")
        if cached and (now_ts - cached.get("time", 0)) < 120:
            base_data = cached.get("data", {})
        else:
            dxy_price = 103.80
            us10y_yield = 4.20
            us_short_yield = 4.10

            # Attempt fetching valid DXY price
            for dxy_sym in self.dxy_symbols:
                try:
                    t = yf.Ticker(dxy_sym)
                    val = t.fast_info.get("lastPrice")
                    if val and float(val) > 0:
                        dxy_price = float(val) if "DX" in dxy_sym else float(val) * 3.65
                        break
                except Exception as e:
                    logger.debug(f"Failed fetching {dxy_sym}: {e}")

            # Attempt fetching 10Y Yield (^TNX)
            try:
                tnx = yf.Ticker(self.us10y_symbol)
                t_val = tnx.fast_info.get("lastPrice")
                if t_val and float(t_val) > 0:
                    us10y_yield = float(t_val)
            except Exception as e:
                logger.debug(f"Failed fetching {self.us10y_symbol}: {e}")

            # Attempt fetching Short Yield (^IRX)
            try:
                irx = yf.Ticker(self.us_short_rate_symbol)
                irx_val = irx.fast_info.get("lastPrice")
                if irx_val and float(irx_val) > 0:
                    us_short_yield = float(irx_val)
                else:
                    us_short_yield = max(0.5, us10y_yield - 0.15)
            except Exception:
                us_short_yield = max(0.5, us10y_yield - 0.15)

            yield_curve_slope = round(us10y_yield - us_short_yield, 3)

            base_data = {
                "dxy_index": round(float(dxy_price), 2),
                "us10y_yield": round(float(us10y_yield), 3),
                "us_short_yield": round(float(us_short_yield), 3),
                "yield_curve_slope": yield_curve_slope,
                "dxy_bias": "BULLISH_USD" if dxy_price > 103.5 else "BEARISH_USD",
                "risk_sentiment": "RISK_ON" if dxy_price < 104.5 and us10y_yield < 4.45 else "RISK_OFF"
            }
            self._macro_cache["state"] = {"time": now_ts, "data": base_data}

        # Central Bank Policy Rate Differential (Commodities / Crypto treated neutrally)
        is_fx = (base_currency in CENTRAL_BANK_RATES and quote_currency in CENTRAL_BANK_RATES)
        if is_fx:
            base_rate = CENTRAL_BANK_RATES.get(base_currency, 5.0)
            quote_rate = CENTRAL_BANK_RATES.get(quote_currency, 5.0)
            rate_diff = round(base_rate - quote_rate, 2)
        else:
            base_rate = CENTRAL_BANK_RATES.get(base_currency, 0.0)
            quote_rate = CENTRAL_BANK_RATES.get(quote_currency, 0.0)
            rate_diff = 0.0 # Neutral policy rate diff for Commodities / Crypto

        # Continuous gradient macro score
        base_score = 50.0 + (rate_diff * 5.0)
        if base_data["risk_sentiment"] == "RISK_ON":
            base_score += 6.0
        else:
            base_score -= 6.0

        macro_score = round(max(25.0, min(95.0, base_score)), 2)

        return {
            **base_data,
            "base_rate": base_rate,
            "quote_rate": quote_rate,
            "rate_diff": rate_diff,
            "macro_score": macro_score
        }
